import json
import time
import uuid
from datetime import datetime
from app.logger import logger
from app.config import PROJECT_ROOT


class Output:
    """
    工具类，功能为把接收到的内容包装成一个json对象，打印到控制台
    json对象的格式为：
    {
        "id": "WVtTAh79ZBKxNaGylg3FGR",
        "type": "liveStatus",
        "timestamp": 1740988422974,
        "text": "Updating plan"
        "data": {
            ...
        }
    }
    id: 唯一标识符，由大小写字母与数字组成随机字符串
    type: 消息类型，决定data的格式
    timestamp: 时间戳，当前时间
    text: 消息内容，用于打印到控制台
    data: 消息数据，用于存储实际数据
    """

    @classmethod
    def print(self, type: str, text: str, data: dict = None):
        """
        打印消息到控制台
        """
        output = self._pack(type, text, data)
        logger.info(output)
        print(output)

        # 同时写入文件到 logs/{datetime}.output
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y%m%d")
        log_path = PROJECT_ROOT / "logs"
        log_path.mkdir(exist_ok=True)
        with open(log_path / f"{formatted_date}.output", "a", encoding="utf-8") as f:
            f.write(json.dumps(output, ensure_ascii=False, indent=4) + "\n")

    @classmethod
    def _pack(self, type: str, text: str, data: dict = None):
        """
        包装消息
        """
        return {
            "id": str(uuid.uuid4()),
            "type": type,
            "timestamp": int(time.time() * 1000),
            "text": text,
            "data": data,
        }
