import datetime
from extensions.tool.result_reporter import ResultReporter
from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.tool import Terminate, ToolCollection
from app.tool.bash import Bash
from app.tool.file_saver import FileSaver
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.web_search import WebSearch

from extensions.tool.data_source import DataSource
from extensions.tool.human_input import HumanInput
from extensions.tool.python_execute import PythonExecute
from extensions.tool.dash_maker_tool import DashmakerTool
from extensions.prompt.answerbot import SYSTEM_PROMPT, NEXT_STEP_PROMPT

class AnswerBot(ToolCallAgent):
    """
    A streamlined agent that combines essential tools from DataAnalyst and ReportMaker
    to provide quick, direct answers to user queries.
    """

    name: str = "AnswerBot"
    description: str = (
        "A streamlined agent that provides quick, direct answers to user queries"
    )

    system_prompt: str = SYSTEM_PROMPT.format(current_date=datetime.datetime.now().strftime("%Y-%m-%d"))
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 10  # Reduced from 20 to encourage quicker responses

    # Add essential tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Terminate(),
            HumanInput(),
            PythonExecute(),
            DataSource(),
            WebSearch(),
            StrReplaceEditor(),
            FileSaver(),
            Bash(),
            DashmakerTool(),
            ResultReporter(),
        )
    )

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        return await super().think()
