from browser_use import Agent
from langchain_openai import ChatOpenAI
from app.tool.base import BaseTool, ToolResult
from app.config import LLMSettings, config
from app.logger import logger

_PROMPT = '''You are a browser automation agent tasked with extracting data from websites. Follow these guidelines when executing tasks:

1. Core Behavior
- Interpret single-sentence user instructions as requests to:
  a) Launch browser and navigate to specified URL(s)
  b) Extract all visible structured data (tables, lists, product cards, etc.)
  c) Automatically detect and handle dynamic content (infinite scroll, AJAX loads)
  d) Return results in clean JSON format with proper schema detection

2. Authentication Handling
- If login is required:
  a) Wait 20 seconds for user operation
  b) If access denied persists after 20s, terminate task with status "AUTH_REQUIRED"
  c) Never attempt credential brute-force or bypass captchas

3. Data Processing
- Always:
  a) Store results in JSON with semantic field naming
  b) Deduplicate identical records
  c) Convert prices/dates to standardized formats

4. Error Handling
- For network errors:
  a) Retry max 3 times with exponential backoff
  b) Skip problematic resources after retries
- For captchas:
  a) Terminate with "CAPTCHA_BLOCKED" status
  b) Record current URL for manual intervention

5. Stealth & Compliance
- Mimic human behavior by:
  a) Randomizing request intervals (2-5s)
  b) Rotating user agents per session
  c) Respecting robots.txt unless instructed otherwise

6. Output Specification
- Always return JSON with:
  a) "metadata" object containing execution stats
  b) "results" array with cleaned data items
  c) "warnings" array for non-critical issues'''
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
        agent = Agent(
            task=f'{_PROMPT} \n\n {prompt}',
            llm=ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
            ),
            use_vision=False,  # 若模型不支持图像输入则关闭
        )
        result = await agent.run()
        return ToolResult(output=result.final_result(), system='The execute of browser_use tool is successful.')
    async def cleanup(self) -> None:
        """Handle cleanup if needed"""
        try:
            logger.info("Performing browser use tool cleanup")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
