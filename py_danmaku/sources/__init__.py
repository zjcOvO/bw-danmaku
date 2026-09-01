"""Onebot, Bilibili, QQ 官方机器人 和 manual 数据源。"""

from .onebot_client import OnebotClient
from .manual_client import ManualDanmakuClient
from .qqbot_client import QQBotClient

__all__ = ["OnebotClient", "ManualDanmakuClient", "QQBotClient"]
