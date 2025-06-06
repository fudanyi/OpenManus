import ast
import json
import time
import traceback
from enum import Enum
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
from app.config import config

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

        # Initialize the planning tool if not provided
        if "planning_tool" not in data:
            data["planning_tool"] = PlanningTool()

        # Call parent's init with the processed data
        super().__init__(agents, **data)

        # 在 super().__init__ 之后设置 session_id
        self.session_id = session_id

        # Set executor_keys to all agent keys if not specified
        if not self.executor_keys:
            self.executor_keys = list(self.agents.keys())

        # Set the planning tool
        self.planning_tool = self.planningAgent.available_tools.get_tool("planning")

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
                self.planning_tool = self.planningAgent.available_tools.get_tool(
                    "planning"
                )

                has_plan = False
                if (
                    self.active_plan_id
                    and self.active_plan_id in self.planning_tool.plans
                ):
                    current_step_index, step_info = await self._get_current_step_info()
                    if current_step_index is not None:
                        logger.info(
                            "already have a running plan {}/{}".format(
                                self.active_plan_id, current_step_index
                            )
                        )
                        has_plan = True

                if has_plan:
                    # 如果已经有plan，则不创建新的plan
                    self.memory.add_message(Message.user_message(input_text))
                else:
                    # 没有plan，创建新的plan
                    logger.info("no plan, create new plan")
                    await self._create_initial_plan(input_text)
                    # Verify plan was created successfully
                    if self.active_plan_id not in self.planning_tool.plans:
                        logger.error(
                            f"Plan creation failed. Plan ID {self.active_plan_id} not found in planning tool {self.planning_tool.plans}."
                        )

                        # Create a simple plan with the input text as the only step
                        self.planning_tool.plans[self.active_plan_id] = {
                            "title": input_text,
                            "sections": [
                                {
                                    "title": "默认计划",
                                    "steps": [input_text],
                                    "types": ["answerbot"],
                                }
                            ],
                            "step_statuses": ["not_started"],
                            "step_notes": [""],
                        }
                        logger.info(
                            f"Created simple plan with input text as step: {input_text}"
                        )
                        # return f"Failed to create plan for: {input_text}"

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
                    # Check if the plan only has answerbot steps
                    plan_data = self.planning_tool.plans.get(self.active_plan_id, {})
                    sections = plan_data.get("sections", [])

                    # Check if all steps are answerbot type
                    only_answerbot = True
                    for section in sections:
                        types = section.get("types", [])
                        for step_type in types:
                            if step_type != "answerbot":
                                only_answerbot = False
                                break
                        if not only_answerbot:
                            break

                    if only_answerbot:
                        # If plan only has answerbot steps, skip finalization
                        result = None
                        break
                    else:
                        # Otherwise finalize the plan
                        result = await self._finalize_plan()
                        break

                Output.print(
                    type="liveStatus",
                    text=f"执行计划步骤 {self.current_step_index + 1}/{sum(len(section['steps']) for section in self.planning_tool.plans[self.active_plan_id].get('sections', []))}",
                )

                # Execute current step with appropriate agent
                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)

                if config.llm["default"].enable_auto_summary:
                    # summarize previous steps and start new step
                    Output.print(
                        type="liveStatus",
                        text="准备下一步",
                    )
                    if self.current_step_index is not None and self.current_step_index > 0:
                        await self._summarize_messages()
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
            if not planning_tool._current_plan_id:
                planning_tool._current_plan_id = self.active_plan_id
            else:
                self.active_plan_id = planning_tool._current_plan_id

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
            logger.error(f"Error getting plan: {str(e)}")
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

    async def _summarize_messages(self) -> None:
        """Summarize all messages in memory and reset memory to only contain original request and summary."""
        try:
            system_message = Message.system_message(
                "You are a information extraction assistant."
            )

            # Get all current messages
            user_messages = self.memory.messages.copy()
            
            # Add request for summary
            user_messages.append(
                Message.user_message(
                "Your task is to summarize previous conversation(representing partial execution of an agent) into a comprehensive document that captures the insights, any fact details, any important information fetched,  any deliverables produced and any recommendation to avoid errors."
                "The document must contain enough and correct details for subsequent execution to complete user goal without duplicate refetching/redoing， especially schema details."
                "Assume subsequent execution only has access to this summary."
                )
            )

            # Get summary from LLM
            response = await self.llm.ask(
                messages=user_messages,
                system_msgs=[system_message],
            )

            if response is None:
                logger.warning("No response received from LLM in _summarize_messages")
                return

            # Find the original user request (first user message)
            original_request = None
            for msg in self.memory.messages:
                if msg.role == "user":
                    original_request = msg
                    break

            if original_request is None:
                logger.warning("No original user request found in memory")
                return

            # Get the summary content, handling both string and object responses
            summary_content = response.content if hasattr(response, 'content') else str(response)


            # 获取成功的python/querydata工具调用结果
            real_results = []
            for i, msg in enumerate(self.memory.all_messages):
                if msg.role == "tool":
                    if msg.name == "python_execute":
                        try:
                            # 去掉前缀
                            prefix = "Observed output of cmd `python_execute` executed:\n"
                            json_like_str = msg.content[len(prefix):]

                            # 使用 ast.literal_eval 安全解析成字典
                            result = ast.literal_eval(json_like_str)

                            if result.get("success") == True and (len(result.get("output_files")) >0 or len(result.get("charts")) >0):
                                # Get the previous message
                                prev_msg = self.memory.all_messages[i-1]
                                real_results.append((prev_msg, msg))
                        except:
                            continue
                    elif msg.name == "datasource":
                        try:
                            # 去掉前缀
                            prefix = "Observed output of cmd `datasource` executed:\n"
                            json_like_str = msg.content[len(prefix):]

                            # 使用 ast.literal_eval 安全解析成字典
                            result = ast.literal_eval(json_like_str)

                            if result.get("error") == False and result.get("data").get("csv_filename"):
                                prev_msg = self.memory.all_messages[i-1]
                                real_results.append((prev_msg, msg))
                        except:
                            continue

            logger.info(f"real_results: {real_results.__len__()}")

            # Convert real_results tuples to Message objects
            real_result_messages = []
            for prev_msg, tool_msg in real_results:
                real_result_messages.extend([prev_msg, tool_msg])

            # Reset memory to only contain original request and summary
            self.memory.messages = [
                original_request,
                *real_result_messages,  # Now contains Message objects instead of tuples
                *[msg for msg in self.memory.messages if msg.type == "summary"],
                Message.summary_message("Summary of previous partial execution: \n" +"=============\n"+ summary_content+"\n=============\n")
            ]

        except Exception as e:
            logger.error(f"Error summarizing messages: {e}")

    async def _finalize_plan(self) -> str:
        """Finalize the plan and provide a summary using the flow's LLM directly."""
        try:
            system_message = Message.system_message(
                "You are a summarize assistant. Your task is to summarize previous messages into a concise summary including deliverables, valuable insights, potential next steps and any final thoughts. "
            )

            self.memory.add_message(
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
