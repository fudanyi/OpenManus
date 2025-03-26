from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.tool import Terminate, ToolCollection
from app.tool.bash import Bash

# from app.tool.chart_visualization.chart_visualization import ChartVisualization
from app.tool.chart_visualization.data_analysis_python import DataAnalysisPythonExecute
from app.tool.chart_visualization.normal_python_execute import NormalPythonExecute
from app.tool.file_saver import FileSaver

# from app.tool.planning import PlanningTool
# from app.tool.python_execute import PythonExecute
from app.tool.str_replace_editor import StrReplaceEditor

# from app.tool.terminal import Terminal
from app.tool.web_search import WebSearch
from extensions.prompt.data_analyst import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from extensions.tool.data_source import DataSource
from extensions.tool.human_input import HumanInput


class DataAnalyst(ToolCallAgent):
    """
    A data analysis agent that uses planning to solve various data analysis tasks.

    This agent extends DataAnalysis with a comprehensive set of tools and capabilities,
    including Python execution, web search, chart visualization.
    """

    name: str = "DataAnalyst"
    description: str = (
        "An analytical agent that utilizes multiple tools to solve diverse data tasks"
    )

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Terminate(),
            HumanInput(),
            # PlanningTool(),
            NormalPythonExecute(),
            DataAnalysisPythonExecute(),
            # ChartVisualization(),
            DataSource(),
            WebSearch(),
            StrReplaceEditor(),
            FileSaver(),
            Bash(),
            # Terminal(),
        )
    )

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # Store original prompt
        original_prompt = self.next_step_prompt

        # Only check recent messages (last 3) for browser activity
        # recent_messages = self.memory.messages[-3:] if self.memory.messages else []
        # browser_in_use = any(
        #     "browser_use" in msg.content.lower()
        #     for msg in recent_messages
        #     if hasattr(msg, "content") and isinstance(msg.content, str)
        # )

        # if browser_in_use:
        #     # Override with browser-specific prompt temporarily to get browser context
        #     self.next_step_prompt = BROWSER_NEXT_STEP_PROMPT

        # Call parent's think method
        result = await super().think()

        # Restore original prompt
        self.next_step_prompt = original_prompt

        return result
