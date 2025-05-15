import argparse
import asyncio
import csv
import json
import os
import time

import openpyxl

from app.config import WORKSPACE_ROOT
from app.flow.flow_factory import FlowFactory, FlowType
from app.logger import logger
from extensions.agent.data_analyst import DataAnalyst
from extensions.agent.planner import Planner
from extensions.agent.report_maker import ReportMaker
from extensions.output import Output
from extensions.session import (
    get_session_id,
    has_session,
    load_flow_from_session,
    save_flow_to_session,
)

SESSION_FOLDER = "sessions"
MAX_ATTACHMENT_LENGTH = 500
MIN_ATTACHMENT_LINE_COUNT = 3
MAX_ATTACHMENT_LINE_COUNT = 10


def read_attachment(file_path: str) -> str:
    """根据文件后缀名，读取附件文件头部内容

    如果文件不存在，则返回空字符串。
    如果文件是json格式，则返回json字符串。
    如果文件是txt格式，则返回txt的前300字内容。
    如果文件是md格式，则返回md的前300字内容。
    如果文件是csv格式，则返回csv的前30行内容，且保证总字数小于300字。

    Args:
        file_path: 文件路径

    Returns:
        文件内容字符串
    """
    try:
        if not os.path.exists(file_path):
            return ""

        file_content = ""
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                # 返回json字符串
                file_content = f.read()
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                # 返回txt的前300字内容
                file_content = f.read(MAX_ATTACHMENT_LENGTH)
        elif file_path.endswith(".md"):
            with open(file_path, "r", encoding="utf-8") as f:
                # 返回md的前300字内容
                file_content = f.read(MAX_ATTACHMENT_LENGTH)
        elif file_path.endswith(".csv"):
            csv_reader = csv.reader(open(file_path, "r", encoding="utf-8"))
            for i, row in enumerate(csv_reader):
                file_content += ",".join(row) + "\n"
                # 如果内容长度小于最大长度，或者行数小于2，则继续读取
                if len(file_content) <= MAX_ATTACHMENT_LENGTH or i < MIN_ATTACHMENT_LINE_COUNT:
                    continue
                else:
                    break
        elif file_path.endswith(".html"):
            with open(file_path, "r", encoding="utf-8") as f:
                # 返回html的内容
                file_content = f.read()
        elif file_path.endswith(".xlsx"):
            # 读取xlsx文件前30行内容
            workbook = openpyxl.load_workbook(file_path)
            sheet = workbook.active
            for row in sheet.iter_rows(max_row=MAX_ATTACHMENT_LINE_COUNT):
                # 将None值转换为空字符串
                file_content += (
                    ",".join(
                        [
                            str(cell.value) if cell.value is not None else ""
                            for cell in row
                        ]
                    )
                    + "\n"
                )
                if len(file_content) <= MAX_ATTACHMENT_LENGTH or i < MIN_ATTACHMENT_LINE_COUNT:
                    continue
                else:
                    break
        else:
            # 尝试当作文本文件读取一下，失败后为""
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read(MAX_ATTACHMENT_LENGTH)
            except Exception:
                file_content = ""

        if file_content:
            return file_path + ":\n" + file_content + "\n"
        else:
            return file_path + ":\nno preview\n"

    except Exception as e:
        logger.error(f"Failed to read attachment {file_path}: {str(e)}")
        return ""


def get_user_input():
    prompt = ""
    attachments = []
    attachments_content = ""
    input_json = input("Enter your prompt: ")

    # json格式，{"prompt":"xxxxx", "attachments":["xxx","bbb"]}
    try:
        # 先去掉外层的双引号
        input_str = input_json.strip('"')
        # 将Python字典字符串转换为JSON格式
        input_str = input_str.replace("'", '"').replace("None", "null")
        input_json = json.loads(input_str)
        prompt = (
            input_json["prompt"] if "prompt" in input_json else input_json["Prompt"]
        )
        attachments = (
            input_json["attachments"]
            if "attachments" in input_json
            else input_json.get("Attachments", [])
        )
    except Exception as e:
        logger.error(f"Invalid input: {str(e)}")
        prompt = str(input_json)  # 确保prompt是字符串
        attachments = []

    if attachments:
        for attachment in attachments:
            attachment_file = "attachments/" + attachment
            # 尝试读取文件内容
            attachment_content = read_attachment(attachment_file)
            if attachment_content:
                attachments_content += attachment_content

    if not isinstance(prompt, str) or not prompt.strip():
        logger.warning("Empty or invalid prompt provided.")
        Output.print(
            type="mainExited",
            text="Request processing exited",
        )
        exit(0)
    if prompt == "exit":
        logger.info("Exited")
        Output.print(
            type="mainExited",
            text="Request processing exited",
        )
        exit(0)

    Output.print(
        type="chat",
        text=f"{prompt}",
        data={
            "sender": "user",
            "message": prompt,
            "attachments": (
                [{"name": "attachments/" + attachment} for attachment in attachments]
                if attachments
                else []
            ),
        },
    )

    return prompt, attachments, attachments_content


async def run_flow(session_id: str):
    agents = {
        "dataAnalyst": DataAnalyst(),
        "reportMaker": ReportMaker(),
    }

    planningAgent = Planner()
    attachments_content = ""

    # Set session ID for output
    Output.set_session_id(session_id)

    try:
        Output.print(
            type="mainStart",
            text=f"Start session {session_id} under {WORKSPACE_ROOT}",
        )

        # 获取用户输入
        prompt, attachments, attachments_content = get_user_input()

        # 如果有session文件，则读取session文件创建flow
        if has_session(session_id):
            flow = load_flow_from_session(
                session_id, FlowType.PLANNING, agents, planningAgent
            )
        # 如果没有session文件，则创建flow
        else:
            flow = FlowFactory.create_flow(
                session_id=session_id,
                flow_type=FlowType.PLANNING,
                agents=agents,
                planningAgent=planningAgent,
            )

        try:
            start_time = time.time()
            if attachments_content:
                prompt += "\n以下是数据文件路径及数据内容的预览，进行分析时请参考：\n"
                prompt += attachments_content
                logger.info(f"prompt: {prompt}")

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
    finally:
        # 保存session
        save_flow_to_session(session_id, flow)


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
