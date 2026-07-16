import io
import os
import random
import csv
from datetime import datetime, timedelta

from PIL import Image
import piexif

# ====== ЗАГРУЗКА CSV ======

BASE_DIR = "/mnt/data"

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


# ====== ВСПОМОГАТЕЛЬНЫЕ ======

def random_datetime():
    dt = datetime.now() - timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    return dt

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


def random_gps():
    lat, lon = random.choice(COORDS)

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: deg_to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: deg_to_dms_rational(lon),
    }
    return gps_ifd


# ====== ГЕНЕРАЦИЯ EXIF ======

def generate_exif():
    brand, model = random_device()
    dt = random_datetime()

    dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")

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
        piexif.ExifIFD.FNumber: (random.randint(17, 22), 10),  # f/1.7–f/2.2
        piexif.ExifIFD.ExposureTime: (1, random.randint(30, 500)),
        piexif.ExifIFD.ISOSpeedRatings: random.choice([50, 100, 200, 400]),
        piexif.ExifIFD.FocalLength: (random.randint(3, 7), 1),
    }

    gps_ifd = random_gps()

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
    }

    return piexif.dump(exif_dict)


# ====== ОБРАБОТКА ======

def process_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")

    # полностью удаляем старые метаданные
    data = list(img.getdata())
    clean_img = Image.new(img.mode, img.size)
    clean_img.putdata(data)

    exif_bytes = generate_exif()

    out = io.BytesIO()
    clean_img.save(out, "jpeg", exif=exif_bytes, quality=95)
    return out.getvalue()


# ====== ИМЯ ФАЙЛА ======

def random_phone_filename():
    dt = random_datetime()
    return f"IMG_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
