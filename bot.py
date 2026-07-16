import io
import logging
import math
import os
import random
import sys
import csv
from datetime import datetime, timedelta

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
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

def load_coords(path="/mnt/data/coords.csv"):
    coords = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coords.append((float(row["lat"]), float(row["lon"])))
    return coords


COORDS = load_coords()


# ================== УСТРОЙСТВА ==================

DEVICES = [
    # Apple
    {
        "make": "Apple",
        "model": "iPhone 13",
        "lens": "iPhone 13 back dual wide camera 5.1mm f/1.6",
        "focal": 26,
    },
    {
        "make": "Apple",
        "model": "iPhone 14 Pro",
        "lens": "iPhone 14 Pro back triple camera 6.86mm f/1.78",
        "focal": 24,
    },

    # Samsung
    {
        "make": "samsung",
        "model": "SM-S911B",
        "lens": "Samsung Galaxy S23 back camera 6.4mm f/1.8",
        "focal": 24,
    },

    # Xiaomi
    {
        "make": "Xiaomi",
        "model": "Mi 11",
        "lens": "Xiaomi Mi 11 camera 5.4mm f/1.85",
        "focal": 27,
    },
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


# ================== РЕАЛИСТИЧНЫЙ EXIF ==================

def create_realistic_exif(lat, lon):
    device = random.choice(DEVICES)
    dt = random_datetime()

    iso = random.choice([50, 64, 100, 200, 400])
    exposure_den = random.choice([30, 60, 120, 250, 500, 1000])
    fnum = random.choice([(18, 10), (20, 10), (22, 10)])  # f/1.8–2.2

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: to_deg(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: to_deg(lon),
    }

    zeroth_ifd = {
        piexif.ImageIFD.Make: device["make"].encode(),
        piexif.ImageIFD.Model: device["model"].encode(),
        piexif.ImageIFD.Software: b"Photos 1.0",
        piexif.ImageIFD.DateTime: dt.encode(),
        piexif.ImageIFD.Orientation: 1,
    }

    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: dt.encode(),
        piexif.ExifIFD.DateTimeDigitized: dt.encode(),
        piexif.ExifIFD.LensMake: device["make"].encode(),
        piexif.ExifIFD.LensModel: device["lens"].encode(),

        piexif.ExifIFD.ISOSpeedRatings: iso,
        piexif.ExifIFD.ExposureTime: (1, exposure_den),
        piexif.ExifIFD.FNumber: fnum,
        piexif.ExifIFD.FocalLength: (device["focal"], 1),

        piexif.ExifIFD.WhiteBalance: 0,
        piexif.ExifIFD.ExposureMode: 0,
        piexif.ExifIFD.SceneCaptureType: 0,
    }

    return {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
        "1st": {},
        "thumbnail": None,
    }


# ================== ОБРАБОТКА ИЗОБРАЖЕНИЯ ==================

def random_geometry(img):
    angle = random.uniform(-1.2, 1.2)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0))
    return img


def random_pipeline(img):
    img = ImageOps.mirror(img)

    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Color(img).enhance(random.uniform(0.92, 1.08))

    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, random.uniform(1.5, 4.0), arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

    return Image.fromarray(arr)


def process_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))

    # Учитываем ориентацию, затем полностью "обнуляем" EXIF
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    img = random_geometry(img)
    img = random_pipeline(img)

    lat, lon = random.choice(COORDS)

    exif_dict = create_realistic_exif(lat, lon)
    exif_bytes = piexif.dump(exif_dict)

    out = io.BytesIO()
    img.save(
        out,
        format="JPEG",
        quality=random.randint(85, 95),
        optimize=True,
        exif=exif_bytes
    )

    return out.getvalue()


# ================== TELEGRAM ==================

def random_phone_filename():
    dt = datetime.now() - timedelta(days=random.randint(0, 700))
    return f"IMG_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Пришли фото — верну как будто снято на телефон 📱")


@dp.message(F.photo | F.document)
async def photo_handler(message: Message):
    try:
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id

        tg_file = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(tg_file.file_path, destination=buf)

        processed = process_image(buf.getvalue())

        await message.answer_document(
            BufferedInputFile(processed, filename=random_phone_filename()),
            caption="Готово: фото перекодировано + реалистичный EXIF добавлен"
        )

    except Exception as e:
        logging.exception("Ошибка")
        await message.answer(f"Ошибка: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())