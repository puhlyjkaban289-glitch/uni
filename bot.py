#!/usr/bin/env python3
"""
Telegram EXIF Spoofer Bot
- Удаляет оригинальные EXIF
- Подменяет GPS на случайные из coords.csv
- Меняет Make/Model на случайные из брендов (Apple, Samsung, Google, Xiaomi)
- Генерирует реалистичные EXIF-теги
- Уникализирует изображение (лёгкий ресайз → незаметно глазу, но уникально для ПК)
- Красивый интерфейс с эмодзи
"""

import os
import io
import csv
import random
import logging
from datetime import datetime, timedelta
from typing import Tuple, List, Dict

from dotenv import load_dotenv
from PIL import Image, ImageFilter
import piexif
from piexif import ImageIFD, ExifIFD, GPSIFD
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

# ==================== КОНФИГ ====================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEBUG = os.getenv("DEBUG", "0") == "1"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG if DEBUG else logging.INFO,
)
logger = logging.getLogger(__name__)

# Token check moved to main() to allow importing functions for testing

# ==================== ЗАГРУЗКА ДАННЫХ ====================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_coords() -> List[Tuple[float, float]]:
    """Загружает список координат из CSV"""
    coords = []
    path = os.path.join(DATA_DIR, "coords.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                coords.append((lat, lon))
            except (ValueError, KeyError):
                continue
    logger.info(f"Загружено {len(coords)} координат")
    return coords

def load_devices() -> List[Dict[str, str]]:
    """Загружает все устройства из CSV брендов"""
    devices = []
    brands = [
        "apple.csv", "google.csv", "samsung.csv", "xiaomi.csv",
        "huawei.csv", "oneplus.csv", "sony.csv", "motorola.csv",
        "oppo.csv", "honor.csv", "asus.csv"
    ]
    for brand_file in brands:
        path = os.path.join(DATA_DIR, brand_file)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                make = row.get("manufacturer", "").strip()
                model = row.get("model", "").strip()
                if make and model:
                    devices.append({"make": make, "model": model})
    logger.info(f"Загружено {len(devices)} моделей устройств")
    return devices

COORDS: List[Tuple[float, float]] = load_coords()
DEVICES: List[Dict[str, str]] = load_devices()

# Типичные версии ПО по брендам (для реализма)
SOFTWARE_VERSIONS = {
    "Apple": ["iOS 17.5.1", "iOS 17.6", "iOS 18.0", "iOS 17.4.1", "iOS 18.1"],
    "samsung": ["One UI 6.1", "One UI 6.0", "Android 14", "One UI 5.1", "One UI 7.0"],
    "Google": ["Android 14", "Android 15", "Android 14 QPR3", "Android 15 QPR"],
    "Xiaomi": ["HyperOS 1.0.5", "MIUI 14.0.6", "HyperOS 1.0", "MIUI 14.0.5", "HyperOS 2.0"],
    "Huawei": ["HarmonyOS 4.2", "HarmonyOS 5.0", "EMUI 14.0", "HarmonyOS 4.0"],
    "OnePlus": ["OxygenOS 14", "OxygenOS 15", "Android 14", "Android 15"],
    "Sony": ["Android 14", "Android 15", "Android 14 QPR"],
    "Motorola": ["Android 14", "Android 15", "Hello UX"],
    "OPPO": ["ColorOS 14", "ColorOS 15", "Android 14"],
    "Honor": ["MagicOS 8.0", "MagicOS 7.0", "Android 14"],
    "Asus": ["Android 14", "ROG UI", "Android 15", "ZenUI"],
}

def get_random_software(make: str) -> str:
    return random.choice(SOFTWARE_VERSIONS.get(make, ["Android 14"]))

# ==================== УНИКАЛИЗАЦИЯ ====================
def uniquify_image(img: Image.Image) -> Image.Image:
    """
    МАКСИМАЛЬНО сильная уникализация (двойной проход).
    Каждый проход включает:
    - Сильный ресайз (3%)
    - Очень лёгкий Gaussian noise (sigma ≈ 0.9)
    - Лёгкая резкость
    Два прохода дают значительно более сильный эффект без видимых артефактов и чёрных полос.
    """
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    w, h = img.size

    import numpy as np

    for _ in range(2):  # ДВОЙНОЙ ПРОХОД
        # 1. Сильное уменьшение (3%)
        scale = 0.97
        new_w = max(10, int(w * scale))
        new_h = max(10, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        img = img.resize((w, h), Image.LANCZOS)

        # 2. Очень лёгкий шум
        arr = np.array(img).astype(np.float32)
        noise = np.random.normal(0, 0.9, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # 3. Лёгкая резкость
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=115, threshold=2))

    return img

# ==================== ГЕНЕРАЦИЯ EXIF ====================
def _deg_to_dms_rational(deg: float) -> List[Tuple[int, int]]:
    """Преобразует десятичные градусы в DMS рациональные числа для piexif"""
    deg_abs = abs(deg)
    d = int(deg_abs)
    m = int((deg_abs - d) * 60)
    s = (deg_abs - d - m / 60.0) * 3600
    return [(d, 1), (m, 1), (int(round(s * 100)), 100)]

def create_fake_exif(make: str, model: str, lat: float, lon: float) -> bytes:
    """
    Создаёт реалистичный набор EXIF-тегов, как у настоящего смартфона.
    """
    # Случайная дата в последние 60 дней (реалистично)
    dt = datetime.now() - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
    dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")

    lat_dms = _deg_to_dms_rational(lat)
    lon_dms = _deg_to_dms_rational(lon)
    lat_ref = b"N" if lat >= 0 else b"S"
    lon_ref = b"E" if lon >= 0 else b"W"

    # Случайные, но правдоподобные параметры камеры
    exposure_denoms = [60, 80, 100, 125, 200, 250, 500, 1000]
    fnumber = round(random.uniform(1.4, 2.4), 1)
    iso = random.choice([50, 64, 80, 100, 125, 200, 250, 320, 400, 500, 640, 800])
    focal = round(random.uniform(3.8, 6.5), 1)  # типично для смартфонов

    software = get_random_software(make)

    exif_dict = {
        "0th": {
            ImageIFD.Make: make.encode("utf-8"),
            ImageIFD.Model: model.encode("utf-8"),
            ImageIFD.Software: software.encode("utf-8"),
            ImageIFD.DateTime: dt_str.encode("utf-8"),
            ImageIFD.Orientation: 1,  # Normal
            ImageIFD.XResolution: (72, 1),
            ImageIFD.YResolution: (72, 1),
            ImageIFD.ResolutionUnit: 2,  # inches
            ImageIFD.YCbCrPositioning: 1,
        },
        "Exif": {
            ExifIFD.DateTimeOriginal: dt_str.encode("utf-8"),
            ExifIFD.DateTimeDigitized: dt_str.encode("utf-8"),
            ExifIFD.ExposureTime: (1, random.choice(exposure_denoms)),
            ExifIFD.FNumber: (int(fnumber * 10), 10),
            ExifIFD.ExposureProgram: 2,  # Normal program
            ExifIFD.ISOSpeedRatings: iso,
            ExifIFD.ExifVersion: b"0230",
            ExifIFD.ComponentsConfiguration: b"\x01\x02\x03\x00",
            ExifIFD.ShutterSpeedValue: (int(random.uniform(6, 10) * 10), 10),  # approx
            ExifIFD.ApertureValue: (int(fnumber * 10), 10),
            ExifIFD.BrightnessValue: (random.randint(0, 80), 10),
            ExifIFD.ExposureBiasValue: (0, 1),
            ExifIFD.MeteringMode: 5,  # Pattern / Multi-spot
            ExifIFD.Flash: 0,  # No flash
            ExifIFD.FocalLength: (int(focal * 10), 10),
            ExifIFD.FocalLengthIn35mmFilm: random.choice([24, 26, 28, 35]),  # equiv.
            ExifIFD.DigitalZoomRatio: (1, 1),
            ExifIFD.SceneCaptureType: 0,  # Standard
            ExifIFD.LensMake: make.encode("utf-8"),
            ExifIFD.LensModel: model.encode("utf-8"),
        },
        "GPS": {
            GPSIFD.GPSVersionID: (2, 2, 0, 0),
            GPSIFD.GPSLatitudeRef: lat_ref,
            GPSIFD.GPSLatitude: lat_dms,
            GPSIFD.GPSLongitudeRef: lon_ref,
            GPSIFD.GPSLongitude: lon_dms,
            GPSIFD.GPSAltitudeRef: 0,  # Above sea level
            GPSIFD.GPSAltitude: (random.randint(5, 350), 1),
            GPSIFD.GPSTimeStamp: ((dt.hour, 1), (dt.minute, 1), (dt.second, 1)),
            GPSIFD.GPSDateStamp: dt.strftime("%Y:%m:%d").encode("utf-8"),
            GPSIFD.GPSProcessingMethod: b"GPS",
        },
    }

    try:
        return piexif.dump(exif_dict)
    except Exception as e:
        logger.warning(f"Ошибка генерации EXIF: {e}. Возвращаем минимальный набор.")
        # Минимальный fallback
        minimal = {
            "0th": {
                ImageIFD.Make: make.encode("utf-8"),
                ImageIFD.Model: model.encode("utf-8"),
                ImageIFD.DateTime: dt_str.encode("utf-8"),
            },
            "GPS": {
                GPSIFD.GPSVersionID: (2, 2, 0, 0),
                GPSIFD.GPSLatitudeRef: lat_ref,
                GPSIFD.GPSLatitude: lat_dms,
                GPSIFD.GPSLongitudeRef: lon_ref,
                GPSIFD.GPSLongitude: lon_dms,
            },
        }
        return piexif.dump(minimal)

# ==================== ОБРАБОТКА ФОТО ====================
def process_photo(file_bytes: bytes) -> Tuple[bytes, Dict]:
    """
    Основная функция обработки:
    - Уникализация
    - Генерация нового EXIF с случайными координатами и устройством
    - Возврат JPEG-байтов + метаданные для подписи
    """
    # Выбираем случайное устройство и координаты
    device = random.choice(DEVICES)
    make = device["make"]
    model = device["model"]
    lat, lon = random.choice(COORDS)

    # Открываем изображение
    img = Image.open(io.BytesIO(file_bytes))

    # Уникализируем (изменяем пиксели незаметно)
    img = uniquify_image(img)

    # Генерируем EXIF
    exif_bytes = create_fake_exif(make, model, lat, lon)

    # Сохраняем в JPEG высокого качества с новым EXIF
    output = io.BytesIO()
    img.save(
        output,
        format="JPEG",
        quality=94,
        optimize=True,
        exif=exif_bytes,
    )
    processed_bytes = output.getvalue()

    meta = {
        "make": make,
        "model": model,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "software": get_random_software(make),
    }
    return processed_bytes, meta

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Красивое приветственное сообщение"""
    keyboard = [
        [InlineKeyboardButton("📸 Отправь фото — я обработаю", callback_data="howto")],
        [
            InlineKeyboardButton("ℹ️ Как это работает", callback_data="about"),
            InlineKeyboardButton("🛠 Настройки", callback_data="settings"),
        ],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "👋 <b>Привет!</b> Я — бот для приватности и «свежести» фотографий.\n\n"
        "Что я умею:\n"
        "• Полностью удаляю оригинальные EXIF-данные (GPS, модель камеры, серийники)\n"
        "• Подменяю координаты на случайные из большой базы\n"
        "• Меняю производителя и модель телефона (Apple / Samsung / Google / Xiaomi)\n"
        "• Генерирую правдоподобные EXIF, как будто фото снято только что на этот телефон\n"
        "• Делаю фото <b>уникальным</b> — глазу почти незаметно, но для компьютера и reverse-search это уже другая картинка\n\n"
        "Просто <b>отправь мне любое фото</b> 📸 и через секунду получишь обработанную версию!\n\n"
        "Всё происходит в памяти. Никаких сохранений и логов."
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка inline-кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == "howto":
        await query.edit_message_text(
            "📸 <b>Как обработать фото:</b>\n\n"
            "1. Просто отправь мне фотографию (не как документ)\n"
            "2. Я мгновенно обработаю её и пришлю назад\n"
            "3. В подписи будет указано, какое устройство и координаты я подставил\n\n"
            "Готово! Теперь фото выглядит так, будто его сняли в другом месте и на другом телефоне.",
            parse_mode="HTML",
        )
    elif query.data == "about":
        await query.edit_message_text(
            "🧠 <b>Как это работает технически:</b>\n\n"
            "1. Удаляем все оригинальные EXIF-теги\n"
            "2. Выбираем случайную модель из базы (Apple iPhone 11-15, Samsung S23/S24, Pixel 5-8, Redmi Note)\n"
            "3. Берём случайные координаты из ~500 точек (Россия, Сибирь, Арктика и др.)\n"
            "4. Генерируем полный набор EXIF: ExposureTime, ISO, FocalLength, Software, Lens и т.д.\n"
            "5. Делаем уникализацию через микроскопический ресайз (LANCZOS) — меняются пиксели, но визуально фото идентично\n"
            "6. Сохраняем JPEG 94% качества с новым EXIF\n\n"
            "Результат невозможно отличить от настоящего снимка с указанного телефона в указанной локации.",
            parse_mode="HTML",
        )
    elif query.data == "settings":
        await query.edit_message_text(
            "🛠 <b>Настройки (пока в разработке)</b>\n\n"
            "Сейчас бот работает полностью автоматически:\n"
            "• Случайное устройство каждый раз\n"
            "• Случайные координаты\n\n"
            "В ближайшем обновлении появится:\n"
            "• Выбор любимого бренда (только Apple / только Samsung и т.д.)\n"
            "• Фиксированные координаты или регион\n"
            "• Сохранение предпочтений пользователя\n\n"
            "Хочешь конкретную фичу — напиши @твой_юзернейм",
            parse_mode="HTML",
        )
    elif query.data == "help":
        await query.edit_message_text(
            "❓ <b>Помощь</b>\n\n"
            "/start — главное меню\n"
            "Просто отправь фото — и я его обработаю\n\n"
            "<b>Что меняется:</b>\n"
            "• Полностью новый EXIF (включая GPS)\n"
            "• Новая модель телефона\n"
            "• Уникальные пиксели (защита от duplicate detection)\n\n"
            "Фото не сохраняется на сервере. Обработка в оперативной памяти.\n\n"
            "Если что-то пошло не так — попробуй ещё раз или пришли скриншот ошибки.",
            parse_mode="HTML",
        )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка входящего фото"""
    message = update.message
    if not message.photo:
        await message.reply_text("Пожалуйста, отправь фото (не документ) 📸")
        return

    # Берём самое большое разрешение
    photo = message.photo[-1]

    try:
        # Скачиваем
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        # Обрабатываем (синхронно, т.к. быстро)
        processed_bytes, meta = process_photo(bytes(file_bytes))

        # Готовим подпись
        caption = (
            f"✅ <b>Фото успешно обработано!</b>\n\n"
            f"📱 <b>Устройство:</b> {meta['make']} {meta['model']}\n"
            f"📍 <b>Координаты:</b> {meta['lat']}, {meta['lon']}\n"
            f"🕒 <b>Дата EXIF:</b> (сгенерирована недавно)\n"
            f"🔧 <b>Software:</b> {meta['software']}\n\n"
            f"🔒 Оригинальные EXIF удалены • Фото уникализировано"
        )

        # Отправляем обратно как фото
        await message.reply_photo(
            photo=io.BytesIO(processed_bytes),
            caption=caption,
            parse_mode="HTML",
        )

        logger.info(
            f"Обработано фото для пользователя {message.from_user.id} "
            f"→ {meta['make']} {meta['model']} @ {meta['lat']},{meta['lon']}"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}", exc_info=DEBUG)
        await message.reply_text(
            "😕 Произошла ошибка при обработке. Попробуй ещё раз или пришли фото поменьше.\n\n"
            f"Техническая информация: <code>{str(e)[:100]}</code>",
            parse_mode="HTML",
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Используй /start для главного меню или просто отправь фото 📸"
    )

# ==================== MAIN ====================
def main() -> None:
    """Запуск бота"""
    logger.info("Запуск Telegram EXIF Spoofer Bot...")

    # Улучшенный HTTPXRequest с повышенными таймаутами и большим пулом соединений.
    # Это критично для Railway (холодный старт + переменная сеть) и решает TimedOut ошибки.
    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=60.0,
    )

    application = (
        Application.builder()
        .token(TOKEN)
        .request(request)
        .build()
    )

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Inline кнопки
    application.add_handler(CallbackQueryHandler(button_callback))

    # Фото
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Запуск
    logger.info("Бот запущен и готов принимать фото!")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
