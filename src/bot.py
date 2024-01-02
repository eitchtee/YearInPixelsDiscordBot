import datetime
import io
from string import ascii_uppercase
from zoneinfo import ZoneInfo
import logging

import aiohttp
import discord
from discord.ext import tasks, commands

from tinydb import TinyDB, Query
from tinydb.table import Document

import gspread
import gspread_formatting as gs_f
from gspread_formatting import (
    Color,
    TextFormat,
    CellFormat,
    Borders,
    Border,
    format_cell_range,
)

import fitz
from PIL import Image, ImageChops

import settings

get_logger = logging.getLogger()
logger = get_logger
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

formatter = logging.Formatter(
    "%(asctime)s :: %(levelname)s :: %(module)s :: %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)

db = TinyDB("data/db.json")
Q = Query()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix="!", log_handler=handler)
tree = bot.tree


def hex_to_unit_rgb(hex_color: str) -> [int, int, int]:
    # Remove the '#' character if present
    hex_color = hex_color.lstrip("#")

    # Convert the hex color to RGB
    r = round(int(hex_color[0:2], 16) / 255.0, 3)
    g = round(int(hex_color[2:4], 16) / 255.0, 3)
    b = round(int(hex_color[4:6], 16) / 255.0, 3)

    return r, g, b


def generate_table(year: int, worksheet: gspread.worksheet) -> gspread.worksheet:
    year = str(year)

    worksheet.update_acell("N24", year)

    for m in range(1, 13):
        for d in range(1, 33):
            try:
                datetime.datetime(year=int(year), day=d, month=m)
            except ValueError:
                starting_day = 1
                ending_day = d - 1
                column = ascii_uppercase[m]

                starting_row = str(starting_day + 1)
                ending_row = str(ending_day + 1)

                clabel_start = "{}{}".format(column, starting_row)
                clabel_end = "{}{}".format(column, ending_row)
                crange = "{}:{}".format(clabel_start, clabel_end)

                cell_format = CellFormat(
                    borders=Borders(
                        bottom=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                        top=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                        left=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                        right=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                    )
                )

                format_cell_range(worksheet, crange, cell_format)
                break

    return worksheet


def download(year: int = None):
    def trim_space(im, border):
        bg = Image.new(im.mode, im.size, border)
        diff = ImageChops.difference(im, bg)
        bbox = diff.getbbox()
        if bbox:
            return im.crop(bbox)

    if not year:  # current year
        year = datetime.date.today().year

    spreadsheet = settings.gc.open_by_key(settings.SPREADSHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(str(year))
    except Exception:
        raise Exception("Year not found")

    url = f"https://docs.google.com/spreadsheets/d/{settings.SPREADSHEET_ID}/export?format=pdf&gid={worksheet.id}"
    response = settings.gc.request(method="get", endpoint=url)

    if not response.ok:
        raise Exception("Error downloading image")

    img_byte_arr = io.BytesIO()

    with fitz.open(None, response.content, "pdf") as doc:
        page = doc.load_page(0)  # number of page
        pix = page.get_pixmap(dpi=600)

        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        image = trim_space(image, (255, 255, 255))
        image.save(img_byte_arr, format="PNG")

    img_byte_arr.seek(0)
    return img_byte_arr


class Date:
    def __init__(self, msg_id: int | None = None, date: datetime.date = None):
        self.msg_id: int | None = msg_id
        self.date: datetime.date | None = date if date else None
        self.formatted_date: str | None = (
            datetime.datetime.strftime(date, settings.DATE_FRMT) if date else None
        )

        self._answer = ""
        self.note = ""

        self._spreadsheet = None
        self._worksheet = None

        self.get_date()

    def get_date(self, new: bool = False) -> None:
        if self.msg_id and not new:
            msg_data = db.get(Q.msg_id == self.msg_id)

            if msg_data:
                if not isinstance(msg_data, Document):
                    msg_data = msg_data[0]

                self.formatted_date = msg_data["date"]
                self.date = datetime.datetime.strptime(
                    self.formatted_date, settings.DATE_FRMT
                )
                self.note = msg_data.get("note", "")
                self._answer = msg_data.get("answer", "")
            else:
                self.get_date(new=True)

        else:
            self.date = self.date if self.date else datetime.date.today()
            self.formatted_date = datetime.datetime.strftime(
                self.date, settings.DATE_FRMT
            )

    def save(self) -> None:
        db.upsert(
            {
                "msg_id": self.msg_id,
                "date": self.formatted_date,
                "answer": self._answer,
                "note": self.note,
            },
            Q.msg_id == self.msg_id,
        )

    def add_cell_note(self, note: str):
        self.note = note

        cell_label, cell_range = self.sheet_range

        self.worksheet.insert_note(cell=cell_label, content=note)

        self.save()

    def answer(self, answer: str):
        self._answer = answer

        cell_label, cell_range = self.sheet_range
        options = {x[1]: x[2] for x in settings.BUTTONS}
        color = gs_f.Color(
            *hex_to_unit_rgb(options.get(answer, settings.DEFAULT_COLOR))
        )

        cell_format = CellFormat(
            backgroundColor=color,
            textFormat=TextFormat(foregroundColor=color),
            wrapStrategy="CLIP",
            borders=Borders(
                bottom=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                top=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                left=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
                right=Border("SOLID", Color(0.40062, 0.40062, 0.40062)),
            ),
        )
        self.worksheet.update_acell(cell_label, answer)
        format_cell_range(self.worksheet, cell_range, cell_format)

        self.save()

    @property
    def worksheet(self):
        if not self._spreadsheet and not self._worksheet:
            self._spreadsheet = settings.gc.open_by_key(settings.SPREADSHEET_ID)
            try:
                self._worksheet = self._spreadsheet.worksheet(str(self.date.year))
            except gspread.exceptions.WorksheetNotFound:
                new_index = len(self._spreadsheet.worksheets())
                new_worksheet = self._spreadsheet.duplicate_sheet(
                    source_sheet_id=settings.MODEL_WORKSHEET_ID,
                    insert_sheet_index=0,
                    new_sheet_id=new_index,
                    new_sheet_name=str(self.date.year),
                )
                self._worksheet = generate_table(
                    year=self.date.year, worksheet=new_worksheet
                )

        return self._worksheet

    @property
    def daily_question_text(self) -> str:
        return settings.DAILY_MESSAGE.format(date=self.formatted_date)

    def get_done_text(self, button: discord.ui.Button = None) -> str:
        if button:
            button_label = button.emoji if button.emoji else button.label
            button_description = button.custom_id
        else:
            button_label = {x[1]: x[0] for x in settings.BUTTONS}.get(self._answer, "❔")
            button_description = self._answer

        if self.note:
            return (
                settings.DONE_MESSAGE.format(
                    date=self.formatted_date,
                    button_label=button_label,
                    button_description=button_description,
                )
                + f"\n\n📝 _{self.note}_"
            )
        else:
            return settings.DONE_MESSAGE.format(
                date=self.formatted_date,
                button_label=button_label,
                button_description=button_description,
            )

    @property
    def sheet_range(self) -> (str, str):
        # Translate current month to it's appropriate column on the worksheet
        column = ascii_uppercase[self.date.month]

        # Translate current day to it's appropriate row on the worksheet
        # Row = Current day + 1
        row = str(int(self.date.day) + 1)

        cell = "{}{}".format(column, row)
        cell_range = "{}:{}".format(cell, cell)
        return cell, cell_range


class SentimentButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        date = Date(msg_id=interaction.message.id)

        await interaction.response.defer()
        await interaction.message.edit(content="⌛", view=None)

        try:
            date.answer(answer=self.custom_id)
        except Exception as err:
            logger.exception("Error when answering Daily Question")

            await interaction.followup.send(
                f"🚨 Err\n\n```{err}```",
                view=AnsweredDailyQuestionView(),
            )
        else:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                content=date.get_done_text(button=self),
                view=AnsweredDailyQuestionView(),
            )


class DailyQuestionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        for emoji, description, color in settings.BUTTONS:
            if not description or not color:
                continue

            button = SentimentButton(
                label=description, custom_id=description, emoji=emoji
            )
            self.add_item(button)


class NoteModal(discord.ui.Modal, title=settings.NOTE_MODAL_TITLE):
    note = discord.ui.TextInput(
        label=settings.NOTE_MODAL_LABEL,
        style=discord.TextStyle.long,
        placeholder=settings.NOTE_MODAL_PLACEHOLDER,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        date = Date(msg_id=interaction.message.id)
        date.add_cell_note(note=self.note.value)

        await interaction.followup.edit_message(
            message_id=interaction.message.id,
            content=date.get_done_text(),
            view=AnsweredDailyQuestionView(),
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"🚨 Err!\n\n```{error}```", ephemeral=True
            )
        else:
            await interaction.followup.send(f"🚨 Err!\n\n```{error}```", ephemeral=True)

        logger.exception("Error when adding note")


class AnsweredDailyQuestionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label=settings.NOTE_BUTTON_TEXT,
        style=discord.ButtonStyle.green,
        custom_id="note",
    )
    async def note(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NoteModal())

    @discord.ui.button(
        label=settings.EDIT_BUTTON_TEXT,
        style=discord.ButtonStyle.danger,
        custom_id="change",
    )
    async def change(self, interaction: discord.Interaction, button: discord.ui.Button):
        date = Date(msg_id=interaction.message.id)

        await interaction.response.edit_message(
            content=date.daily_question_text,
            view=DailyQuestionView(),
        )


@bot.event
async def on_ready():
    logger.info(f"We have logged in as {bot.user}")
    daily_question.start()
    monthly_progress.start()

    if settings.PING:
        ping.start()
    bot.add_view(DailyQuestionView())
    bot.add_view(AnsweredDailyQuestionView())
    await bot.tree.sync()


@tree.command(name="view", description="Display the image for a given year")
async def view_year(
    interaction: discord.Interaction, year: int = datetime.date.today().year
):
    await interaction.response.defer()
    try:
        image = download(year=year)
    except Exception as err:
        logger.exception("Error when downloading image")

        await interaction.followup.send(f"🚨 Err!\n\n```{err}```")
    else:
        await interaction.followup.send(
            settings.VIEW_COMMAND_RESULT.format(year=year),
            file=discord.File(image, filename="YearInPixels.png"),
        )


@tree.command(name="ask", description="Re-ask a date")
async def ask(interaction: discord.Interaction, date: str):
    await interaction.response.defer()
    try:
        date = datetime.datetime.strptime(date, settings.DATE_FRMT).date()
        date = Date(date=date)
    except Exception as err:
        logger.exception("Error when interpreting date for Ask command")

        await interaction.followup.send(f"🚨 Err!\n\n```{err}```")
    else:
        view = DailyQuestionView()
        msg = await interaction.followup.send(
            date.daily_question_text,
            view=view,
        )
        date.msg_id = msg.id
        date.save()


@tasks.loop(
    time=datetime.time(
        hour=settings.DAILY_MESSAGE_HOUR,
        minute=settings.DAILY_MESSAGE_MINUTE,
        second=settings.DAILY_MESSAGE_SECONDS,
        tzinfo=ZoneInfo(settings.TIMEZONE),
    )
)
async def daily_question():
    view = DailyQuestionView()
    for channel_id in settings.CHANNELS:
        try:
            channel = bot.get_channel(channel_id)
            date = Date()
            msg = await channel.send(date.daily_question_text, view=view)
            date.msg_id = msg.id
            date.save()
        except AttributeError:
            logger.exception("Error when sending message to channel")

            continue


@tasks.loop(
    time=datetime.time(
        hour=9,
        minute=0,
        second=0,
        tzinfo=ZoneInfo(settings.TIMEZONE),
    )
)
async def monthly_progress():
    date = Date()
    if date.date.day == 1:
        if date.date.month == 1:
            year = date.date.year - 1
        else:
            year = date.date.year

        image = download(year=year)
        for channel_id in settings.CHANNELS:
            try:
                channel = bot.get_channel(channel_id)
                await channel.send(
                    settings.MONTLY_PROGRESS_TEXT.format(date=date.formatted_date),
                    file=discord.File(image, filename="YearInPixels.png"),
                )
            except AttributeError:
                logger.exception("Error when sending message to channel")
                continue


@tasks.loop(seconds=550)
async def ping():
    logger.info("Pinging")
    uptime_kuma_url = settings.PING_URL

    async with aiohttp.ClientSession() as session:
        async with session.get(uptime_kuma_url) as r:
            pass


bot.run(settings.BOT_TOKEN)
