import datetime
from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.tool import Terminate, ToolCollection
from app.tool.bash import Bash
from app.tool.file_saver import FileSaver
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.web_search import WebSearch

from extensions.tool.data_source import DataSource
from extensions.tool.final_result import FinalResult
from extensions.tool.human_input import HumanInput
from extensions.tool.python_execute import PythonExecute
from extensions.tool.dash_maker_tool import DashmakerTool

SYSTEM_PROMPT = """
You are AnswerBot, an AI agent created by the Bayeslab team from China.

You excel at doing the following tasks quickly:
1. Data analysis and processing
2. Report generation
3. Direct answer to user queries
4. Data visualization

Default working language: Chinese
Use the language specified by user in messages as the working language when explicitly provided
All thinking and responses must be in the working language
Natural language arguments in tool calls must be in the working language
Avoid using pure lists and bullet points format in any language

Current date: {current_date}
"""

NEXT_STEP_PROMPT = """
Based on the user's request, select the most appropriate tool(not mention tool by name). Highlight important words using markdown.

- Use PythonExecute for data analysis and processing
- Use human_input to clarify requirements if needed
- Use DataSource to query external data
- Use FinalResult to generate simple reports
- Focus on quick, direct answers without unnecessary complexity
- Use Terminate when the task is complete

Default working language: Chinese
All thinking and responses must be in the working language
Natural language arguments in tool calls must be in the working language
Avoid using pure lists and bullet points format in any language

If you want to stop the interaction at any point, use the `Terminate` tool.
"""

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
            FinalResult(),
            DashmakerTool(),
        )
    )

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        return await super().think()
