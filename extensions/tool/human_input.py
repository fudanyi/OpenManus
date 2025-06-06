import json
from typing import Optional

from app.logger import logger
from app.tool.base import BaseTool, ToolResult
from extensions.output import Output
from extensions.utils.user_input import get_user_input


class HumanInput(BaseTool):
    """A tool for getting human input"""

    name: str = "human_input"
    description: str = "Get input from a human user"
    parameters: dict = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt to show to the user",
            },
            "type": {
                "type": "string",
                "description": "The type of input to get",
                "enum": ["new_datasource", "feedback", "others"],
            },
            "default": {
                "type": "string",
                "description": "The default value if user just presses Enter",
            },
        },
        "required": ["prompt"],
    }

    async def execute(
        self,
        prompt: str,
        type: str,
        default: Optional[str] = None,
    ) -> ToolResult:
        """
        Get input from a human user.

        Args:
            prompt (str): The prompt to show to the user
            type (str): The type of input to get
            default (str, optional): Default value if user just presses Enter

        Returns:
            ToolResult: The user's input or the default value
        """
        try:
            # Output.print(
            #     type="chat",
            #     text=f"{prompt}",
            #     data={
            #         "sender": "assistant",
            #         "type": type,
            #         "message": prompt,
            #     },
            # )

            # Show prompt and get input
            if not prompt.endswith("\n"):
                prompt += "\n"
            user_input, attachments, user_input_with_attachment = get_user_input(
                f"{prompt}"
            )

            Output.print(
                type="chat",
                text=f"{user_input}",
                data={
                    "sender": "user",
                    "type": type,
                    "message": user_input,
                    "attachments": (
                        [
                            {"name": "attachments/" + attachment}
                            for attachment in attachments
                        ]
                        if attachments
                        else []
                    ),
                },
            )

            # Return default if input is empty and default is provided
            if not user_input_with_attachment and default is not None:
                return ToolResult(output=default)

            return ToolResult(output=user_input_with_attachment)
        except Exception as e:
            logger.error(f"Error getting human input: {e}")
            return ToolResult(error=str(e))

    async def cleanup(self) -> None:
        """Handle cleanup if needed"""
        try:
            logger.info("Performing human input tool cleanup")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
