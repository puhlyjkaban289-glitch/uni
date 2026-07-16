"""
Telegram-бот для "приватизации" фото:
- полностью удаляет метаданные (EXIF, GPS, XMP и т.д.)
- перекодирует изображение (случайное качество JPEG)
- добавляет случайные лёгкие искажения: поворот, кроп/масштаб,
  цветокоррекция, шум, иногда зеркалирование
- возвращает файл со случайным "телефонным" именем вида
  IMG_20260712_150953.jpg

Никакие метаданные геолокации НЕ подставляются — они просто удаляются.
Это сделано намеренно: бот не подделывает происхождение фото,
а лишь снижает узнаваемость и защищает приватность автора.
"""

import io
import logging
import random
import string
from datetime import datetime, timedelta

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile

logging.basicConfig(level=logging.INFO)

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- Обработка изображения ----------

def random_geometry(img: Image.Image) -> Image.Image:
    """Небольшой случайный поворот + небольшой случайный кроп/масштаб."""
    angle = random.uniform(-2.5, 2.5)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0))

    w, h = img.size
    crop_pct = random.uniform(0.0, 0.03)  # до 3% с каждой стороны
    left = int(w * random.uniform(0, crop_pct))
    top = int(h * random.uniform(0, crop_pct))
    right = w - int(w * random.uniform(0, crop_pct))
    bottom = h - int(h * random.uniform(0, crop_pct))
    if right > left and bottom > top:
        img = img.crop((left, top, right, bottom))

    # случайный микро-ресайз (масштаб ±2%)
    scale = random.uniform(0.98, 1.02)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    return img


def random_mirror(img: Image.Image) -> Image.Image:
    if random.random() < 0.5:
        return ImageOps.mirror(img)
    return img


def random_color(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Color(img).enhance(random.uniform(0.92, 1.08))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.15))
    return img


def random_noise(img: Image.Image) -> Image.Image:
    if random.random() < 0.7:
        arr = np.array(img).astype(np.int16)
        sigma = random.uniform(1.5, 5.0)
        noise = np.random.normal(0, sigma, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.6)))
    return img


def process_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)  # учесть исходную ориентацию до удаления EXIF
    img = img.convert("RGB")

    img = random_geometry(img)
    img = random_mirror(img)
    img = random_color(img)
    img = random_noise(img)

    out = io.BytesIO()
    quality = random.randint(84, 95)
    # save() без exif=... и без параметра icc_profile — метаданные не переносятся
    img.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def random_phone_filename() -> str:
    """Имя вида IMG_20260712_150953.jpg со случайной правдоподобной датой."""
    days_back = random.randint(0, 365 * 2)
    dt = datetime.now() - timedelta(days=days_back,
                                     hours=random.randint(0, 23),
                                     minutes=random.randint(0, 59),
                                     seconds=random.randint(0, 59))
    rand_suffix = "".join(random.choices(string.digits, k=0))  # оставлено для расширения при желании
    return f"IMG_{dt.strftime('%Y%m%d_%H%M%S')}{rand_suffix}.jpg"


# ---------- Хендлеры ----------

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Пришли мне фото (как файл или как обычное фото), "
        "и я верну его перекодированным, без метаданных и с лёгкими "
        "случайными изменениями."
    )


@dp.message(F.photo | F.document)
async def photo_handler(message: Message):
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        else:
            await message.answer("Это не похоже на изображение.")
            return

        tg_file = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(tg_file.file_path, destination=buf)
        raw_bytes = buf.getvalue()

        processed = process_image(raw_bytes)
        filename = random_phone_filename()

        await message.answer_document(
            BufferedInputFile(processed, filename=filename),
            caption="Готово: метаданные удалены, изображение перекодировано."
        )
    except Exception as e:
        logging.exception("Ошибка обработки фото")
        await message.answer(f"Не получилось обработать файл: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
