import asyncio
import logging
import random
from io import BytesIO

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ContentType

from PIL import Image
from exif_utils import generate_exif

API_TOKEN = "YOUR_BOT_TOKEN"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


def get_random_coords():
    coords = []
    with open("coords.csv", encoding="utf-8") as f:
        for line in f:
            lat, lon = line.strip().split(",")
            coords.append((float(lat), float(lon)))
    return random.choice(coords)


def apply_exif(image_bytes, lat, lon):
    import piexif

    image = Image.open(BytesIO(image_bytes))

    exif_bytes = generate_exif(lat, lon)

    output = BytesIO()
    image.save(output, format="JPEG", exif=exif_bytes)

    return output.getvalue()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Send photo")


@dp.message(lambda message: message.content_type == ContentType.PHOTO)
async def handler(message: Message):
    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    downloaded = await bot.download_file(file.file_path)

    image_bytes = downloaded.read()

    lat, lon = get_random_coords()

    result = apply_exif(image_bytes, lat, lon)

    await message.answer_photo(result)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
