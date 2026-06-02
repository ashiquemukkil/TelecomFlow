import asyncio
import logging
import time
from typing import Optional


async def get_answer(query: str, history: list, conv_id: str,user_data: dict) -> str:
    user_data = user_data or {}
    