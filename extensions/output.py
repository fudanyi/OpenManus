import json
import sys
import time
from typing import Any
import uuid
from datetime import datetime
from app.logger import logger
from app.config import PROJECT_ROOT


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            # 对于有__dict__属性的对象，只序列化其__dict__
            return obj.__dict__
        return super().default(obj)


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

    # Class variable to store current session ID
    _current_session_id = None

    @classmethod
    def set_session_id(cls, session_id: str):
        """
        Set the current session ID for output
        """
        cls._current_session_id = session_id
        # Ensure sessions directory exists
        sessions_path = PROJECT_ROOT / "sessions"
        sessions_path.mkdir(exist_ok=True)

    @classmethod
    def print(self, type: str, text: str, data: dict = None):
        """
        打印消息到控制台
        """
        output = self._pack(type, text, data)
        logger.info(output)
        output_str = json.dumps(output, cls=CustomJSONEncoder)
        print(output_str, flush=True)

        # 写入文件到 logs/{datetime}.output
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y%m%d")
        log_path = PROJECT_ROOT / "logs"
        log_path.mkdir(exist_ok=True)
        with open(log_path / f"{formatted_date}.output", "a", encoding="utf-8") as f:
            try:
                f.write(output_str + ",\n")
            except Exception:
                # logger.error(f"Error writing to output file: {e}")
                pass

        # 如果设置了session_id，同时写入到sessions/{session_id}.out
        if self._current_session_id:
            sessions_path = PROJECT_ROOT / "sessions"
            with open(sessions_path / f"{self._current_session_id}.out", "a", encoding="utf-8") as f:
                try:
                    f.write(output_str + ",\n")
                except Exception:
                    # logger.error(f"Error writing to session file: {e}")
                    pass

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
