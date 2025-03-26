import asyncio
import time

from app.logger import logger
from app.flow.flow_factory import FlowFactory, FlowType
from extensions.agent.data_analyst import DataAnalyst
from extensions.output import Output


async def run_flow():
    agents = {
        "dataAnalyst": DataAnalyst(),
    }

    try:
        prompt = input("Enter your prompt: ")

        if prompt.strip().isspace() or not prompt:
            logger.warning("Empty prompt provided.")
            return

        if prompt == "exit":
            logger.info("Exited")
            Output.print(
                type="mainExited",
                text="Request processing exited",
            )
            return

        flow = FlowFactory.create_flow(
            flow_type=FlowType.PLANNING,
            agents=agents,
        )
        logger.warning("Processing your request...")

        Output.print(
            type="chat",
            text=f"{prompt}",
            data={
                "sender": "user",
                "message": prompt,
            },
        )

        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                flow.execute(prompt),
                timeout=3600,  # 60 minute timeout for the entire execution
            )
            elapsed_time = time.time() - start_time
            logger.info(f"Request processed in {elapsed_time:.2f} seconds")
            logger.info(result)

            Output.print(
                type="chat",
                text=f"{result}",
                data={
                    "sender": "assistant",
                    "message": result,
                },
            )

            Output.print(
                type="mainCompleted",
                text=f"Request processing completed in {elapsed_time:.2f} seconds.",
            )

        except asyncio.TimeoutError:
            logger.error("Request processing timed out after 1 hour")
            logger.info(
                "Operation terminated due to timeout. Please try a simpler request."
            )

            Output.print(
                type="mainTimeout",
                text="Operation terminated due to timeout. Please try a simpler request.",
            )

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")

        Output.print(
            type="mainInterrupted",
            text="Operation cancelled by user.",
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}")

        Output.print(
            type="mainError",
            text=f"Error: {str(e)}",
        )


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

                Output.print(
                    type="mainExited",
                    text="Request processing exited",
                )

                break

            logger.info(f"Processing your request:{prompt}")

            Output.print(
                type="chat",
                text=f"{prompt}",
                data={
                    "sender": "user",
                    "message": prompt,
                },
            )

            result = await agent.run(prompt)
            logger.info(f"Request processing completed.{result}")

            Output.print(
                type="chat",
                text=f"{result}",
                data={
                    "sender": "assistant",
                    "message": result,
                },
            )

            Output.print(
                type="mainCompleted",
                text="Request processing completed.",
            )

        except KeyboardInterrupt:
            logger.warning("Operation interrupted.")

            Output.print(
                type="mainInterrupted",
                text="Operation interrupted.",
            )

        except Exception as e:
            logger.error(f"Error: {str(e)}")

            Output.print(
                type="mainError",
                text=f"Error: {str(e)}",
            )


if __name__ == "__main__":
    # asyncio.run(main())
    asyncio.run(run_flow())
