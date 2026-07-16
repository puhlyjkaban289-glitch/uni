# -*- coding: utf-8 -*-
import io
import logging
import os
import sys

from PIL import Image
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart

from exif_utils import generate_exif

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("Íåò òîêåíà")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def apply_exif(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    exif_bytes = generate_exif()

    out = io.BytesIO()
    img.save(out, "JPEG", quality=95, exif=exif_bytes)

    return out.getvalue()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Îòïðàâü ôîòî")


@dp.message(F.photo | F.document)
async def handler(message: Message):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)

   import random

def get_random_coords():
    coords = []
    with open("coords.csv", encoding="utf-8") as f:
        for line in f:
            lat, lon = line.strip().split(",")
            coords.append((float(lat), float(lon)))
    return random.choice(coords)


lat, lon = get_random_coords()

result = apply_exif(buf.getvalue(), lat, lon)
    await message.answer_document(
        BufferedInputFile(result, filename="IMG_0001.JPG")
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
