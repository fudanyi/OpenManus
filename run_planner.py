import argparse
import asyncio
import time

from app.logger import logger
from extensions.agent.planner import Planner
from extensions.output import Output
from extensions.session import (
    get_session_id,
    has_session,
    load_flow_from_session,
    save_flow_to_session,
)

SESSION_FOLDER = "sessions"

async def run_planner(session_id: str, task: str):
    # Initialize the Planner agent
    planner = Planner()

    # Set session ID for output
    Output.set_session_id(session_id)

    try:
        Output.print(
            type="mainStart",
            text=f"Starting planning session {session_id}",
        )

        # Run the planner
        await planner.run(task)

        Output.print(
            type="mainEnd",
            text=f"Planning session {session_id} completed",
        )

    except Exception as e:
        logger.error(f"Error in planning session {session_id}: {str(e)}")
        raise

async def main():
    parser = argparse.ArgumentParser(description="Run the Planner agent")
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID to use (optional)",
    )
    parser.add_argument(
        "--task",
        type=str,
        required=True,
        help="The task to plan for (required)",
    )
    args = parser.parse_args()

    # Get or create session ID
    session_id = args.session if args.session else get_session_id()

    # Run the planner with the task
    await run_planner(session_id, args.task)

if __name__ == "__main__":
    asyncio.run(main()) 