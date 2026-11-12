from __future__ import annotations

import os
from pathlib import Path
import requests
from dotenv import load_dotenv


def send_telegram(message: str) -> bool:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": message[:4000]}, timeout=15)
    r.raise_for_status()
    return True
