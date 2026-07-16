import io
import os
import random
import csv
import string
from datetime import datetime, timedelta

from PIL import Image
import piexif


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ===== CSV =====

def load_models(file):
    models = []
    with open(os.path.join(BASE_DIR, file), newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                models.append(row[0].strip())
    return models


APPLE = load_models("apple.csv")
SAMSUNG = load_models("samsung.csv")
XIAOMI = load_models("xiaomi.csv")
GOOGLE = load_models("google.csv")

BRANDS = {
    "Apple": APPLE,
    "Samsung": SAMSUNG,
    "Xiaomi": XIAOMI,
    "Google": GOOGLE,
}


def load_coords():
    coords = []
    with open(os.path.join(BASE_DIR, "coords(2).csv"), newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                coords.append((float(row[0]), float(row[1])))
    return coords


COORDS = load_coords()


# ===== ВСПОМОГАТЕЛЬНОЕ =====

def random_datetime():
    return datetime.now() - timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )


def deg_to_dms_rational(deg_float):
    deg = int(deg_float)
    min_float = abs((deg_float - deg) * 60)
    minute = int(min_float)
    sec = int((min_float - minute) * 60 * 100)
    return ((abs(deg), 1), (minute, 1), (sec, 100))


def random_device():
    brand = random.choice(list(BRANDS.keys()))
    model = random.choice(BRANDS[brand])
    return brand, model


# ===== СЕРИЙНИКИ =====

def random_serial(brand):
    if brand == "Apple":
        # Пример: C02ZQ0ABCDE
        return random.choice(string.ascii_uppercase) + \
               random.choice(string.digits) + \
               random.choice(string.ascii_uppercase) + \
               ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    elif brand == "Samsung":
        # Пример: R58N123ABC
        return "R" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    elif brand == "Xiaomi":
        # Пример: 12345/ABCDEF12
        return ''.join(random.choices(string.digits, k=5)) + "/" + \
               ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    elif brand == "Google":
        # Пример: G9ABC123XYZ
        return "G" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))


def random_image_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=32))


def random_gps():
    lat, lon = random.choice(COORDS)

    return {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: deg_to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: deg_to_dms_rational(lon),
    }


# ===== EXIF =====

def generate_exif():
    brand, model = random_device()
    dt = random_datetime()

    dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")

    serial = random_serial(brand)

    zeroth_ifd = {
        piexif.ImageIFD.Make: brand.encode(),
        piexif.ImageIFD.Model: model.encode(),
        piexif.ImageIFD.Software: b"Camera",
        piexif.ImageIFD.DateTime: dt_str.encode(),
    }

    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: dt_str.encode(),
        piexif.ExifIFD.DateTimeDigitized: dt_str.encode(),
        piexif.ExifIFD.LensMake: brand.encode(),
        piexif.ExifIFD.LensModel: model.encode(),

        # 📸 камера
        piexif.ExifIFD.FNumber: (random.randint(17, 22), 10),
        piexif.ExifIFD.ExposureTime: (1, random.randint(30, 500)),
        piexif.ExifIFD.ISOSpeedRatings: random.choice([50, 100, 200, 400]),
        piexif.ExifIFD.FocalLength: (random.randint(3, 7), 1),

        # 🔥 серийники
        piexif.ExifIFD.BodySerialNumber: serial.encode(),
        piexif.ExifIFD.ImageUniqueID: random_image_id().encode(),
    }

    gps_ifd = random_gps()

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
    }

    return piexif.dump(exif_dict)


# ===== ОБРАБОТКА =====

def process_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")

    # удаляем ВСЁ
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)

    exif_bytes = generate_exif()

    out = io.BytesIO()
    clean.save(out, "jpeg", quality=95, exif=exif_bytes)

    return out.getvalue()


# ===== ИМЯ ФАЙЛА =====

def random_phone_filename():
    dt = random_datetime()
    return f"IMG_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
