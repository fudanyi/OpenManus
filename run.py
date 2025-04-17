import argparse
import asyncio
import time

from app.flow.flow_factory import FlowFactory, FlowType
from app.logger import logger
from extensions.agent.data_analyst import DataAnalyst
from extensions.agent.planner import Planner
from extensions.output import Output
from extensions.session import (
    get_session_id,
    has_session,
    load_flow_from_session,
    save_flow_to_session,
)

SESSION_FOLDER = "sessions"


async def run_flow(session_id: str):
    agents = {
        "dataAnalyst": DataAnalyst(),
    }

    planningAgent = Planner()

    # Set session ID for output
    Output.set_session_id(session_id)

    try:
        Output.print(
            type="mainStart",
            text=f"Start session {session_id}",
        )

        # 如果有session文件，则读取
        if has_session(session_id):
            prompt = ""
            flow = load_flow_from_session(session_id, FlowType.PLANNING, agents, planningAgent)
        # 如果没有session文件，则创建
        else:
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
            logger.warning("Processing your request...")

            Output.print(
                type="chat",
                text=f"{prompt}",
                data={
                    "sender": "user",
                    "message": prompt,
                },
            )

            flow = FlowFactory.create_flow(
                flow_type=FlowType.PLANNING,
                agents=agents,
                planningAgent=planningAgent,
            )

        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                flow.execute(prompt),
                timeout=3600,  # 60 minute timeout for the entire execution
            )
            elapsed_time = time.time() - start_time
            logger.info(result)
            logger.info(f"Request processed in {elapsed_time:.2f} seconds")

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
        finally:
            # 保存session
            save_flow_to_session(session_id, flow)

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
    # 获取参数sessionId
    parser = argparse.ArgumentParser(description="Run the application")
    parser.add_argument("--sid", type=str, help="Session ID")
    args = parser.parse_args()
    if args.sid:
        session_id = args.sid
    else:
        # session_id = "f4646819-1613-4e92-8661-bde26a6bdbec"
        session_id = get_session_id()

    # asyncio.run(main(session_id))
    asyncio.run(run_flow(session_id))
