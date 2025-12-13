import sys, os

APP_VERSION = "v1.4 - 2025"
APP_TITLE   = "Phần mềm chuyển đổi ảnh qua POI HSL " + APP_VERSION
APP_COMPANY = "Happy Smart Light"

# ====================
# App info
# Version update: v1.3 - Dec 2025
# Changelog:
# - Thêm nút cài đặt ARGB
# - Cải tiến giao diện chọn số mắt LED
# Version update: v1.4 - Dec 2025
# Changelog:
# - Thêm tính năng gửi nhiều ảnh đến ARGB với preset tăng dần
# - Sửa lỗi nhỏ giao diện nhìn rỏ hơn
# ====================
# Các gói cài đặt phụ thuộc:
# pip install Pillow PySide6 requests zeroconf
# Build command:
# cmd build app: pyinstaller --onefile --windowed  --icon assets/icon.ico   --add-data "assets;assets"  main.py


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)
