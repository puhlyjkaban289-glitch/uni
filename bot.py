import io
import os
import sys
import csv
import random
import logging
from datetime import datetime, timedelta

import numpy as np
from PIL import Image, ImageOps
import piexif

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("No TELEGRAM_BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== КООРДИНАТЫ ==================

def load_coords():
    coords = []

    if not os.path.exists("coords.csv"):
        return [(55.7558, 37.6173)]

    try:
        with open("coords.csv") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    coords.append((float(row[0]), float(row[1])))
    except:
        return [(55.7558, 37.6173)]

    return coords if coords else [(55.7558, 37.6173)]


COORDS = load_coords()


# ================== УСТРОЙСТВА ==================

DEVICES = [
    {
        "make": b"Apple",
        "model": b"iPhone 13",
        "lens": b"iPhone 13 back camera 4.2mm f/1.6",
        "software": b"16.6",
    },
    {
        "make": b"samsung",
        "model": b"SM-S911B",
        "lens": b"Samsung S23 camera",
        "software": b"13",
    },
]


# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def to_deg(val):
    val = abs(val)
    d = int(val)
    m = int((val - d) * 60)
    s = int((((val - d) * 60) - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def random_datetime():
    dt = datetime.now() - timedelta(
        days=random.randint(0, 365),
        seconds=random.randint(0, 86400),
    )
    return dt.strftime("%Y:%m:%d %H:%M:%S"), str(random.randint(100, 999))


def realistic_filename(device):
    if device["make"] == b"Apple":
        return f"IMG_{random.randint(1000,9999)}.JPG"
    else:
        return datetime.now().strftime("%Y%m%d_%H%M%S.jpg")


# ================== EXIF ==================

def create_exif(lat, lon, device):
    dt, subsec = random_datetime()
    orientation = random.choice([1, 3, 6, 8])

    return piexif.dump({
        "0th": {
            piexif.ImageIFD.Make: device["make"],
            piexif.ImageIFD.Model: device["model"],
            piexif.ImageIFD.Software: device["software"],
            piexif.ImageIFD.Orientation: orientation,
            piexif.ImageIFD.DateTime: dt.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: dt.encode(),
            piexif.ExifIFD.DateTimeDigitized: dt.encode(),
            piexif.ExifIFD.SubSecTimeOriginal: subsec.encode(),
            piexif.ExifIFD.LensMake: device["make"],
            piexif.ExifIFD.LensModel: device["lens"],
            piexif.ExifIFD.ExposureTime: (1, random.choice([30, 60, 120])),
            piexif.ExifIFD.FNumber: (random.choice([16, 18]), 10),
            piexif.ExifIFD.ISOSpeedRatings: random.choice([50, 100, 200]),
            piexif.ExifIFD.FocalLength: (42, 10),
            piexif.ExifIFD.WhiteBalance: 0,
            piexif.ExifIFD.Flash: 0,
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude: to_deg(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude: to_deg(lon),
        },
    })


# ================== ОБРАБОТКА ==================

def process_image(data: bytes):
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    device = random.choice(DEVICES)

    # фронталка (зеркало)
    if random.random() < 0.3:
        img = ImageOps.mirror(img)

    # шум (реализм)
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, 2, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    lat, lon = random.choice(COORDS)

    exif = create_exif(lat, lon, device)

    output = io.BytesIO()
    img.save(output, "JPEG", quality=92, subsampling=2, exif=exif)

    filename = realistic_filename(device)

    return output.getvalue(), filename


# ================== TELEGRAM ==================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Отправь фото")


@dp.message(F.photo | F.document)
async def handler(message: Message):
    try:
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        file = await bot.get_file(file_id)

        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)

        result, filename = process_image(buf.getvalue())

        await message.answer_document(
            BufferedInputFile(result, filename=filename)
        )

    except Exception as e:
        logging.exception(e)
        await message.answer("Ошибка обработки")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
