# -*- coding: utf-8 -*-

import os
import random
import csv
import piexif

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_device():
    devices_dir = os.path.join(BASE_DIR, "devices")

    files = [f for f in os.listdir(devices_dir) if f.endswith(".csv")]
    file = random.choice(files)

    path = os.path.join(devices_dir, file)

    devices = []

    with open(path, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            manufacturer = row.get("manufacturer")
            model = row.get("model")

            if manufacturer and model:
                devices.append((manufacturer, model))

    return random.choice(devices)


def deg_to_dms(deg):
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m / 60) * 3600 * 100)

    return ((d, 1), (m, 1), (s, 100))


def generate_exif(lat, lon):
    manufacturer, model = load_device()

    zeroth_ifd = {
        piexif.ImageIFD.Make: manufacturer.encode(),
        piexif.ImageIFD.Model: model.encode(),
    }

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b'N' if lat >= 0 else b'S',
        piexif.GPSIFD.GPSLatitude: deg_to_dms(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: b'E' if lon >= 0 else b'W',
        piexif.GPSIFD.GPSLongitude: deg_to_dms(abs(lon)),
    }

    exif_dict = {
        "0th": zeroth_ifd,
        "GPS": gps_ifd,
    }

    return piexif.dump(exif_dict)
