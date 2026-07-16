import os
import telebot
import piexif
from PIL import Image
from io import BytesIO
import random
import csv

TOKEN = os.getenv("BOT_TOKEN")  # токен через Railway Variables
bot = telebot.TeleBot(TOKEN)

print("🔥 START FILE")

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise Exception("❌ BOT_TOKEN не найден")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================
# 📍 Загрузка координат
# =========================
def load_coords():
    coords = []
    path = os.path.join(BASE_DIR, "coords.csv")

    if not os.path.exists(path):
        print("⚠️ coords.csv НЕ найден")
        return [(55.7558, 37.6173)]

    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # пропуск заголовка

        for row in reader:
            try:
                coords.append((float(row[0]), float(row[1])))
            except:
                continue

    return coords if coords else [(55.7558, 37.6173)]


COORDS = load_coords()

# =========================
# 📱 Загрузка устройств
# =========================
def load_devices():
    brands = {}

    files = {
        "Apple": "apple.csv",
        "Samsung": "samsung.csv",
        "Xiaomi": "xiaomi.csv",
        "Google": "google.csv"
    }

    for brand, filename in files.items():
        path = os.path.join(BASE_DIR, filename)

        if not os.path.exists(path):
            print(f"⚠️ нет файла {filename}")
            continue

        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            models = [row[0] for row in reader if row]

            if models:
                brands[brand] = models

    return brands


DEVICES = load_devices()

# =========================
# 🎲 Генерация устройства
# =========================
def random_device():
    brand = random.choice(list(DEVICES.keys()))
    model = random.choice(DEVICES[brand])
    return brand, model


# =========================
# 🤖 БОТ
# =========================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "📸 Пришли фото — добавлю метаданные")

# =========================
# 📍 GPS → EXIF формат
# =========================
def to_deg(value):
    d = int(value)
    m = int((value - d) * 60)
    s = int(((value - d) * 60 - m) * 60 * 100)
    return ((d,1),(m,1),(s,100))


def make_exif(brand, model, lat, lon):
    zeroth_ifd = {
        piexif.ImageIFD.Make: brand.encode(),
        piexif.ImageIFD.Model: model.encode(),
    }

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b'N' if lat >= 0 else b'S',
        piexif.GPSIFD.GPSLatitude: to_deg(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: b'E' if lon >= 0 else b'W',
        piexif.GPSIFD.GPSLongitude: to_deg(abs(lon)),
    }

    exif_dict = {"0th": zeroth_ifd, "GPS": gps_ifd}
    return piexif.dump(exif_dict)

# =========================
# 🤖 ОБРАБОТКА ФОТО
# =========================
@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    try:
        # 📥 скачать фото
        file_info = bot.get_file(msg.photo[-1].file_id)
        file_bytes = bot.download_file(file_info.file_path)

        image = Image.open(BytesIO(file_bytes)).convert("RGB")

        # 🎲 данные
        brand, model = random_device()
        lat = round(random.uniform(-90, 90), 6)
        lon = round(random.uniform(-180, 180), 6)

        # 🧠 EXIF
        exif_bytes = make_exif(brand, model, lat, lon)

        # 💾 сохранить в память
        output = BytesIO()
        image.save(output, format="JPEG", exif=exif_bytes)
        output.seek(0)

        caption = f"""📱 Устройство:
{brand} {model}

📍 Координаты:
{lat}, {lon}
"""

        # 📤 ОТПРАВКА ФОТО (ВАЖНО!)
        bot.send_photo(
            msg.chat.id,
            photo=output,
            caption=caption
        )

    except Exception as e:
        bot.send_message(msg.chat.id, f"Ошибка: {e}")
# =========================
# 🚀 ЗАПУСК (ВАЖНО!)
# =========================
def run():
    print("🚀 Бот запущен")

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print("❌ Ошибка:", e)
            time.sleep(5)


if __name__ == "__main__":
    run()
