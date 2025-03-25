import sys
from datetime import datetime
from loguru import logger as loguru_logger

from app.config import PROJECT_ROOT


class Logger:
    _instance = None
    _initialized = False
    _logger = None

    def __init__(self):
        if not self._initialized:
            self._print_level = "INFO"
            self._logfile_level = "DEBUG"
            self._current_log_file = None
            self._logger = loguru_logger
            self._initialize_logger()
            Logger._initialized = True

    def _initialize_logger(
        self, print_level="INFO", logfile_level="DEBUG", name: str = None
    ):
        """Adjust the log level and create a new log file if needed"""
        self._print_level = print_level
        self._logfile_level = logfile_level

        # Remove existing handlers
        self._logger.remove()

        # Add console handler
        self._logger.add(sys.stderr, level=print_level)

        # Create new log file if needed
        if self._current_log_file is None:
            current_date = datetime.now()
            formatted_date = current_date.strftime("%Y%m%d")
            log_name = f"{name}_{formatted_date}" if name else formatted_date
            log_path = PROJECT_ROOT / "logs"
            log_path.mkdir(exist_ok=True)
            self._current_log_file = log_path / f"{log_name}.log"
            self._logger.add(self._current_log_file, level=logfile_level)

    @classmethod
    def get_instance(self):
        if self._instance is None:
            self._instance = Logger()
        return self._instance

    @classmethod
    def get_logger(self):
        """Get the configured logger instance"""
        return self.get_instance()._logger
