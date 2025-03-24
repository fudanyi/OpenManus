from pydantic import Field

from app.agent.manus import Manus
from app.config import config
from app.prompt.browser import NEXT_STEP_PROMPT as BROWSER_NEXT_STEP_PROMPT
from extensions.prompt.data_analyst import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.bash import Bash
from extensions.tool.data_source import DataSource
from app.tool.file_saver import FileSaver
from app.tool.python_execute import PythonExecute
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.web_search import WebSearch


class DataAnalyst(Manus):
    """
    A specialized data analysis agent focused on handling datasets and generating insights.

    This agent extends BrowserAgent with tools for data processing, statistical analysis,
    visualization, and reporting to efficiently analyze datasets and extract valuable information.
    """

    name: str = "DataAnalyst"
    description: str = (
        "A specialized agent focused on data analysis, processing, and visualization"
    )

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(),
            WebSearch(),
            StrReplaceEditor(),
            FileSaver(),
            Bash(),
            DataSource(),
            Terminate(),
        )
    )

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # Store original prompt
        original_prompt = self.next_step_prompt

        # Only check recent messages (last 3) for browser activity
        recent_messages = self.memory.messages[-3:] if self.memory.messages else []
        browser_in_use = any(
            "browser_use" in msg.content.lower()
            for msg in recent_messages
            if hasattr(msg, "content") and isinstance(msg.content, str)
        )

        if browser_in_use:
            # Override with browser-specific prompt temporarily to get browser context
            self.next_step_prompt = BROWSER_NEXT_STEP_PROMPT

        # Call parent's think method
        result = await super().think()

        # Restore original prompt
        self.next_step_prompt = original_prompt

        return result
