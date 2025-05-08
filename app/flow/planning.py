import json
import time
from enum import Enum
import traceback
from typing import Dict, List, Optional, Union

from pydantic import Field

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory, Message, ToolChoice
from app.tool import PlanningTool
from app.tool.tool_collection import ToolCollection
from extensions.agent.planner import Planner
from extensions.output import Output
from extensions.tool.human_input import HumanInput
from extensions.tool.result_reporter import ResultReporter


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

    session_id: Optional[str] = None
    llm: LLM = Field(default_factory=lambda: LLM())
    planning_tool: PlanningTool = Field(default_factory=PlanningTool)
    planningAgent: BaseAgent = Field(default_factory=lambda: Planner())
    humaninput_tool: HumanInput = Field(default_factory=HumanInput)
    executor_keys: List[str] = Field(default_factory=list)
    active_plan_id: str = Field(default_factory=lambda: f"plan_{int(time.time())}")
    current_step_index: Optional[int] = None
    memory: Memory = Field(default_factory=Memory, description="Flow's memory store")

    def __init__(
        self,
        agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]],
        session_id: Optional[str] = None,
        **data,
    ):
        # Set executor keys before super().__init__
        if "executors" in data:
            data["executor_keys"] = data.pop("executors")

        # Set plan ID if provided
        if "plan_id" in data:
            data["active_plan_id"] = data.pop("plan_id")

        # Set the planning tool
        self.planning_tool = self.planningAgent.available_tools.get_tool("planning")

        # Initialize the planning tool if not provided
        if "planning_tool" not in data:
            planning_tool = self.planning_tool
            data["planning_tool"] = planning_tool

        # Call parent's init with the processed data
        super().__init__(agents, **data)

        # 在 super().__init__ 之后设置 session_id
        self.session_id = session_id

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

            # Create initial plan if there is no plan
            if input_text:
                self.planningAgent.memory = self.memory
                await self._create_initial_plan(input_text)

                # Verify plan was created successfully
                if self.active_plan_id not in self.planning_tool.plans:
                    logger.error(
                        f"Plan creation failed. Plan ID {self.active_plan_id} not found in planning tool."
                    )
                    return f"Failed to create plan for: {input_text}"

            # 保存session
            if self.session_id:
                from extensions.session import save_flow_to_session

                save_flow_to_session(self.session_id, self)

            result = ""
            while True:
                # Get current step to execute
                self.current_step_index, step_info = await self._get_current_step_info()

                # Exit if no more steps or plan completed
                if self.current_step_index is None:
                    result = await self._finalize_plan()
                    break

                Output.print(
                    type="liveStatus",
                    text=f"执行计划步骤 {self.current_step_index + 1}/{sum(len(section['steps']) for section in self.planning_tool.plans[self.active_plan_id].get('sections', []))}",
                )

                # Execute current step with appropriate agent
                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)
                executor.memory = self.memory
                step_result = await self._execute_step(executor, step_info)
                result += step_result + "\n"

                Output.print(
                    type="liveStatus",
                    text=f"完成计划步骤 {self.current_step_index + 1}/{sum(len(section['steps']) for section in self.planning_tool.plans[self.active_plan_id].get('sections', []))}",
                )

                # Check if agent wants to terminate
                if hasattr(executor, "state") and executor.state == AgentState.FINISHED:
                    break

                # 保存session
                if self.session_id:
                    from extensions.session import save_flow_to_session

                    save_flow_to_session(self.session_id, self)

            Output.print(
                type="liveStatus",
                text="计划完成",
            )

            return result
        except Exception as e:
            logger.error(
                f"Error in PlanningFlow: {str(e)}, e.traceback: {traceback.format_exc()}"
            )
            return f"Execution failed: {str(e)}"

    async def _create_initial_plan(self, request: str) -> None:
        """Create an initial plan based on the request using the flow's LLM and PlanningTool."""
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        # Output.print(
        #     type="liveStatus",
        #     text="规划中...",
        # )

        response = await self.planningAgent.run(request)

        # Log the planning agent's response
        logger.info(f"Planning agent response: {response}")

        # Output the planning status to the user
        Output.print(
            type="liveStatus",
            text="计划创建完成",
        )

        # Get the planning tool and retrieve the active plan ID
        planning_tool = self.planningAgent.available_tools.get_tool("planning")
        if planning_tool and hasattr(planning_tool, "_current_plan_id"):
            self.active_plan_id = (
                planning_tool._current_plan_id
                if planning_tool._current_plan_id
                else f"plan_{int(time.time())}"
            )
        self.planning_tool = planning_tool

        # If execution reached here, create a default plan
        logger.info(f"Created plan for {request} with id: {self.active_plan_id}")

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
                for i, step in enumerate(section["steps"]):
                    if current_index >= len(step_statuses):
                        logger.warning("Step statuses array shorter than steps")
                        return None, None

                    if step_statuses[current_index] != "completed":
                        return current_index, {
                            "section_title": section["title"],
                            "step": step,
                            "status": step_statuses[current_index],
                            "type": section["types"][i],
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
        try:
            system_message = Message.system_message(
                "You are a summarize assistant. Your task is to summarize previous messages into a concise summary including deliverables, valuable insights, potential next steps and any final thoughts."
            )

            self.memory.messages.append(
                Message.user_message(
                    "Please summarize previous messages into a concise summary including deliverables, valuable insights, potential next steps and any final thoughts"
                    "Then always use result_reporter tool to report deliverables. But DONOT mention the tool in your summary."
                )
            )
            user_messages = self.memory.messages

            available_tools = ToolCollection(ResultReporter())

            response = await self.llm.ask_tool(
                messages=user_messages,
                system_msgs=[system_message],
                tool_choice=ToolChoice.AUTO,
                tools=available_tools.to_params(),
            )

            if response is None:
                logger.warning("No response received from LLM in _finalize_plan")
                return "Plan completed. Unable to generate summary due to LLM response error."

            # Extract deliverables from tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call.function.name == "result_reporter":
                        try:
                            args = json.loads(tool_call.function.arguments)
                            if "deliverables" in args:
                                Output.print(
                                    type="finalResult",
                                    text=response.content,
                                    data={
                                        "deliverables": args["deliverables"],
                                    },
                                )
                                return response.content
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing deliverables JSON: {e}")

            return "Plan completed. No deliverables found in response."
        except Exception as e:
            logger.error(f"Error finalizing plan with LLM: {e}")
            return "Plan completed. Error generating summary."
