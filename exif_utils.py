import random
import piexif
from datetime import datetime


def to_deg(value):
    d = int(value)
    m = int((value - d) * 60)
    s = int(((value - d) * 60 - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def generate_exif(lat, lon):
    now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")

    zeroth_ifd = {
        piexif.ImageIFD.Make: "Apple",
        piexif.ImageIFD.Model: "iPhone 13",
        piexif.ImageIFD.Software: "iOS 17.0",
        piexif.ImageIFD.DateTime: now,
    }

    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: now,
        piexif.ExifIFD.LensMake: "Apple",
        piexif.ExifIFD.LensModel: "iPhone 13 back camera 5.1mm f/1.6",
    }

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
        piexif.GPSIFD.GPSLatitude: to_deg(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
        piexif.GPSIFD.GPSLongitude: to_deg(abs(lon)),
    }

    exif_dict = {
        "0th": zeroth_ifd,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
    }

    return piexif.dump(exif_dict)
