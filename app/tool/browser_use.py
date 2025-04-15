from browser_use import Agent
from langchain_openai import ChatOpenAI
from app.schema import AgentState
from app.tool.base import BaseTool, ToolResult
from app.config import LLMSettings, config


class BrowserUseTool(BaseTool):
    name: str = "browser_use"
    description: str = """Use the browser to complete the task.
    Use this tool when you need to complete a task that requires web browsing.
    The tool accepts a task description and executes it using a browser agent.
    The tool returns the result of the task as a string."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The task to be completed.",
            },
        },
        "required": ["prompt"],
    }
    llm_config: LLMSettings = config.llm.get('default', config.llm["default"])
    model: str = llm_config.model
    max_tokens: int = llm_config.max_tokens
    temperature: float = llm_config.temperature
    api_key: str = llm_config.api_key
    base_url: str = llm_config.base_url
    async def execute(self, prompt: str):
        from app.agent.browser import BrowserAgent
        agent = Agent(
            task=prompt,
            llm=ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
            ),
            use_vision=False,  # 若模型不支持图像输入则关闭
        )
        result = await agent.run()
        BrowserAgent.state = AgentState.FINISHED
        return ToolResult(output=result.final_result())
