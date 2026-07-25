"""
日志配置模块
"""
import sys
from pathlib import Path
from loguru import logger

# 移除默认 handler
logger.remove()

# 日志文件路径
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 控制台输出
console_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
logger.add(
    sys.stderr,
    format=console_format,
    level="INFO",
    enqueue=True,
)

# 文件输出 - 每日轮转
logger.add(
    log_dir / "xhs_hunter_{time:YYYY-MM-DD}.log",
    rotation="00:00",       # 每日零点轮转
    retention="30 days",    # 保留 30 天
    compression="gz",       # 压缩旧日志
    level="DEBUG",
    encoding="utf-8",
    enqueue=True,
)

# 错误日志单独文件
logger.add(
    log_dir / "error_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="ERROR",
    encoding="utf-8",
    enqueue=True,
)

__all__ = ["logger"]
