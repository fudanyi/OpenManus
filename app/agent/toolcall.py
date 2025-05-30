import base64
import json
import ast
import os
from typing import Any, List, Optional, Union

from pydantic import Field

from app.config import config
from app.agent.react import ReActAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, Role, ToolCall, ToolChoice
from app.tool import CreateChatCompletion, Terminate, ToolCollection
from extensions.output import Output


TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    _current_base64_image: Optional[str] = None

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        try:
            Output.print(
                type="liveStatus",
                text="思考中...",
            )

            # check if last func message is a python tools call with image output, if yes need to call ask_tool_with_image
            last_message = self.messages[-2] if self.messages else None
            # print("\n")
            # print(last_message)
            # print("\n")

            is_python_execute = (
                last_message
                and last_message.role == Role.TOOL
                and last_message.name == "python_execute"
            )

            has_output_files = False
            if is_python_execute and last_message.content:
                try:
                    # Try to parse the content as JSON to check for output_files

                    content_dict = last_message.content.replace("Observed output of cmd `python_execute` executed:", "")

                    content_dict = ast.literal_eval(content_dict)

                    # Only check for image files in output_files
                    has_output_files = (
                        "output_files" in content_dict
                        and content_dict["output_files"]
                        and any(
                            file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                            for file in content_dict["output_files"]
                        )
                    )
                except json.JSONDecodeError as err:
                    # If content is not JSON, check if it contains image file extensions
                    has_output_files = any(
                        ext in last_message.content.lower()
                        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']
                    )


            if is_python_execute and has_output_files:
                # Use ask_tool_with_image for python_execute results with output files
                # print("\n using image think")

                response = await self.llm.ask_tool_with_image(
                    messages=self.messages,
                    tools=self.available_tools.to_params(),
                    images=[f for f in content_dict.get("output_files", []) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))],
                    tool_choice=self.tool_choices,
                    system_msgs=(
                        [Message.system_message(self.system_prompt)]
                        if self.system_prompt
                        else None
                    ),
                )
            else:
                # Regular ask_tool for other messages
                response = await self.llm.ask_tool(
                    messages=self.messages,
                    system_msgs=(
                        [Message.system_message(self.system_prompt)]
                        if self.system_prompt
                        else None
                    ),
                    tools=self.available_tools.to_params(),
                    tool_choice=self.tool_choices,
                )
        except ValueError:
            raise
        except Exception as e:
            # Check if this is a RetryError containing TokenLimitExceeded
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(
                    f"🚨 Token limit error (from RetryError): {token_limit_error}"
                )
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum token limit reached, cannot continue execution: {str(token_limit_error)}"
                    )
                )
                self.state = AgentState.FINISHED
                return False
            raise

        self.tool_calls = tool_calls = (
            response.tool_calls if response and response.tool_calls else []
        )
        content = response.content if response and response.content else ""

        # Log response info
        logger.info(f"✨ {self.name}'s thoughts: {content}")

        # Output.print(
        #     type="chat",
        #     text=f"✨ {self.name}'s thoughts: {content}",
        #     data={
        #         "sender": "assistant",
        #         "agent": self.name,
        #         "message": f"{content}",
        #     },
        # )

        logger.info(
            f"🛠️ {self.name} selected {len(tool_calls) if tool_calls else 0} tools to use"
        )
        if tool_calls:
            logger.info(
                f"🧰 Tools being prepared: {[call.function.name for call in tool_calls]}"
            )
            logger.info(f"🔧 Tool arguments: {tool_calls[0].function.arguments}")

            # Output.print(
            #     type="liveStatus",
            #     text=f"🧰 准备工具: {[call.function.name for call in tool_calls]}",
            # )

        try:
            if response is None:
                raise RuntimeError("No response received from the LLM")

            # Handle different tool_choices modes
            if self.tool_choices == ToolChoice.NONE:
                if tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if content:
                    self.memory.add_message(Message.assistant_message(content))
                    return True
                return False

            # Create and add assistant message
            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls
                else Message.assistant_message(content)
            )
            self.memory.add_message(assistant_msg)

            if self.tool_choices == ToolChoice.REQUIRED and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == ToolChoice.AUTO and not self.tool_calls:
                return bool(content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        results = []
        for command in self.tool_calls:
            # Reset base64_image for each tool call
            self._current_base64_image = None

            Output.print(
                type="liveStatus",
                text=f"执行 '{command.function.name}'...",
            )

            result_raw = await self.execute_tool(command)

            Output.print(
                type="liveStatus",
                text=f"完成 '{command.function.name}'...",
            )

            if self.max_observe:
                result = result_raw[: self.max_observe]

            logger.info(
                f"🎯 Tool '{command.function.name}' completed its mission! Result: {result_raw}"
            )

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
                base64_image=self._current_base64_image,
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        # Parse arguments
        args = json.loads(command.function.arguments or "{}")

        try:

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")

            # DEMO HACK: Convert paths to relative for certain tools
            args_to_print = args.copy() if isinstance(args, dict) else {}
            if name == "file_saver" and isinstance(args, dict) and "file_path" in args:
                args_to_print["file_path"] = os.path.basename(args["file_path"])
            elif name == "str_replace_editor" and isinstance(args, dict) and "path" in args:
                args_to_print["path"] = os.path.basename(args["path"])

            Output.print(
                type="execute",
                text=f"🔧 激活工具 '{name}'...",
                data={
                    "status": "executing",
                    "id": command.id,
                    "name": name,
                    "arguments": args_to_print,
                },
            )

            if name == "python_execute":
                args["toolcall_id"] = command.id

            result = await self.available_tools.execute(name=name, tool_input=args)

            # Handle special tools
            await self._handle_special_tool(name=name, result=result)

            # DEMO HACK: Convert paths to relative for certain tools
            args_to_print = args.copy() if isinstance(args, dict) else {}
            if name == "file_saver" and isinstance(args, dict) and "file_path" in args:
                args_to_print["file_path"] = os.path.basename(args["file_path"])
            elif name == "str_replace_editor" and isinstance(args, dict) and "path" in args:
                args_to_print["path"] = os.path.basename(args["path"])

            Output.print(
                type="execute",
                text=f"🎯 Tool '{name}' completed its mission!",
                data={
                    "status": "completed",
                    "id": command.id,
                    "name": name,
                    "arguments": args_to_print,
                    "result": result,
                    "base64_image": (
                        result.base64_image if hasattr(result, "base64_image") else None
                    ),
                },
            )

            # Check if result is a ToolResult with base64_image
            if hasattr(result, "base64_image") and result.base64_image:
                # Store the base64_image for later use in tool_message
                self._current_base64_image = result.base64_image

                # Format result for display
                observation = (
                    f"Observed output of cmd `{name}` executed:\n{str(result)}"
                    if result
                    else f"Cmd `{name}` completed with no output"
                )
                return observation

            # Format result for display (standard case)
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )

            Output.print(
                type="execute",
                text=f"🚨 Error parsing arguments for '{name}': Invalid JSON format",
                data={
                    "status": "error",
                    "id": command.id,
                    "name": name,
                    "arguments": args,
                    "result": error_msg,
                },
            )

            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)

            Output.print(
                type="execute",
                text=f"🚨 Error executing tool '{name}': {str(e)}",
                data={
                    "status": "error",
                    "id": command.id,
                    "name": name,
                    "arguments": args,
                    "result": error_msg,
                },
            )

            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]
