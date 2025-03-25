import asyncio

from app.logger import logger
from extensions.agent.data_analyst import DataAnalyst


async def main():
    agent = DataAnalyst()
    while True:
        try:
            prompt = input("Enter your prompt: ")
            if not prompt.strip():
                logger.warning("Empty prompt provided.")
                continue
            if prompt == "exit":
                logger.warning("Exiting...")
                break

            logger.info(f"Processing your request:{prompt}")
            await agent.run(prompt)
            logger.info("Request processing completed.")
        except KeyboardInterrupt:
            logger.warning("Operation interrupted.")


if __name__ == "__main__":
    asyncio.run(main())
