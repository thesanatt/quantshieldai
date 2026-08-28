import os
import smtplib
from email.mime.text import MIMEText

import requests
from dotenv import load_dotenv

from quantshield.utils import log

SENSITIVE_PATTERNS = (
    'API_KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'ALPACA',
    'ZERODHA', 'WEBHOOK_URL', 'SMTP_PASSWORD', 'SMTP_EMAIL',
)
LEVEL_PREFIX = {'warning': 'WARNING: ', 'emergency': 'EMERGENCY: '}


def _sanitize(message: str) -> str:
    upper = message.upper()
    if '=' in message and any(pat in upper for pat in SENSITIVE_PATTERNS):
        return "[REDACTED: message contained sensitive data]"
    return message


def send_discord(message: str) -> bool:
    url = os.environ.get('DISCORD_WEBHOOK_URL', '')
    if not url:
        return False
    try:
        resp = requests.post(url, json={'content': _sanitize(message)}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception:
        return False


def send_email(message: str, subject: str = "Quant Engine Alert") -> bool:
    smtp_email = os.environ.get('SMTP_EMAIL', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    smtp_to = os.environ.get('SMTP_TO', '')
    if not smtp_email or not smtp_password or not smtp_to:
        return False
    try:
        msg = MIMEText(_sanitize(message))
        msg['Subject'] = subject
        msg['From'] = smtp_email
        msg['To'] = smtp_to
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, smtp_to, msg.as_string())
        return True
    except Exception:
        return False


def send_pushover(message: str, title: str = "Quant Engine") -> bool:
    user_key = os.environ.get('PUSHOVER_USER_KEY', '')
    app_token = os.environ.get('PUSHOVER_APP_TOKEN', '')
    if not user_key or not app_token:
        return False
    try:
        resp = requests.post('https://api.pushover.net/1/messages.json', data={
            'token': app_token,
            'user': user_key,
            'message': _sanitize(message),
            'title': title,
        }, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def notify(message: str, level: str = 'info') -> bool:
    load_dotenv()
    full = f"{LEVEL_PREFIX.get(level, '')}{message}"
    log(f"{level}: {full[:200]}", 'notify')
    if send_discord(full):
        return True
    if send_email(full, subject=f"[{level.upper()}] Quant Engine"):
        return True
    return send_pushover(full)


def format_emergency(trigger_data: dict) -> str:
    lines = ["CRASH ALERT"]
    if trigger_data.get('us_vix') is not None:
        lines.append(f"US VIX: {trigger_data['us_vix']}")
    if trigger_data.get('india_vix') is not None:
        lines.append(f"India VIX: {trigger_data['india_vix']}")
    lines.extend(f"- {t}" for t in trigger_data.get('triggers', []))
    affected = trigger_data.get('affected_tickers', [])
    if affected:
        lines.append(f"Affected: {', '.join(affected)}")
    return '\n'.join(lines)
