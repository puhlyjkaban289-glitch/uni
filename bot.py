"""
Telegram-бот для "приватизации" фото:
- полностью удаляет метаданные (EXIF, GPS, XMP и т.д.)
- перекодирует изображение (случайное качество JPEG)
- добавляет лёгкие искажения: кроп/масштаб,
  цветокоррекция, шум + **обязательное** зеркальное отражение
- возвращает файл со случайным "телефонным" именем вида
  IMG_20260712_150953.jpg

Никакие метаданные геолокации НЕ подставляются — они просто удаляются.
Это сделано намеренно: бот не подделывает происхождение фото,
а лишь снижает узнаваемость и защищает приватность автора.
"""

import io
import logging
import math
import os
import random
import string
import sys
from datetime import datetime, timedelta

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile

logging.basicConfig(level=logging.INFO)

# ==== НАСТРОЙКИ ====
# Токен НИКОГДА не хранится в коде. Задайте переменную окружения
# TELEGRAM_BOT_TOKEN (в Railway: Settings -> Variables) со значением
# токена от @BotFather.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit(
        "Не найдена переменная окружения TELEGRAM_BOT_TOKEN. "
        "Задайте её со значением токена от @BotFather перед запуском."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- Обработка изображения ----------

def _largest_rect_after_rotation(w: float, h: float, angle_rad: float):
    """
    Размер (в пикселях исходного, неповёрнутого изображения) наибольшего
    прямоугольника без чёрных полей, который помещается внутри повёрнутого
    на angle_rad изображения размера w x h.
    """
    if w <= 0 or h <= 0:
        return 0, 0

    width_is_longer = w >= h
    side_long, side_short = (w, h) if width_is_longer else (h, w)

    sin_a, cos_a = abs(math.sin(angle_rad)), abs(math.cos(angle_rad))
    if side_short <= 2.0 * sin_a * cos_a * side_long or abs(sin_a - cos_a) < 1e-10:
        # "дегенеративный" случай (около 45° и т.п.)
        x = 0.5 * side_short
        if width_is_longer:
            wr, hr = x / sin_a, x / cos_a
        else:
            wr, hr = x / cos_a, x / sin_a
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr = (w * cos_a - h * sin_a) / cos_2a
        hr = (h * cos_a - w * sin_a) / cos_2a

    return wr, hr


def random_geometry(img: Image.Image) -> Image.Image:
    """Небольшой случайный поворот с точной обрезкой чёрных углов + небольшой доп. кроп/масштаб."""
    angle = random.uniform(-1.2, 1.2)  # уменьшенный угол — выглядит естественнее
    orig_w, orig_h = img.size

    rotated = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0))

    # Точный размер наибольшего прямоугольника без чёрных полей
    wr, hr = _largest_rect_after_rotation(orig_w, orig_h, math.radians(angle))
    wr = min(wr, rotated.width)
    hr = min(hr, rotated.height)

    rw, rh = rotated.size
    left = (rw - wr) / 2
    top = (rh - hr) / 2
    right = left + wr
    bottom = top + hr
    img = rotated.crop((int(left), int(top), int(right), int(bottom)))

    # дополнительный небольшой кроп/масштаб (магнитуда случайная, но всегда применяется)
    w, h = img.size
    crop_pct = random.uniform(0.0, 0.03)  # до 3% с каждой стороны
    left = int(w * random.uniform(0, crop_pct))
    top = int(h * random.uniform(0, crop_pct))
    right = w - int(w * random.uniform(0, crop_pct))
    bottom = h - int(h * random.uniform(0, crop_pct))
    if right > left and bottom > top:
        img = img.crop((left, top, right, bottom))

    scale = random.uniform(0.98, 1.02)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    return img


def random_mirror(img: Image.Image) -> Image.Image:
    """Всегда зеркалит изображение (горизонтальное отражение)."""
    return ImageOps.mirror(img)


def random_color(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.94, 1.06))
    img = ImageEnhance.Color(img).enhance(random.uniform(0.92, 1.08))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.15))
    return img


def random_noise(img: Image.Image) -> Image.Image:
    """Шум и лёгкое размытие применяются всегда, случайна только их величина."""
    arr = np.array(img).astype(np.int16)
    sigma = random.uniform(1.5, 5.0)
    noise = np.random.normal(0, sigma, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.15, 0.5)))
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
        "и я верну его перекодированным, с зеркальным отражением, "
        "без метаданных и с лёгкими случайными изменениями."
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
            caption="Готово: зеркальное отражение + метаданные обновлены (GPS), изображение перекодировано."
        )
    except Exception as e:
        logging.exception("Ошибка обработки фото")
        await message.answer(f"Не получилось обработать файл: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
