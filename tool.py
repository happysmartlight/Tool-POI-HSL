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


APP_TITLE   = "Phần mềm chuyển đổi ảnh qua POI HSL"
APP_VERSION = "v1.2 - 2025"
APP_COMPANY = "Happy Smart Light"



class BMPConverter(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("favicon.ico"))
        self.resize(820, 650)  # tăng chiều cao để thêm combobox scan

        self.input_path = None
        self.loaded_image = None
        self.preview_qpix = None

        # ==== layout chính ====
        main = QVBoxLayout(self)

        # ==== menu ====
        self._make_menu()

        # ==== controls chính ====
        ctl = QHBoxLayout()
        main.addLayout(ctl)

        btn_open = QPushButton("📁 Chọn ảnh...")
        btn_open.clicked.connect(self.open_image)
        ctl.addWidget(btn_open)

        ctl.addWidget(QLabel("🔧 Pixel POI (15-72):"))
        self.entry_width = QLineEdit("72")
        self.entry_width.setFixedWidth(80)
        ctl.addWidget(self.entry_width)

        btn_preview = QPushButton("👀 Xem trước")
        btn_preview.clicked.connect(self.preview_convert)
        ctl.addWidget(btn_preview)

        btn_save = QPushButton("💾 Lưu POI BMP...")
        btn_save.clicked.connect(self.save_as_bmp)
        ctl.addWidget(btn_save)

        btn_quit = QPushButton("❌ Thoát")
        btn_quit.clicked.connect(self.close)
        ctl.addWidget(btn_quit)

        ctl.addStretch(1)

        # ==== dòng tùy chọn đặc biệt ====
        ctl2 = QHBoxLayout()
        main.addLayout(ctl2)

        btn_multi = QPushButton("✨ Chuyển nhiều ảnh… (Batch)")
        btn_multi.clicked.connect(self.convert_multiple)
        ctl2.addWidget(btn_multi)

        ctl2.addStretch(1)

        # ==== combobox scan ARGB ====
        ctl3 = QHBoxLayout()
        main.addLayout(ctl3)

        self.combo_ip = QComboBox()
        self.combo_ip.setEditable(True)
        self.combo_ip.setMinimumWidth(200)
        ctl3.addWidget(QLabel("🌐 Chọn/mạch ARGB:"))
        ctl3.addWidget(self.combo_ip)


        btn_scan = QPushButton("🔍 Scan ARGB")
        btn_scan.clicked.connect(self.scan_wled_mdns)
        ctl3.addWidget(btn_scan)
        # ctl3.addStretch(1)

        btn_send = QPushButton("📤 Gửi BMP đến ARGB")
        btn_send.clicked.connect(self.send_to_wled)
        ctl3.addWidget(btn_send)

        # ==== label thông tin ====
        self.lbl_info = QLabel("Chưa tải ảnh.")
        main.addWidget(self.lbl_info)

        # ==== vùng preview ====
        frame = QFrame()
        frame.setStyleSheet("border:1px solid gray;")
        main.addWidget(frame, 1)

        frm_layout = QVBoxLayout(frame)
        self.lbl_preview = QLabel("Chưa có ảnh.")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        frm_layout.addWidget(self.lbl_preview)

        # ==== footer ====
        footer = QLabel(
            """
            <div style='text-align:center;'>
                📝 <b>Lưu ý:</b> Ảnh sẽ được crop chính giữa thành hình vuông rồi resize theo chiều rộng bạn nhập.<br><br>
                📌 Output được sử dụng cho phần cứng
                <b>ARGB của Happy Smart Light</b>,<br>
                chuyên biệt cho tính năng <b>Quay POI LED</b>.
            </div>
            """
        )
        footer.setTextFormat(Qt.RichText)
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        main.addWidget(footer)

    # ====================
    # Scan ARGB qua mDNS (không cần subnet)
    # ====================
    def scan_wled_mdns(self):
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
            self._warn_width("Giá trị không hợp lệ! Vui lòng nhập số.")
            return None

        if w < 15 or w > 72:
            self._warn_width("Giá trị phải nằm trong khoảng 15 đến 72 pixel.")
            return None

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
        qimg = self._image_to_qpixmap(im2)
        self.lbl_preview.setPixmap(
            qimg.scaled(
                self.lbl_preview.width(),
                self.lbl_preview.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

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
    def send_to_wled(self):
        if self.loaded_image is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng mở ảnh trước.")
            return

        # Lấy IP từ userData của combobox (không lấy toàn bộ text hiển thị)
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

        # Dùng requests để upload thay vì gọi curl ngoài
        try:
            import requests
            url = f"http://{ip}/upload"
            with open(tmp_file.name, "rb") as f:
                files = {"data": f}
                r = requests.post(url, files=files, timeout=3)

            if r.status_code == 200:
                QMessageBox.information(self, "Hoàn tất", f"Đã gửi BMP đến {ip} thành công!")
            else:
                msg = QMessageBox(self)
                msg.setWindowTitle("Lỗi")
                msg.setText(f"Gửi không thành công! HTTP {r.status_code}")
                # Thêm nút mở trang settings/sec
                btn_open = msg.addButton("Mở mã PIN ARGB", QMessageBox.ActionRole)
                msg.addButton("Đóng", QMessageBox.RejectRole)
                msg.exec()
                if msg.clickedButton() == btn_open:
                    QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể gửi BMP:\n{e}")
        finally:
            os.unlink(tmp_file.name)



# ====================
# RUN
# ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("favicon.ico"))   # <== bắt buộc
    win = BMPConverter()
    win.setWindowIcon(QIcon("favicon.ico"))   # nếu muốn
    win.show()
    sys.exit(app.exec())
