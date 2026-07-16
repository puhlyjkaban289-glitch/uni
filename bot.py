import io
import logging
import os
import random
import sys
import csv
from datetime import datetime, timedelta

from PIL import Image, ImageOps
import numpy as np
import piexif

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ Нет TELEGRAM_BOT_TOKEN")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================== КООРДИНАТЫ ==================

def load_coords(path="coords.csv"):
    coords = []

    if not os.path.exists(path):
        logging.warning("coords.csv не найден → fallback")
        return [(55.7558, 37.6173)]

    try:
        with open(path) as f:
            reader = csv.reader(f)
            rows = list(reader)

            # если есть заголовки
            if rows and ("lat" in rows[0][0].lower()):
                reader = csv.DictReader(open(path))
                for row in reader:
                    coords.append((float(row["lat"]), float(row["lon"])))
            else:
                for row in rows:
                    if len(row) >= 2:
                        coords.append((float(row[0]), float(row[1])))

    except Exception as e:
        logging.error(f"Ошибка coords: {e}")
        return [(55.7558, 37.6173)]

    return coords if coords else [(55.7558, 37.6173)]


COORDS = load_coords()


# ================== EXIF ==================

def to_deg(val):
    val = abs(val)
    d = int(val)
    m = int((val - d) * 60)
    s = int((((val - d) * 60) - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def random_dt():
    dt = datetime.now() - timedelta(days=random.randint(0, 365))
    return dt.strftime("%Y:%m:%d %H:%M:%S")


def create_exif(lat, lon):
    dt = random_dt()

    return {
        "0th": {
            piexif.ImageIFD.Make: b"Apple",
            piexif.ImageIFD.Model: b"iPhone 13",
            piexif.ImageIFD.DateTime: dt.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: dt.encode(),
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
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")

    # ✔ FIX numpy crash
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, 2, arr.shape).astype(np.float32)
    arr = arr + noise
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
    await message.answer("Отправь фото")


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
        logging.exception("Ошибка")
        await message.answer("Ошибка обработки")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
