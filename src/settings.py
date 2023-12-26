import json
import os

import gspread

TIMEZONE = os.environ.get("TZ", "UTC")

CHANNELS = os.environ.get("CHANNELS", None)
CHANNELS = CHANNELS.split(",") if CHANNELS else []

EDIT_BUTTON_TEXT = os.environ.get("EDIT_BUTTON_TEXT", "Edit")

DAILY_MESSAGE_HOUR = os.environ.get("DAILY_MESSAGE_HOUR", 23)
DAILY_MESSAGE_MINUTE = os.environ.get("DAILY_MESSAGE_MINUTE", 0)
DAILY_MESSAGE_SECONDS = os.environ.get("DAILY_MESSAGE_SECONDS", 0)
DAILY_MESSAGE = os.environ.get("DAILY_MESAGE", "{date}\n\nHow was your day?")
DONE_MESSAGE = os.environ.get(
    "DONE_MESSAGE", "{date} was {button_label} ({button_description})"
)
MONTLY_PROGRESS_TEXT = os.environ.get(
    "MONTLY_PROGRESS_TEXT", "**Here's your year until now ({date})**"
)
VIEW_COMMAND_RESULT = os.environ.get(
    "VIEW_COMMAND_RESULT", "Here's your Year In Pixels for the year `{year}`"
)

BUTTONS = json.loads(
    os.environ.get(
        "BUTTONS",
        '[["😄","Very Happy","#ff6961"],["🙂","Happy","#ffb347"],["😐","Neutral","#fdfd96"],["🙁","Sad","#48d148"],["😞","Very Sad","#779ecb"]]',
    )
)

print(BUTTONS)

DEFAULT_COLOR = os.environ.get("DEFAULT_COLOR", "#d9d9d9")
MODEL_WORKSHEET_ID = os.environ.get("MODEL_WORKSHEET_ID", 0)

DATE_FRMT = os.environ.get("DATE_FRMT", "%d/%m/%Y")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

gc = gspread.service_account(filename="./data/credentials.json")


if BOT_TOKEN is None:
    raise ValueError("DISCORD_TOKEN not set")
if SPREADSHEET_ID is None:
    raise ValueError("SPREADSHEET_ID not set")
