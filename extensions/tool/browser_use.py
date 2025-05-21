from browser_use import Agent
from langchain_openai import ChatOpenAI
from app.tool.base import BaseTool
from app.config import LLMSettings, config
from app.logger import logger
from extensions.prompt.browser import SYSTEM_PROMPT
from extensions.output import Output
import time
import csv

class BrowserUseTool(BaseTool):
    name: str = "browser_use"
    description: str = """Use the browser to complete the task.
    Use this tool when you need to complete a task that requires web browsing."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The task to be completed. This parameter specifies the exact task or query that the user wants to execute using the browser. The input should be clear and concise, allowing the AI system to understand the intent of the task. For example, it could involve searching for specific information on the web, interacting with a webpage, or extracting data from a website. While the input may be simple, providing additional context or details can help ensure the task is executed accurately and efficiently.",
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
        try:
          agent = Agent(
              task=f'{prompt}',
              llm=ChatOpenAI(
                  model=self.model,
                  base_url=self.base_url,
                  api_key=self.api_key,
              ),
              save_conversation_path="logs/conversation",
              use_vision=False,  # 若模型不支持图像输入则关闭
          )
          agent.message_manager.state.history.messages[0].message.content = SYSTEM_PROMPT
          browser_result = await agent.run()
          final_result = browser_result.final_result()
          # Output.print(
          #   type="browser_user_result",
          #   text=final_result,
          # )
          return final_result
        except Exception as e:
          return str(e)
    
    async def cleanup(self) -> None:
        """Handle cleanup if needed"""
        try:
            logger.info("Performing browser use tool cleanup")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
