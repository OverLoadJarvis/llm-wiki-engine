"""日志配置模块

提供统一的日志记录能力，所有模块通过 ``get_logger(__name__)`` 获取 logger 实例。

Usage:
    from tools.logger import get_logger, setup_logging

    setup_logging(level="INFO")          # 在入口处配置一次
    logger = get_logger(__name__)        # 在各模块中获取 logger
    logger.info("something happened")
"""

import logging
import sys
from pathlib import Path

_logging_initialized: bool = False


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str | None = None,
) -> None:
    """初始化全局日志配置（仅执行一次）。

    Args:
        level: 日志级别，默认 ``"INFO"``
        log_file: 日志文件路径，为 ``None`` 时仅输出到控制台
        log_format: 自定义日志格式，默认带时间戳 / 级别 / 模块名
    """
    global _logging_initialized
    if _logging_initialized:
        return

    if log_format is None:
        log_format = "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s"

    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # 根 logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # 文件 handler（可选）
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _logging_initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger 实例。

    等价于 ``logging.getLogger(name)``，但明确表达了意图。

    Args:
        name: logger 名称，通常传入 ``__name__``

    Returns:
        :class:`logging.Logger` 实例
    """
    return logging.getLogger(name)