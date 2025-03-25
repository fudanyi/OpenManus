import asyncio

from app.logger import logger
from extensions.agent.data_analyst import DataAnalyst
from extensions.output import Output


async def main():
    agent = DataAnalyst()
    while True:
        try:
            prompt = input("Enter your prompt: ")
            if not prompt.strip():
                logger.warning("Empty prompt provided.")
                continue
            if prompt == "exit":
                logger.info("Exited")
                Output.print(type="main_exit", text="Exited")
                break

            logger.info(f"Processing your request:{prompt}")
            Output.print(
                type="main_start",
                text=f"Processing your request:{prompt}",
                data={"prompt": prompt},
            )
            await agent.run(prompt)
            logger.info("Request processing completed.")
            Output.print(type="main_terminate", text="Request processing completed.")
        except KeyboardInterrupt:
            logger.warning("Operation interrupted.")
            Output.print(type="terminate", text="Operation interrupted.")


if __name__ == "__main__":
    asyncio.run(main())
