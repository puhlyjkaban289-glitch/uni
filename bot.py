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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("Нет TELEGRAM_BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== КООРДИНАТЫ ==================

def load_coords(path="coords.csv"):
    coords = []

    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл координат не найден: {path}")

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coords.append((float(row["lat"]), float(row["lon"])))

    if not coords:
        raise ValueError("coords.csv пустой")

    return coords


COORDS = load_coords()


# ================== УСТРОЙСТВА ==================

DEVICES = [
    {"make": "Apple", "model": "iPhone 13", "lens": "iPhone 13 camera", "focal": 26},
    {"make": "Apple", "model": "iPhone 14 Pro", "lens": "iPhone 14 Pro camera", "focal": 24},
    {"make": "samsung", "model": "SM-S911B", "lens": "Samsung S23 camera", "focal": 24},
    {"make": "Xiaomi", "model": "Mi 11", "lens": "Mi 11 camera", "focal": 27},
]


# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def to_deg(value):
    abs_value = abs(value)
    deg = int(abs_value)
    min_float = (abs_value - deg) * 60
    minutes = int(min_float)
    sec = round((min_float - minutes) * 60 * 100)

    return ((deg, 1), (minutes, 1), (sec, 100))


def random_datetime():
    dt = datetime.now() - timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return dt.strftime("%Y:%m:%d %H:%M:%S")


# ================== EXIF ==================

def create_realistic_exif(lat, lon):
    device = random.choice(DEVICES)
    dt = random_datetime()

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: to_deg(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: to_deg(lon),
    }

    zeroth_ifd = {
        piexif.ImageIFD.Make: device["make"].encode(),
        piexif.ImageIFD.Model: device["model"].encode(),
        piexif.ImageIFD.DateTime: dt.encode(),
    }

    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: dt.encode(),
        piexif.ExifIFD.ISOSpeedRatings: random.choice([100, 200, 400]),
        piexif.ExifIFD.FocalLength: (device["focal"], 1),
    }

    return {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
        "1st": {},
        "thumbnail": None,
    }


# ================== ОБРАБОТКА ==================

def process_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))

    # Удаляем старый EXIF
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    # лёгкая обработка
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.05))

    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 2, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr)

    lat, lon = random.choice(COORDS)

    exif_bytes = piexif.dump(create_realistic_exif(lat, lon))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, exif=exif_bytes)

    return out.getvalue()


# ================== TELEGRAM ==================

def random_filename():
    dt = datetime.now()
    return f"IMG_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Пришли фото")


@dp.message(F.photo | F.document)
async def handler(message: Message):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    tg_file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(tg_file.file_path, destination=buf)

    processed = process_image(buf.getvalue())

    await message.answer_document(
        BufferedInputFile(processed, filename=random_filename())
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())