import os
import time
import telebot
import csv
import random

TOKEN = os.getenv("BOT_TOKEN")  # токен через Railway Variables
bot = telebot.TeleBot(TOKEN)

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


@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    brand, model = random_device()
    lat, lon = random.choice(COORDS)

    text = f"""📱 Устройство:
{brand} {model}

📍 Координаты:
{lat}, {lon}
"""

    bot.send_message(msg.chat.id, text)

    # 👉 тут вставишь свой EXIF код


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
