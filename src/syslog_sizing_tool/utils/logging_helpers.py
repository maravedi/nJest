from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in (
                "args",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelno",
                "levelname",
                "lineno",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            ):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def get_json_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger
