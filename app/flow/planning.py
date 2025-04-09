import json
import time
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import Field

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Message, ToolChoice
from app.tool import PlanningTool
from extensions.output import Output
from extensions.tool.human_input import HumanInput


class PlanStepStatus(str, Enum):
    """Enum class defining possible statuses of a plan step"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

    @classmethod
    def get_all_statuses(cls) -> list[str]:
        """Return a list of all possible step status values"""
        return [status.value for status in cls]

    @classmethod
    def get_active_statuses(cls) -> list[str]:
        """Return a list of values representing active statuses (not started or in progress)"""
        return [cls.NOT_STARTED.value, cls.IN_PROGRESS.value]

    @classmethod
    def get_status_marks(cls) -> Dict[str, str]:
        """Return a mapping of statuses to their marker symbols"""
        return {
            cls.COMPLETED.value: "[✓]",
            cls.IN_PROGRESS.value: "[→]",
            cls.BLOCKED.value: "[!]",
            cls.NOT_STARTED.value: "[ ]",
        }


class PlanningFlow(BaseFlow):
    """A flow that manages planning and execution of tasks using agents."""

    llm: LLM = Field(default_factory=lambda: LLM())
    planning_tool: PlanningTool = Field(default_factory=PlanningTool)
    humaninput_tool: HumanInput = Field(default_factory=HumanInput)
    executor_keys: List[str] = Field(default_factory=list)
    active_plan_id: str = Field(default_factory=lambda: f"plan_{int(time.time())}")
    current_step_index: Optional[int] = None

    def __init__(
        self, agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], **data
    ):
        # Set executor keys before super().__init__
        if "executors" in data:
            data["executor_keys"] = data.pop("executors")

        # Set plan ID if provided
        if "plan_id" in data:
            data["active_plan_id"] = data.pop("plan_id")

        # Initialize the planning tool if not provided
        if "planning_tool" not in data:
            planning_tool = PlanningTool()
            data["planning_tool"] = planning_tool

        # Call parent's init with the processed data
        super().__init__(agents, **data)

        # Set executor_keys to all agent keys if not specified
        if not self.executor_keys:
            self.executor_keys = list(self.agents.keys())

    def get_executor(self, step_type: Optional[str] = None) -> BaseAgent:
        """
        Get an appropriate executor agent for the current step.
        Can be extended to select agents based on step type/requirements.
        """
        # If step type is provided and matches an agent key, use that agent
        if step_type and step_type in self.agents:
            return self.agents[step_type]

        # Otherwise use the first available executor or fall back to primary agent
        for key in self.executor_keys:
            if key in self.agents:
                return self.agents[key]

        # Fallback to primary agent
        return self.primary_agent

    async def execute(self, input_text: str) -> str:
        """Execute the planning flow with agents."""
        try:
            if not self.primary_agent:
                raise ValueError("No primary agent available")

            # Create initial plan if input provided
            if input_text:
                await self._create_initial_plan(input_text)

                # Verify plan was created successfully
                if self.active_plan_id not in self.planning_tool.plans:
                    logger.error(
                        f"Plan creation failed. Plan ID {self.active_plan_id} not found in planning tool."
                    )
                    return f"Failed to create plan for: {input_text}"

            result = ""
            while True:
                # Get current step to execute
                self.current_step_index, step_info = await self._get_current_step_info()

                # Exit if no more steps or plan completed
                if self.current_step_index is None:
                    result += await self._finalize_plan()
                    break

                Output.print(
                    type="liveStatus",
                    text=f"Executing plan step {self.current_step_index + 1}/{sum(len(section['steps']) for section in self.planning_tool.plans[self.active_plan_id].get('sections', []))}",
                )

                # Execute current step with appropriate agent
                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)
                step_result = await self._execute_step(executor, step_info)
                result += step_result + "\n"

                Output.print(
                    type="liveStatus",
                    text=f"Completed plan step {self.current_step_index + 1}/{sum(len(section['steps']) for section in self.planning_tool.plans[self.active_plan_id].get('sections', []))}",
                )

                # Check if agent wants to terminate
                if hasattr(executor, "state") and executor.state == AgentState.FINISHED:
                    break

            Output.print(
                type="liveStatus",
                text="Plan completed",
            )

            return result
        except Exception as e:
            logger.error(f"Error in PlanningFlow: {str(e)}")
            return f"Execution failed: {str(e)}"

    async def _create_initial_plan(self, request: str) -> None:
        """Create an initial plan based on the request using the flow's LLM and PlanningTool."""
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        # Create a system message for plan creation
        system_message = Message.system_message(
            "You are a planning assistant. Create a concise, actionable plan with clear steps. "
            "Do not overthink for simple tasks."
            "Focus on key milestones rather than detailed sub-steps. "
            "Optimize for clarity and efficiency."
            "Default working language: Chinese"
            "Use the language specified by user in messages as the working language when explicitly provided"
            "All thinking and responses must be in the working language"
            "Natural language arguments in tool calls must be in the working language"
            "Avoid using pure lists and bullet points format in any language"
        )

        # Create a user message with the request
        user_message = Message.user_message(
            f"Create a reasonable plan with clear steps to accomplish the task: {request}"
        )
        user_messages = [user_message]

        Output.print(
            type="liveStatus",
            text="Planning",
        )

        while True:
            # Call LLM with PlanningTool
            response = await self.llm.ask_tool(
                messages=user_messages,
                system_msgs=[system_message],
                tools=[self.planning_tool.to_param()],
                tool_choice=ToolChoice.AUTO,
            )

            if response.tool_calls:
                plan_text = ""
                for tool_call in response.tool_calls:
                    if tool_call.function.name == "planning":
                        args = tool_call.function.arguments
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse tool arguments: {args}")
                                continue

                        plan_text += f"{response.content}\n\n"
                        plan_text += f"{args['title']}\n"
                        for section in args["sections"]:
                            plan_text += f"## {section['title']}\n"
                            for step in section["steps"]:
                                plan_text += f"[ ] {step}\n"
                        plan_text += "\n您觉得我的计划怎么样？如果有什么问题，请告诉我。如果觉得我的计划还不错，那我们就按照这个计划执行啦~~\n"

                # ask user for confirmation
                # {
                #     "id": "66bd3c68-10e0-49b0-b9dc-5fb3629317d8",
                #     "type": "execute",
                #     "timestamp": 1743657699874,
                #     "text": "\ud83d\udd27 Activating tool 'human_input'...",
                #     "data": {
                #         "status": "executing",
                #         "id": "toolu_01KA96sG61AcBdyvqpHnBE87",
                #         "name": "human_input",
                #         "arguments": {
                #             "type": "feedback",
                #             "prompt": "I propose the following data collection and analysis plan:\n\n1. Create a structured dataset with the following columns:\n   - Breed Name\n   - Recognition Status (which organizations recognize it)\n   - Classification Category (Natural, Hybrid, Mutation, etc.)\n   - Origin/Country\n   - Physical Characteristics\n   - Recognition Year\n\n2. Collect data from each major organization:\n   - TICA recognized breeds\n   - CFA recognized breeds\n   - FIFe recognized breeds\n   - WCF recognized breeds\n\n3. Create comparative analysis:\n   - Total number of recognized breeds by each organization\n   - Overlap analysis\n   - Classification distribution\n   - Historical recognition trends\n\nDo you agree with this plan? Would you like to add or modify any aspects?",
                #         },
                #     },
                # },
                Output.print(
                    type="execute",
                    text="\ud83d\udd27 Activating tool 'human_input'...",
                    data={
                        "status": "executing",
                        "id": "toolu_01KA96sG61AcBdyvqpHnBE87",
                        "name": "human_input",
                        "arguments": {
                            "type": "feedback",
                            "prompt": plan_text,
                        },
                    },
                )

                ok_words = ["ok", "okay", "yes", "go", "确认", "是", "好", "可以"]
                human_input = await self.humaninput_tool.execute(
                    prompt=plan_text,
                    type="confirm",
                    default="yes",
                )

                # {
                #     "id": "eb185246-5412-4c05-999e-c7dad8e9c8b6",
                #     "type": "execute",
                #     "timestamp": 1744181364925,
                #     "text": "\ud83c\udfaf Tool 'human_input' completed its mission!",
                #     "data": {
                #         "status": "completed",
                #         "id": "toolu_01S8Mz8jYpXP6vGQgZJBZVCh",
                #         "name": "human_input",
                #         "arguments": {
                #             "type": "feedback",
                #             "prompt": "\u6211\u8ba1\u5212\u4ece\u4ee5\u4e0b\u51e0\u4e2a\u7ef4\u5ea6\u5206\u6790CFA\u548cFIFe\u7684\u732b\u79cd\u5206\u7c7b\u6807\u51c6\uff1a\n1. \u5206\u7c7b\u4f53\u7cfb\u5bf9\u6bd4\uff08\u5305\u62ec\u5206\u7ec4\u65b9\u5f0f\u3001\u8bc4\u5224\u6807\u51c6\u7b49\uff09\n2. \u8ba4\u8bc1\u54c1\u79cd\u6570\u91cf\u7edf\u8ba1\n3. \u4e24\u5927\u673a\u6784\u7684\u5171\u540c\u70b9\u548c\u5dee\u5f02\n4. \u5bf9\u732b\u79cd\u9009\u62e9\u7684\u5b9e\u9645\u6307\u5bfc\u610f\u4e49\n\n\u8bf7\u95ee\u8fd9\u4e2a\u5206\u6790\u6846\u67b6\u662f\u5426\u5408\u9002\uff1f\u6216\u8005\u60a8\u89c9\u5f97\u8fd8\u9700\u8981\u8865\u5145\u5176\u4ed6\u65b9\u9762\uff1f",
                #         },
                #         "result": {
                #             "output": "\u5f88\u597d\uff0c\u53ef\u4ee5\u7b80\u5355\u4e00\u70b9",
                #             "error": null,
                #             "base64_image": null,
                #             "system": null,
                #         },
                #         "base64_image": null,
                #     },
                # },
                Output.print(
                    type="execute",
                    text="\ud83c\udfaf Tool 'human_input' completed its mission!",
                    data={
                        "status": "completed",
                        "id": "toolu_01KA96sG61AcBdyvqpHnBE87",
                        "name": "human_input",
                        "arguments": {
                            "type": "feedback",
                            "prompt": plan_text,
                        },
                        "result": {
                            "output": human_input.output,
                            "error": None,
                            "base64_image": None,
                            "system": None,
                        },
                        "base64_image": None,
                    },
                )

                if human_input.output.strip().lower() in ok_words:
                    break
                else:
                    user_messages.append(Message.assistant_message(plan_text))
                    user_messages.append(Message.user_message(human_input.output))

        # Process tool calls if present
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call.function.name == "planning":
                    # Parse the arguments
                    args = tool_call.function.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse tool arguments: {args}")
                            continue

                    # Ensure plan_id is set correctly and execute the tool
                    args["plan_id"] = self.active_plan_id

                    # Execute the tool via ToolCollection instead of directly
                    result = await self.planning_tool.execute(**args)

                    Output.print(
                        type="liveStatus",
                        text=f"Plan {self.active_plan_id} created",
                    )

                    logger.info(f"Plan creation result: {str(result)}")
                    return

        # If execution reached here, create a default plan
        logger.warning("Creating default plan")

        # Create default plan using the ToolCollection
        await self.planning_tool.execute(
            **{
                "command": "create",
                "plan_id": self.active_plan_id,
                "title": f"Plan for: {request[:50]}{'...' if len(request) > 50 else ''}",
                "steps": ["Analyze request", "Execute task", "Verify results"],
            }
        )

    async def _get_current_step_info(self) -> tuple[Optional[int], Optional[dict]]:
        """
        Parse the current plan to identify the first non-completed step's index and info.
        Returns (None, None) if no active step is found.
        """
        if (
            not self.active_plan_id
            or self.active_plan_id not in self.planning_tool.plans
        ):
            logger.error(f"Plan with ID {self.active_plan_id} not found")
            return None, None

        try:
            # Direct access to plan data from planning tool storage
            plan_data = self.planning_tool.plans[self.active_plan_id]
            sections = plan_data.get("sections", [])
            step_statuses = plan_data.get("step_statuses", [])

            # Find first non-completed step
            current_index = 0
            for section in sections:
                for step in section["steps"]:
                    if current_index >= len(step_statuses):
                        logger.warning("Step statuses array shorter than steps")
                        return None, None

                    if step_statuses[current_index] != "completed":
                        return current_index, {
                            "section_title": section["title"],
                            "step": step,
                            "status": step_statuses[current_index],
                        }
                    current_index += 1

            return None, None  # All steps completed
        except Exception as e:
            logger.error(f"Error getting current step info: {e}")
            return None, None

    async def _execute_step(self, executor: BaseAgent, step_info: dict) -> str:
        """Execute the current step with the specified agent using agent.run()."""
        # Prepare context for the agent with current plan status
        plan_status = await self._get_plan_text()
        step_text = step_info.get("step")

        # Create a prompt for the agent to execute the current step
        step_prompt = f"""
        CURRENT PLAN STATUS:
        {plan_status}

        YOUR CURRENT TASK:
        You are now working on step {self.current_step_index}: "{step_text}"

        Please execute this step using the appropriate tools. When you're done, provide a summary of what you accomplished.
        """

        # Use agent.run() to execute the step
        try:
            step_result = await executor.run(step_prompt)

            # Mark the step as completed after successful execution
            await self._mark_step_completed()

            return step_result
        except Exception as e:
            logger.error(f"Error executing step {self.current_step_index}: {e}")
            return f"Error executing step {self.current_step_index}: {str(e)}"

    async def _mark_step_completed(self) -> None:
        """Mark the current step as completed."""
        if self.current_step_index is None:
            return

        try:
            # Mark the step as completed
            await self.planning_tool.execute(
                command="mark_step",
                plan_id=self.active_plan_id,
                step_index=self.current_step_index,
                step_status=PlanStepStatus.COMPLETED.value,
            )
            logger.info(
                f"Marked step {self.current_step_index} as completed in plan {self.active_plan_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to update plan status: {e}")
            # Update step status directly in planning tool storage
            if self.active_plan_id in self.planning_tool.plans:
                plan_data = self.planning_tool.plans[self.active_plan_id]
                step_statuses = plan_data.get("step_statuses", [])

                # Ensure the step_statuses list is long enough
                while len(step_statuses) <= self.current_step_index:
                    step_statuses.append(PlanStepStatus.NOT_STARTED.value)

                # Update the status
                step_statuses[self.current_step_index] = PlanStepStatus.COMPLETED.value
                plan_data["step_statuses"] = step_statuses

    async def _get_plan_text(self) -> str:
        """Get the current plan as formatted text."""
        try:
            result = await self.planning_tool.execute(
                command="get", plan_id=self.active_plan_id
            )
            return result.output if hasattr(result, "output") else str(result)
        except Exception as e:
            logger.error(f"Error getting plan: {e}")
            return self._generate_plan_text_from_storage()

    def _generate_plan_text_from_storage(self) -> str:
        """Generate plan text directly from storage if the planning tool fails."""
        try:
            if self.active_plan_id not in self.planning_tool.plans:
                return f"Error: Plan with ID {self.active_plan_id} not found"

            plan_data = self.planning_tool.plans[self.active_plan_id]
            title = plan_data.get("title", "Untitled Plan")
            sections = plan_data.get("sections", [])
            step_statuses = plan_data.get("step_statuses", [])
            step_notes = plan_data.get("step_notes", [])

            # Calculate total steps
            total_steps = sum(len(section["steps"]) for section in sections)

            # Ensure step_statuses and step_notes match the number of steps
            while len(step_statuses) < total_steps:
                step_statuses.append(PlanStepStatus.NOT_STARTED.value)
            while len(step_notes) < total_steps:
                step_notes.append("")

            # Count steps by status
            status_counts = {status: 0 for status in PlanStepStatus.get_all_statuses()}

            for status in step_statuses:
                if status in status_counts:
                    status_counts[status] += 1

            completed = status_counts[PlanStepStatus.COMPLETED.value]
            progress = (completed / total_steps) * 100 if total_steps > 0 else 0

            plan_text = f"Plan: {title} (ID: {self.active_plan_id})\n"
            plan_text += "=" * len(plan_text) + "\n\n"

            plan_text += f"Progress: {completed}/{total_steps} steps completed ({progress:.1f}%)\n"
            plan_text += f"Status: {status_counts[PlanStepStatus.COMPLETED.value]} completed, {status_counts[PlanStepStatus.IN_PROGRESS.value]} in progress, "
            plan_text += f"{status_counts[PlanStepStatus.BLOCKED.value]} blocked, {status_counts[PlanStepStatus.NOT_STARTED.value]} not started\n\n"

            # Add each section with its steps
            current_step_index = 0
            for section in sections:
                plan_text += f"## {section['title']}\n"
                for step in section["steps"]:
                    status = step_statuses[current_step_index]
                    notes = step_notes[current_step_index]

                    status_symbol = PlanStepStatus.get_status_marks().get(status, "[ ]")
                    plan_text += f"  {status_symbol} {step}\n"
                    if notes:
                        plan_text += f"     Notes: {notes}\n"

                    current_step_index += 1
                plan_text += "\n"

            return plan_text
        except Exception as e:
            logger.error(f"Error generating plan text: {e}")
            return f"Error generating plan text: {str(e)}"

    async def _finalize_plan(self) -> str:
        """Finalize the plan and provide a summary using the flow's LLM directly."""
        plan_text = await self._get_plan_text()

        # Create a summary using the flow's LLM directly
        try:
            system_message = Message.system_message(
                "You are a planning assistant. Your task is to summarize the completed plan."
            )

            user_message = Message.user_message(
                f"The plan has been completed. Here is the final plan status:\n\n{plan_text}\n\nPlease provide a summary of what was accomplished and any final thoughts."
            )

            response = await self.llm.ask(
                messages=[user_message], system_msgs=[system_message]
            )

            return f"Plan completed:\n\n{response}"
        except Exception as e:
            logger.error(f"Error finalizing plan with LLM: {e}")

            # Fallback to using an agent for the summary
            try:
                agent = self.primary_agent
                summary_prompt = f"""
                The plan has been completed. Here is the final plan status:

                {plan_text}

                Please provide a summary of what was accomplished and any final thoughts.
                """
                summary = await agent.run(summary_prompt)
                return f"Plan completed:\n\n{summary}"
            except Exception as e2:
                logger.error(f"Error finalizing plan with agent: {e2}")
                return "Plan completed. Error generating summary."
