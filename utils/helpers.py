"""
通用工具函数
"""
import asyncio
import hashlib
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


# 随机 User-Agent 池（Windows Chrome 各版本）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]

# 视口尺寸池（常见分辨率，带细微差异）
VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 720},
    {"width": 1440, "height": 820},
]


def get_random_user_agent() -> str:
    """随机返回一个 User-Agent"""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    """随机返回一个视口尺寸"""
    return random.choice(VIEWPORTS)


def load_config(config_path: str = "config.py") -> dict:
    """加载配置（从 config.py 模块导入）"""
    import importlib.util
    import sys

    path = Path(config_path).resolve()
    if not path.exists():
        # 尝试加载 config.local.py
        local_path = path.parent / "config.local.py"
        if local_path.exists():
            path = local_path
        else:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

    spec = importlib.util.spec_from_file_location("config", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["config"] = mod
    spec.loader.exec_module(mod)
    return mod


def generate_note_id(url: str) -> str:
    """根据 URL 生成唯一笔记 ID（用于去重）"""
    return hashlib.md5(url.encode()).hexdigest()


async def random_delay(min_sec: float = 3, max_sec: float = 8):
    """随机延迟，模拟人类行为（异步版本）"""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


def safe_get(data: dict, *keys, default=None):
    """安全地从嵌套字典中获取值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


def truncate_text(text: str, max_length: int = 500) -> str:
    """截断文本到指定长度"""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def format_date(dt: Optional[datetime] = None) -> str:
    """格式化为飞书可接受的日期字符串"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")


def parse_xhs_date(date_str: str) -> Optional[datetime]:
    """解析小红书的各种日期格式"""
    if not date_str:
        return None

    now = datetime.now()
    date_str = date_str.strip()

    # 分钟前 / 小时前
    if "分钟前" in date_str:
        minutes = int(date_str.replace("分钟前", ""))
        return now - timedelta(minutes=minutes)
    if "小时前" in date_str:
        hours = int(date_str.replace("小时前", ""))
        return now - timedelta(hours=hours)
    if "天前" in date_str:
        days = int(date_str.replace("天前", ""))
        return now - timedelta(days=days)

    # 格式: "2024-01-15"
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%Y年%m月%d日"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def retry_on_failure(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """重试装饰器"""
    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            wait = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(wait)
                        wait *= backoff
                    else:
                        raise last_exception
            return None
        return wrapper
    return decorator


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分割成指定大小的块"""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
