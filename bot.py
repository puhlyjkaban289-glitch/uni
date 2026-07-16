import os
import logging
import random
from io import BytesIO

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

from PIL import Image

from exif_utils import generate_exif

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN not set")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


def get_random_coords():
    coords = []
    with open("coords.csv", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lat, lon = line.strip().split(",")
                coords.append((float(lat), float(lon)))
    return random.choice(coords)


def apply_exif(image_bytes, lat, lon):
    image = Image.open(BytesIO(image_bytes))

    exif_bytes = generate_exif(lat, lon)

    output = BytesIO()
    image.save(output, format="JPEG", exif=exif_bytes)

    return output.getvalue()


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Send photo")


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    downloaded = await bot.download_file(file.file_path)

    image_bytes = downloaded.read()

    lat, lon = get_random_coords()

    result = apply_exif(image_bytes, lat, lon)

    await message.answer_photo(result)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
