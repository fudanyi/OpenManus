from app.logger import logger
from app.tool.base import BaseTool
from extensions.output import Output

_TERMINATE_DESCRIPTION = """Terminate current step or task:
1. when the request is met of current step 
2. if the assistant cannot proceed further with the task.
3. use ask for quitting
4. when you have finished all the tasks

"""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            },
            "target": {
                "type": "string",
                "description": "The target of termination.",
                "enum": ["step", "task"],
            },
        },
        "required": ["status", "target"],
    }

    async def execute(self, status: str, target: str) -> str:
        """Finish the current execution"""
        try:
            logger.info(f"Terminating interaction with status: {status}")

            # Output.print(
            #     type="terminate",
            #     text=f"Terminating interaction with status: {status}",
            #     data={"status": status},
            # )

            return f"The interaction has been completed with status: {status}"
        except Exception as e:
            logger.error(f"Error during termination: {e}")
            return f"The interaction encountered an error during termination: {e}"

    async def cleanup(self) -> None:
        """Handle cleanup if needed"""
        try:
            logger.info("Performing terminate tool cleanup")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
