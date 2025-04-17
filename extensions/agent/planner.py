import os
from typing import Optional, Union

from app.tool.planning import PlanningTool
from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.tool import Terminate, ToolCollection
from app.tool.bash import Bash
from app.tool.file_saver import FileSaver
from app.tool.pwsh import Powershell
from app.tool.str_replace_editor import StrReplaceEditor

# from app.tool.terminal import Terminal
from app.tool.web_search import WebSearch
from extensions.prompt.data_analyst import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from extensions.tool.data_source import DataSource
from extensions.tool.final_result import FinalResult
from extensions.tool.human_input import HumanInput

# from app.tool.planning import PlanningTool
from extensions.tool.python_execute import PythonExecute


class Planner(ToolCallAgent):
    """
    A planning agent that focus on creating a plan for a given task.
    """

    name: str = "Planner"
    description: str = (
        "An planning assistant that focus on creating a plan for a given task"
    )

    system_prompt: str = (
        "You are a friendly and efficient planning assistant. Create a concise, actionable plan with clear steps. "
        "Do not overthink for simple tasks. "
        "Focus on key milestones rather than detailed sub-steps. "
        "Optimize for clarity and efficiency. "
        "Default working language: Chinese. "
        "Use the language specified by user in messages as the working language when explicitly provided. "
        "All thinking and responses must be in the working language"
        "Natural language arguments in tool calls must be in the working language"
        "Avoid using pure lists and bullet points format in any language"
    )

    next_step_prompt: str = """
Determine if you have enough information to create a plan for the given task. If you do not have enough information, ask for more information only when absolutely needed. 
Do not output thinking.

If you have enough information, create a plan for the given task. Ask for user confirmation aftering creating the plan.
If user have no futher comments, terminate this step.
"""

    max_observe: int = 10000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Terminate(),
            HumanInput(),
            PlanningTool(),
        )
    )

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # Store original prompt
        original_prompt = self.next_step_prompt

        # Call parent's think method
        result = await super().think()

        # Restore original prompt
        self.next_step_prompt = original_prompt

        return result

