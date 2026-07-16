import io
import logging
import os
import random
import sys
import csv
from datetime import datetime, timedelta

from PIL import Image, ImageEnhance, ImageOps
import numpy as np
import piexif

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN не задан")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== КООРДИНАТЫ ==================

def load_coords(path="coords.csv"):
    coords = []

    if not os.path.exists(path):
        logging.warning("⚠ coords.csv не найден, используем fallback")
        return [(55.7558, 37.6173), (40.7128, -74.0060)]

    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                coords.append((float(row["lat"]), float(row["lon"])))
    except Exception as e:
        logging.error(f"Ошибка чтения coords: {e}")
        return [(55.7558, 37.6173)]

    if not coords:
        return [(55.7558, 37.6173)]

    return coords


COORDS = load_coords()


# ================== УСТРОЙСТВА ==================

DEVICES = [
    ("Apple", "iPhone 13", 26),
    ("Apple", "iPhone 14 Pro", 24),
    ("samsung", "SM-S911B", 24),
    ("Xiaomi", "Mi 11", 27),
]


# ================== UTILS ==================

def to_deg(value):
    abs_value = abs(value)
    deg = int(abs_value)
    minutes = int((abs_value - deg) * 60)
    seconds = int((((abs_value - deg) * 60) - minutes) * 60 * 100)

    return ((deg, 1), (minutes, 1), (seconds, 100))


def random_datetime():
    dt = datetime.now() - timedelta(days=random.randint(0, 365))
    return dt.strftime("%Y:%m:%d %H:%M:%S")


# ================== EXIF ==================

def create_exif(lat, lon):
    make, model, focal = random.choice(DEVICES)
    dt = random_datetime()

    return {
        "0th": {
            piexif.ImageIFD.Make: make.encode(),
            piexif.ImageIFD.Model: model.encode(),
            piexif.ImageIFD.DateTime: dt.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: dt.encode(),
            piexif.ExifIFD.ISOSpeedRatings: random.choice([100, 200, 400]),
            piexif.ExifIFD.FocalLength: (focal, 1),
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude: to_deg(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude: to_deg(lon),
        },
    }


# ================== ОБРАБОТКА ==================

def process_image(data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        raise ValueError("Не удалось открыть изображение")

    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    # шум
    arr = np.array(img).astype(np.int16)
    arr += np.random.normal(0, 2, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr)

    lat, lon = random.choice(COORDS)
    exif = piexif.dump(create_exif(lat, lon))

    out = io.BytesIO()
    img.save(out, "JPEG", quality=90, exif=exif)

    return out.getvalue()


# ================== TG ==================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Пришли фото")


@dp.message(F.photo | F.document)
async def handle(message: Message):
    try:
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        file = await bot.get_file(file_id)

        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)

        result = process_image(buf.getvalue())

        await message.answer_document(
            BufferedInputFile(result, filename="image.jpg")
        )

    except Exception as e:
        logging.exception("Ошибка обработки")
        await message.answer("Ошибка обработки файла")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
