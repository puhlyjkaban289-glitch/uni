import csv
import os
import random
from datetime import datetime, timedelta
import piexif


# ================== LOAD DEVICES ==================

def load_devices():
    base = "devices"
    devices = []

    for file in os.listdir(base):
        if file.endswith(".csv"):
            with open(os.path.join(base, file)) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    devices.append(row)

    if not devices:
        raise ValueError("Нет устройств")

    return devices


DEVICES = load_devices()


# ================== COORDS ==================

def load_coords(path="coords.csv"):
    coords = []
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                coords.append((float(row[0]), float(row[1])))
    return coords


COORDS = load_coords()


# ================== HELPERS ==================

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
    return dt.strftime("%Y:%m:%d %H:%M:%S")


# ================== EXIF ==================

def generate_exif():
    device = random.choice(DEVICES)
    lat, lon = random.choice(COORDS)

    dt = random_datetime()

    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: device["make"].encode(),
            piexif.ImageIFD.Model: device["model"].encode(),
            piexif.ImageIFD.Software: device["software"].encode(),
            piexif.ImageIFD.DateTime: dt.encode(),
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: dt.encode(),
            piexif.ExifIFD.DateTimeDigitized: dt.encode(),
            piexif.ExifIFD.LensModel: device["lens"].encode(),
            piexif.ExifIFD.ISOSpeedRatings: random.choice([50, 100, 200]),
            piexif.ExifIFD.FocalLength: (42, 10),
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude: to_deg(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude: to_deg(lon),
        },
    }

    return piexif.dump(exif_dict)