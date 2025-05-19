import os
import json
import csv
import openpyxl
import xlrd

from app.logger import logger

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
            # 尝试不同的编码方式读取文件
            encodings = ["utf-8", "gbk", "gb2312", "gb18030"]
            file_content = ""

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        csv_reader = csv.reader(f)
                        for i, row in enumerate(csv_reader):
                            file_content += ",".join(row) + "\n"
                            # 如果内容长度小于最大长度，或者行数小于2，则继续读取
                            if (
                                len(file_content) <= MAX_ATTACHMENT_LENGTH
                                or i < MIN_ATTACHMENT_LINE_COUNT
                            ):
                                continue
                            else:
                                break
                    # 如果成功读取，跳出编码尝试循环
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"读取文件 {file_path} 时发生错误: {str(e)}")
                    raise
        elif file_path.endswith(".html"):
            with open(file_path, "r", encoding="utf-8") as f:
                # 返回html的内容
                file_content = f.read()
        elif file_path.endswith(".xlsx"):
            # 读取xlsx文件前30行内容
            workbook = openpyxl.load_workbook(file_path)
            sheet = workbook.active
            for i, row in enumerate(sheet.iter_rows(max_row=MAX_ATTACHMENT_LINE_COUNT)):
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
                if (
                    len(file_content) <= MAX_ATTACHMENT_LENGTH
                    or i < MIN_ATTACHMENT_LINE_COUNT
                ):
                    continue
                else:
                    break
        elif file_path.endswith(".xls"):
            # 读取xls文件前30行内容
            workbook = xlrd.open_workbook(file_path)
            sheet = workbook.sheet_by_index(0)
            for i in range(min(sheet.nrows, MAX_ATTACHMENT_LINE_COUNT)):
                row_values = []
                for j in range(sheet.ncols):
                    cell_value = sheet.cell_value(i, j)
                    row_values.append(str(cell_value) if cell_value is not None else "")
                file_content += ",".join(row_values) + "\n"
                if (
                    len(file_content) <= MAX_ATTACHMENT_LENGTH
                    or i < MIN_ATTACHMENT_LINE_COUNT
                ):
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
            return "- " + file_path + ":\n" + file_content + "\n"
        else:
            return "- " + file_path + ":\nno preview\n"

    except Exception as e:
        logger.error(f"Failed to read attachment {file_path}: {str(e)}")
        return "- " + file_path + ":\nno preview\n"


def get_user_input(input_prompt: str):
    prompt = ""
    attachments = []
    attachments_content = ""
    prompt_with_attachments = ""
    input_json = input(input_prompt)

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
        prompt_with_attachments = prompt
    except Exception as e:
        logger.error(f"Invalid input: {str(e)}")
        prompt = str(input_json)  # 确保prompt是字符串
        attachments = []
        prompt_with_attachments = prompt

    if attachments:
        for attachment in attachments:
            attachment_file = "attachments/" + attachment
            # 尝试读取文件内容
            attachment_content = read_attachment(attachment_file)
            if attachment_content:
                attachments_content += attachment_content

    if attachments_content:
        prompt_with_attachments += (
            "\n以下是数据文件路径及数据内容的头部预览。预览内容仅供参考，进行分析时请先读取文件实际内容：\n"
        )
        prompt_with_attachments += attachments_content
        logger.info(f"prompt_with_attachments: {prompt_with_attachments}")

    return prompt, attachments, prompt_with_attachments
