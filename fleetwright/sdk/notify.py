"""fleetwright/sdk/notify.py — pluggable notification sender.

Alerts from circuit breakers and the fleet engine route through here.
Out of the box: logs to stderr. Configure TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
for Telegram delivery.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def send_notification(text: str) -> None:
    """Send a notification. Logs at WARNING; optionally delivers via Telegram."""
    logger.warning("ALERT: %s", text)

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not (bot_token and chat_id):
        return

    try:
        import httpx
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as exc:
        logger.debug("telegram send failed: %s", exc)
