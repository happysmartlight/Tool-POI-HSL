import sys
import os
import socket
import json
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import requests
from zeroconf import ServiceBrowser, Zeroconf
import threading

from PIL import Image
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

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
# cmd build app: pyinstaller --onefile --windowed --icon=icon.ico     --add-data "hsl_logo.png;."  --add-data "favicon.ico;."   --add-data "qrcode_with_logo.png;."     tool.py


APP_VERSION = "v1.4 - 2025"
APP_TITLE   = "Phần mềm chuyển đổi ảnh qua POI HSL " + APP_VERSION
APP_COMPANY = "Happy Smart Light"

# ====================
# Resource path (cho PyInstaller)
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS   # Thư mục tạm khi chạy EXE
    except Exception:
        base_path = os.path.abspath(".")  # Khi chạy file .py

    return os.path.join(base_path, relative_path)

class PixelPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.grid = True  # bật/tắt lưới pixel
        self.setAutoFillBackground(True)  # Cho phép Qt tự tô nền theo system palette

    def setImage(self, qimg: QImage):
        self.image = qimg
        self.update()

    def clear(self):
        """Xóa ảnh hiện tại"""
        self.image = None
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)

        # --- Không có ảnh: vẽ background theo palette hệ thống ---
        if self.image is None:
            # Lấy màu nền hệ thống
            pal = self.palette()
            bg = pal.color(QPalette.Window)
            painter.fillRect(self.rect(), bg)

            # Vẽ text hướng dẫn ở giữa
            painter.setPen(pal.color(QPalette.WindowText))
            painter.setFont(QFont("Arial", 12))

            text = "Khu vực hiển thị ảnh xem trước khi quay Poi"
            rect = self.rect()
            painter.drawText(rect, Qt.AlignCenter, text)
            return

        # --- Có ảnh: vẽ ảnh pixel ---
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = self.width()
        h = self.height()

        img_w = self.image.width()
        img_h = self.image.height()

        px = min(w // img_w, h // img_h)

        offset_x = (w - img_w * px) // 2
        offset_y = (h - img_h * px) // 2

        for y in range(img_h):
            for x in range(img_w):
                color = QColor(self.image.pixel(x, y))
                painter.fillRect(
                    offset_x + x * px,
                    offset_y + y * px,
                    px,
                    px,
                    color
                )

                if self.grid and px >= 4:
                    painter.setPen(QColor(40, 40, 40))
                    painter.drawRect(
                        offset_x + x * px,
                        offset_y + y * px,
                        px,
                        px
                    )

        painter.end()


# ====================

class PixelIndexBar(QWidget):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.setMinimumHeight(40)

    def setCount(self, n):
        self.count = n
        self.update()

    def paintEvent(self, event):
        if self.count <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # === Style chung ===
        painter.setPen(QPen(QColor(180, 180, 180), 2))
        painter.setBrush(QColor(30, 30, 30))
        painter.drawRoundedRect(5, 5, w-10, h-10, 8, 8)

        # ==== Các mốc LED ====
        led_start = 1
        led_mid   = self.count // 2
        led_end   = self.count

        # ==== Chia đều chiều ngang cho 4 nhãn ====
        sections = 4
        x_positions = [
            w * (0.5 / sections),   # MẠCH ARGB HSL
            w * (1.5 / sections),   # LED 1
            w * (2.5 / sections),   # LED MID
            w * (3.5 / sections),   # LED END
        ]
        y = h // 2 + 5

        # Font đẹp
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))

        arrow = "➜"

        # ==== Vẽ text ====
        painter.drawText(int(x_positions[0] - 50), y, "|| MẠCH ARGB HSL ||")
        painter.drawText(int(x_positions[1] - 20), y, f"LED {led_start} {arrow}")
        painter.drawText(int(x_positions[2] - 30), y, f"{arrow} LED {led_mid} {arrow}")
        painter.drawText(int(x_positions[3] - 20), y, f"{arrow} LED {led_end}")

        painter.end()



class BMPConverter(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("favicon.ico"))

        screen = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        # Resize theo tỉ lệ
        win_w = int(screen_width * 0.60)
        win_h = int(screen_height * 0.90)
        self.resize(win_w, win_h)

        # Căn giữa màn hình
        geo = self.frameGeometry()
        geo.moveCenter(screen.center())
        self.move(geo.topLeft())
        # ==== biến lưu trữ ====
        self.input_path = None
        self.loaded_image = None
        self.preview_qpix = None

        # ==== layout chính ====
        main = QVBoxLayout(self)

        # ==== menu ====
        self._make_menu()

        # ==== Nhóm ưu tiên: Pixel LED / Số lượng Pixel ==== 
        grp_pixel = QGroupBox("🔧 Cấu hình Pixel LED")
        layout_pixel = QVBoxLayout(grp_pixel)

        # --- Hàng nhập số pixel ---
        row_pixel = QHBoxLayout()
        row_pixel.addWidget(QLabel("Pixel LEDs POI (15-72):"))

        self.entry_width = QLineEdit("72")
        self.entry_width.setFixedWidth(80)
        row_pixel.addWidget(self.entry_width)
        row_pixel.addStretch(1)

        layout_pixel.addLayout(row_pixel)

        # --- Ghi chú về chất lượng ảnh ---
        note = QLabel(
            "<i>● Số lượng pixel càng cao → hình ảnh hiển thị càng chi tiết và mượt.</i><br>"
        )
        note.setWordWrap(True)
        palette = self.palette()
        text_color = palette.color(QPalette.WindowText)
        note.setStyleSheet(f"color: {text_color.name()}; font-size: 12px;")

        layout_pixel.addWidget(note)
        # ==== Nhóm Ảnh / Batch (group lớn) ====
        grp_image = QGroupBox("🖼 Công cụ chuyển Ảnh")

        layout_img = QHBoxLayout(grp_image)

        # ======== GROUP TRÁI: XỬ LÝ 1 ẢNH ========
        grp_single = QGroupBox("📦 Xử lý 1 ảnh")
        layout_left = QVBoxLayout(grp_single)

        row_buttons = QHBoxLayout()
        btn_open = QPushButton("📁 Chọn ảnh...")
        btn_open.clicked.connect(self.open_image)
        row_buttons.addWidget(btn_open)

        btn_save = QPushButton("💾 Lưu tệp ảnh POI ...")
        btn_save.clicked.connect(self.save_as_bmp)
        row_buttons.addWidget(btn_save)

        layout_left.addLayout(row_buttons)
        self.lbl_info = QLabel("Chưa tải/chọn ảnh.")
        layout_left.addWidget(self.lbl_info)

        layout_img.addWidget(grp_single, stretch=1)

        # ======== GROUP PHẢI: BATCH ========
        grp_multi = QGroupBox("📦 Chuyển nhiều ảnh")
        layout_right = QVBoxLayout(grp_multi)
        layout_right.setAlignment(Qt.AlignTop)

        btn_multi = QPushButton("✨ Chuyển nhiều ảnh…")
        btn_multi.clicked.connect(self.convert_multiple)
        layout_right.addWidget(btn_multi)

        # --- Ghi chú về batch tool ---
        note_multi = QLabel(
            "<i>● Sau khi chuyển đổi, ảnh sẽ được lưu vào thư mục bạn chọn.</i>"
        )
        note_multi.setWordWrap(True)
        palette = self.palette()
        text_color = palette.color(QPalette.WindowText)
        note_multi.setStyleSheet(f"color: {text_color.name()}; font-size: 12px;")

        layout_right.addWidget(note_multi)

        layout_img.addWidget(grp_multi, stretch=1)

        # ============================================
        # ==== ĐẶT 2 GROUP NẰM NGANG ====
        # ============================================
        top_row = QHBoxLayout()
        top_row.addWidget(grp_pixel, stretch=1)
        top_row.addWidget(grp_image, stretch=3)

        main.addLayout(top_row)



        # ==== Nhóm ARGB / LED tách 2 nhóm nhỏ ==== 
        grp_argb_main = QGroupBox("🌐 Mạch ARGB / LED")
        main.addWidget(grp_argb_main)
        layout_argb_main = QHBoxLayout(grp_argb_main)

        # --- Nhóm 1: Chọn mạch + gửi ảnh ---
        grp_mach = QGroupBox("Chọn / Gửi ARGB")
        layout_mach = QHBoxLayout(grp_mach)

        layout_mach.addWidget(QLabel("Chọn/mạch ARGB:"))
        self.combo_ip = QComboBox()
        self.combo_ip.setEditable(True)
        self.combo_ip.setMinimumWidth(200)
        layout_mach.addWidget(self.combo_ip)

        btn_scan = QPushButton("🔍 Tìm ARGB")
        btn_scan.clicked.connect(self.scan_argb_mdns)
        layout_mach.addWidget(btn_scan)

        btn_send = QPushButton("📤 Gửi ảnh preview")
        btn_send.clicked.connect(self.send_to_argb)
        layout_mach.addWidget(btn_send)

        btn_sends = QPushButton("📤 Gửi nhiều ảnh")
        def on_send_multiple():
            # Xóa hình hiển thị
            self.lbl_preview.clear()
            # Gọi hàm gửi nhiều ảnh
            self.send_multiple_to_argb()

        btn_sends.clicked.connect(on_send_multiple)
        layout_mach.addWidget(btn_sends)

        layout_mach.addStretch(1)
        grp_mach.setLayout(layout_mach)
        layout_argb_main.addWidget(grp_mach, stretch=2)  # chiếm phần lớn

        # --- Nhóm 2: Nút điều khiển LED ---
        grp_control = QGroupBox("Điều khiển LED")
        layout_control = QHBoxLayout(grp_control)

        btn_settings = QPushButton("⚙️ Cài đặt")
        btn_settings.clicked.connect(self.settings_led)
        layout_control.addWidget(btn_settings)

        btn_off = QPushButton("💡 Tắt LED")
        btn_off.clicked.connect(self.turn_off_led)
        layout_control.addWidget(btn_off)

        btn_sync = QPushButton("🔗 Đồng bộ Mạch POI")
        btn_sync.clicked.connect(self.sync_poi)
        layout_control.addWidget(btn_sync)

        layout_control.addStretch(1)
        grp_control.setLayout(layout_control)
        layout_argb_main.addWidget(grp_control, stretch=1)  # chiếm ít hơn



        # ==== vùng preview ====
        frame = QFrame()
        frame.setStyleSheet("border:1px solid gray;")
        main.addWidget(frame, 1)

        #==== index bar ====
        frm_layout = QVBoxLayout(frame)
        self.index_bar = PixelIndexBar()
        self.index_bar.setFixedHeight(30)
        frm_layout.addWidget(self.index_bar)

        self.lbl_preview = PixelPreview()
        frm_layout.addWidget(self.lbl_preview)



        # ==== footer ====
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0,0,0,0)
        footer_layout.setSpacing(10)

        # Logo HSL
        pixmap_hsl = QPixmap(resource_path("hsl_logo.png")).scaledToWidth(80)
        lbl_logo_hsl = QLabel()
        lbl_logo_hsl.setPixmap(pixmap_hsl)
        lbl_logo_hsl.setAlignment(Qt.AlignVCenter)

        # Logo thứ 2
        pixmap_logo2 = QPixmap(resource_path("qrcode_with_logo.png")).scaledToWidth(80)
        lbl_logo2 = QLabel()
        lbl_logo2.setPixmap(pixmap_logo2)
        lbl_logo2.setAlignment(Qt.AlignVCenter)

        # Text
        lbl_text = QLabel(
            "📝 Lưu ý: Ảnh được crop chính giữa và resize theo kích thước thanh POI.<br>"
            "📌 Dùng cho <b>ARGB Happy Smart Light</b>, chuyên biệt cho <b>POI LED</b>.<br><br>"
            "💬 Zalo: <a href='https://zalo.me/0784140494'>0784140494</a><br>"
            "🌐 Website: <a href='https://happysmartlight.com/'>https://happysmartlight.com/</a>"
        )
        lbl_text.setTextFormat(Qt.RichText)
        lbl_text.setWordWrap(True)
        lbl_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Thêm các widget vào layout
        footer_layout.addWidget(lbl_logo_hsl)
        footer_layout.addWidget(lbl_logo2)
        footer_layout.addWidget(lbl_text, stretch=1)

        main.addWidget(footer_widget)

        # ==== nút thoát ====
        btn_quit = QPushButton("❌ Thoát")
        btn_quit.clicked.connect(self.close)
        main.addWidget(btn_quit)

    # ====================
    # Mở trang cài đặt ARGB
    def settings_led(self):
        # Lấy IP từ combobox
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Lỗi", "Không có IP để mở trang Cài đặt.")
            return

        QDesktopServices.openUrl(QUrl(f"http://{ip}/"))

    # ====================
    # Đồng bộ POI (chưa implement)
    def sync_poi(self):
        """
        Hàm đồng bộ các mạch POI.
        Hiện tại chỉ thông báo đang được xây dựng.
        """
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "🚧 Tính năng đang xây dựng",
            "Tính năng Đồng bộ các Mạch POI hiện đang được xây dựng. Vui lòng thử lại sau."
        )

    # ====================
    # Tắt LED ARGB
    def turn_off_led(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        try:
            url_state = f"http://{ip}/json/state"
            json_payload = {
                "on": False  # Tắt toàn bộ LED
            }
            r = requests.post(url_state, json=json_payload, timeout=3)
            if r.status_code == 200:
                QMessageBox.information(self, "OK", "Đã tắt LED ARGB thành công!")
            else:
                QMessageBox.warning(self, "Lỗi", f"Tắt LED thất bại! HTTP {r.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tắt LED:\n{e}")


    # ====================
    # Scan ARGB qua mDNS (không cần subnet)
    # ====================
    def scan_argb_mdns(self):
        try:
            from zeroconf import Zeroconf, ServiceBrowser
        except ImportError:
            QMessageBox.warning(
                self, "Thiếu thư viện",
                "Bạn cần cài đặt zeroconf:\n\npip install zeroconf"
            )
            return

        self.combo_ip.clear()
        self.combo_ip.addItem("Đang quét ARGB...")
        QApplication.processEvents()

        found_devices = {}  # ip -> name

        class WledListener:
            def add_service(self, zeroconf, type, name):
                info = zeroconf.get_service_info(type, name)
                if info:
                    ip_bytes = info.addresses[0]
                    ip = ".".join(str(b) for b in ip_bytes)

                    if ip not in found_devices:
                        try:
                            r = requests.get(f"http://{ip}/json", timeout=0.25)
                            j = r.json()
                            if "info" in j and j["info"].get("brand") == "ARGB":
                                dev_name = j["info"].get("name", "Unnamed")
                                found_devices[ip] = dev_name
                                print(f"[mDNS] Phát hiện ARGB HSL: {ip} ({dev_name})")
                        except Exception as e:
                            print(f"[mDNS] Lỗi kiểm tra JSON từ {ip}: {e}")

            def remove_service(self, zeroconf, type, name):
                pass
            def update_service(self, zeroconf, type, name):
                pass

        zeroconf = Zeroconf()
        listener = WledListener()
        browser = ServiceBrowser(zeroconf, "_wled._tcp.local.", listener)

        def finish_scan():
            zeroconf.close()
            self.combo_ip.clear()
            if found_devices:
                for ip, dev_name in found_devices.items():
                    # hiển thị Tên (IP)
                    self.combo_ip.addItem(f"{dev_name} ({ip})", userData=ip)
            else:
                self.combo_ip.addItem("Không tìm thấy mạch ARGB HSL")

        QTimer.singleShot(2000, finish_scan)



    # ====================
    # Contact
    # ====================
    def show_contact(self):
        text = (
            '<b>Zalo:</b> '
            '<a href="https://zalo.me/0784140494">0784140494 (Bằng)</a><br><br>'
            '<b>Website:</b> '
            '<a href="https://happysmartlight.com/">https://happysmartlight.com/</a>'
        )

        box = QMessageBox(self)
        box.setWindowTitle("Liên hệ")
        box.setTextFormat(Qt.RichText)     # cho phép HTML
        box.setTextInteractionFlags(Qt.TextBrowserInteraction)  # cho phép click
        box.setText(text)
        box.exec()

    # ====================
    # Menu
    # ====================
    def _make_menu(self):
        bar = QMenuBar()

        # ---- Giới thiệu ----
        menu_about = QMenu("Giới thiệu", bar)
        act_info = QAction("Thông tin phần mềm", self)
        act_info.triggered.connect(self.show_about)
        menu_about.addAction(act_info)
        bar.addMenu(menu_about)

        # ---- Liên hệ ----
        menu_contact = QMenu("Liên hệ", bar)
        act_contact = QAction("Thông tin liên hệ", self)
        act_contact.triggered.connect(self.show_contact)
        menu_contact.addAction(act_contact)
        bar.addMenu(menu_contact)

        self.layout().setMenuBar(bar)


    # ====================
    # About
    # ====================
    def show_about(self):
        QMessageBox.information(
            self,
            "Giới thiệu",
            f"{APP_TITLE}\n\n"
            f"Thiết kế bởi {APP_COMPANY}\n"
            f"Phiên bản: {APP_VERSION}\n\n"
            f"Chúc bạn một ngày tốt lành!"
        )

    # ====================
    # Logic crop + resize
    # ====================
    def _center_crop_square(self, im: Image.Image) -> Image.Image:
        w, h = im.size
        if w == h:
            return im
        if w > h:
            left = (w - h)//2
            return im.crop((left, 0, left + h, h))
        else:
            top = (h - w)//2
            return im.crop((0, top, w, top + w))

    def _convert_to_square_rgb(self, width: int, img: Image.Image):
        im_sq = self._center_crop_square(img)
        im_sq = im_sq.resize((width, width), Image.LANCZOS)
        return im_sq.convert("RGB")

    def _get_target_width(self):
        try:
            w = int(self.entry_width.text())
        except:
            # Reset về 72 khi sai kiểu dữ liệu
            self.entry_width.setText("72")
            self._warn_width("Giá trị không hợp lệ! Vui lòng nhập số.")
            self.entry_width.setStyleSheet("")
            return 72

        if w < 14 or w > 72:
            # Reset về 72 khi sai kiểu dữ liệu
            self.entry_width.setText("72")
            self._warn_width("Giá trị phải nằm trong khoảng 15 đến 72 pixel.")
            self.entry_width.setStyleSheet("")
            return 72

        # reset màu
        self.entry_width.setStyleSheet("")
        return w

    def _warn_width(self, msg):
        self.entry_width.setStyleSheet("background:#ffb1b1;")
        QMessageBox.warning(
            self, 
            "Sai thông số",
            f"<font color='red'><b>{msg}</b></font><br><br>"
            "Gợi ý: POI HSL đề xuất sử dụng từ 15 → 72 pixel."
        )


    # ====================
    # Open image
    # ====================
    def open_image(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh",
            filter="Tất cả ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
        )
        if not file:
            return
        try:
            img = Image.open(file)
            self.input_path = file
            self.loaded_image = img.copy()
            img.close()

            self.lbl_info.setText(
                f"Đã tải: {os.path.basename(file)} — kích thước {self.loaded_image.width}x{self.loaded_image.height}"
            )
            self.preview_convert()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở ảnh:\n{e}")

    # ====================
    # Preview
    # ====================
    def preview_convert(self):
        if self.loaded_image is None:
            return

        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)
        qimg = self._image_to_qpixmap(im2).toImage()
        self.lbl_preview.setImage(qimg)
        self.index_bar.setCount(im2.width)



    def _image_to_qpixmap(self, im: Image.Image):
        data = im.tobytes("raw", "RGB")
        qimg = QImage(data, im.width, im.height, im.width * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    # ====================
    # Save BMP (kèm dung lượng + khuyến nghị)
    # ====================
    def save_as_bmp(self):
        if self.loaded_image is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng mở ảnh trước.")
            return

        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)

        default_name = os.path.splitext(os.path.basename(self.input_path))[0] + ".bmp"

        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Lưu BMP",
            default_name,
            "BMP files (*.bmp)"
        )      
        if not path:
            return

        if not path.lower().endswith(".bmp"):
            path += ".bmp"

        try:
            im2.save(path, "BMP")

            # ==== size ====
            size_bytes = os.path.getsize(path)
            
            if size_bytes < 1024:
                human = f"{size_bytes} bytes"
            elif size_bytes < 1024*1024:
                human = f"{size_bytes/1024:.1f} KB"
            else:
                human = f"{size_bytes/1024/1024:.2f} MB"

            # ==== đánh giá POI ====
            if size_bytes < 63 * 1024:
                comment = "<font color='green'><b>Sử dụng tốt cho POI HSL ✓</b></font>"
            else:
                comment = "<font color='red'><b>⚠ Không phù hợp cho POI HSL (file quá lớn)</b></font>"

            msg = QMessageBox(self)
            msg.setWindowTitle("Đã lưu")
            msg.setText(
                f"Đã lưu: {path}<br>"
                f"Dung lượng: <b>{human}</b><br><br>"
                f"{comment}"
            )
            msg.setIcon(QMessageBox.Information)

            btn_open = msg.addButton("Mở thư mục", QMessageBox.ActionRole)
            btn_ok    = msg.addButton("Đóng", QMessageBox.AcceptRole)

            msg.exec()

            if msg.clickedButton() == btn_open:
                folder = os.path.dirname(path)
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


    # ====================
    # Convert multiple files
    # ====================
    def convert_multiple(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn nhiều ảnh",
            filter="Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
        )
        if not files:
            return

        w = self._get_target_width()
        if not w:
            return

        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Chọn thư mục lưu BMP"
        )
        if not out_dir:
            return

        report = []   # danh sách thông tin

        for f in files:
            try:
                im = Image.open(f)
                im2 = self._convert_to_square_rgb(w, im)
                name = os.path.splitext(os.path.basename(f))[0] + ".bmp"
                out_path = os.path.join(out_dir, name)
                im2.save(out_path, "BMP")

                # ==== size ====
                size_bytes = os.path.getsize(out_path)
                
                # format đẹp
                if size_bytes < 1024:
                    sz = f"{size_bytes} bytes"
                elif size_bytes < 1024*1024:
                    sz = f"{size_bytes/1024:.1f} KB"
                else:
                    sz = f"{size_bytes/1024/1024:.2f} MB"

                # đánh giá
                if size_bytes < 63 * 1024:
                    status = "<font color='green'>✓ Hợp lệ cho POI</font>"
                else:
                    status = "<font color='red'>⚠ Quá lớn, không phù hợp</font>"

                report.append(f"<b>{name}</b> ({sz}) — {status}")

            except Exception as e:
                report.append(f"<b>{os.path.basename(f)}</b> — <font color='red'>Lỗi: {e}</font>")

            html = "<br>".join(report)

            msg = QMessageBox(self)
            msg.setWindowTitle("Hoàn thành")
            msg.setTextFormat(Qt.RichText)
            msg.setText(
                f"Đã xử lý {len(files)} ảnh<br><br>"
                f"Lưu tại:<br><b>{out_dir}</b><br><br>"
                f"{html}"
            )

            # thêm button mở thư mục
            btn_open = msg.addButton("Mở thư mục", QMessageBox.ActionRole)
            msg.addButton("Đóng", QMessageBox.AcceptRole)

            msg.exec()

            if msg.clickedButton() == btn_open:
                QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))

    # ====================
    # Gửi BMP đến ARGB
    # ====================
    # Gửi BMP đến ARGB và cập nhật trạng thái
    def send_to_argb(self):
        if self.loaded_image is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng mở ảnh trước.")
            return

        # Lấy IP từ userData của combobox
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # Lưu file tạm trước khi gửi
        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)
        import tempfile
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
        im2.save(tmp_file.name, "BMP")
        tmp_file.close()

        import os
        output_name = os.path.basename(tmp_file.name)  # chỉ lấy tmpf2cwciv6.bmp

        try:
            import requests

            # --- Bước 1: Upload BMP ---
            url_upload = f"http://{ip}/upload"
            with open(tmp_file.name, "rb") as f:
                files = {"data": f}
                r = requests.post(url_upload, files=files, timeout=5)

            if r.status_code == 200:
                QMessageBox.information(self, "Hoàn tất", f"Đã gửi BMP đến {ip} thành công!")

                # --- Bước 2: POST JSON cập nhật LED ---
                url_state = f"http://{ip}/json/state"
                json_payload = {
                    "on": True,          # bật toàn bộ LED
                    "bri": 100,          # độ sáng tổng thể
                    "seg": [
                        {
                            "id": 0,
                            "on": True,
                            "bri": 60,               # độ sáng segment
                            "n": f"/{output_name}",  # tên BMP vừa upload
                            "fx": 48                 # hiệu ứng
                        }
                    ],
                    "psave": 1,  # lưu cấu hình ưu tiên
                }
                try:
                    r2 = requests.post(url_state, json=json_payload, timeout=3)
                    if r2.status_code == 200:
                        print(f"[INFO] Segment 0 cập nhật thành công: {r2.json()}")
                    else:
                        print(f"[WARN] POST JSON thất bại HTTP {r2.status_code}")
                except Exception as e2:
                    print(f"[ERROR] Không thể cập nhật JSON: {e2}")

            else:
                msg = QMessageBox(self)
                msg.setWindowTitle("Lỗi")
                msg.setText(f"Gửi không thành công! HTTP {r.status_code}")
                btn_open = msg.addButton("Mở mã PIN ARGB", QMessageBox.ActionRole)
                msg.addButton("Đóng", QMessageBox.RejectRole)
                msg.exec()
                if msg.clickedButton() == btn_open:
                    QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể gửi BMP:\n{e}")
        finally:
            import os
            os.unlink(tmp_file.name)


    # ====================
    # Gửi nhiều ảnh đến ARGB (Preset tăng dần)
    def send_multiple_to_argb(self):
        """
        Mở dialog chọn nhiều ảnh, gửi lần lượt đến ARGB,
        lưu Preset tăng dần và xử lý HTTP 401 (PIN ARGB) với popup gửi lại.
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PIL import Image
        import tempfile, os, requests

        # 3️⃣ Lấy IP mạch
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # 4️⃣ Lấy width target
        w = self._get_target_width()
        if not w:
            return

        # 1️⃣ Chọn nhiều file ảnh
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh để gửi ARGB", "", "Images (*.png *.jpg *.bmp)"
        )
        if not file_paths:
            return

        # 2️⃣ Load ảnh PIL
        try:
            images = [Image.open(p) for p in file_paths]
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load ảnh: {e}")
            return

        # 5️⃣ Gửi lần lượt từng ảnh
        for idx, img in enumerate(images, start=1):
            while True:  # Vòng lặp để hỗ trợ "Gửi lại"
                try:
                    # Chuyển sang vuông RGB 24-bit
                    bmp_image = self._convert_to_square_rgb(w, img)

                    # Lưu tạm
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
                    bmp_image.save(tmp_file.name, "BMP")
                    tmp_file.close()
                    output_name = os.path.basename(tmp_file.name)

                    # --- Upload BMP ---
                    url_upload = f"http://{ip}/upload"
                    with open(tmp_file.name, "rb") as f:
                        files = {"data": f}
                        r = requests.post(url_upload, files=files, timeout=5)

                    if r.status_code == 200:
                        print(f"[INFO] Upload ảnh {idx} thành công")
                        break  # Upload thành công, thoát vòng while

                    elif r.status_code == 401:
                        # Nếu bị khóa PIN, hiển thị popup
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Khóa PIN ARGB")
                        msg.setText(f"Upload ảnh {idx} thất bại: HTTP 401 (khóa mã PIN)")

                        btn_open_pin = msg.addButton("Mở mã PIN ARGB", QMessageBox.ActionRole)
                        btn_retry = msg.addButton("Gửi lại", QMessageBox.AcceptRole)
                        msg.addButton("Đóng", QMessageBox.RejectRole)

                        msg.exec()

                        clicked = msg.clickedButton()
                        if clicked == btn_open_pin:
                            QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
                            continue  # quay lại vòng while, user có thể mở PIN và bấm Gửi lại
                        elif clicked == btn_retry:
                            continue  # gửi lại ảnh hiện tại
                        else:
                            print(f"[WARN] Người dùng bỏ qua ảnh {idx}")
                            break  # thoát vòng while, bỏ qua ảnh

                    else:
                        print(f"[WARN] Upload ảnh {idx} thất bại HTTP {r.status_code}")
                        break  # bỏ qua ảnh này

                except Exception as e:
                    print(f"[ERROR] Gửi ảnh {idx} thất bại: {e}")
                    break  # bỏ qua ảnh này

                finally:
                    if os.path.exists(tmp_file.name):
                        os.unlink(tmp_file.name)

            # --- POST JSON cập nhật LED và lưu Preset ---
            try:
                url_state = f"http://{ip}/json/state"
                json_payload = {
                    "on": True,
                    "bri": 100,
                    "seg": [
                        {
                            "id": 0,
                            "on": True,
                            "bri": 60,
                            "n": f"/{output_name}",
                            "fx": 48
                        }
                    ],
                    "psave": idx  # Preset tăng dần
                }
                r2 = requests.post(url_state, json=json_payload, timeout=3)
                if r2.status_code == 200:
                    print(f"[INFO] Ảnh {idx} cập nhật thành công: Preset {idx}")
                else:
                    print(f"[WARN] POST JSON ảnh {idx} thất bại HTTP {r2.status_code}")
            except Exception as e2:
                print(f"[ERROR] Không thể cập nhật JSON ảnh {idx}: {e2}")

        QMessageBox.information(self, "Hoàn tất", f"Đã gửi {len(images)} ảnh tới ARGB thành công!")



# ====================
# RUN
# ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = resource_path("favicon.ico")
    app.setWindowIcon(QIcon(icon_path))   # Icon ứng dụng
    win = BMPConverter()
    win.setWindowIcon(QIcon(icon_path))   # Icon cửa sổ (nếu muốn)
    win.show()
    sys.exit(app.exec())
