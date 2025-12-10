import sys
import os
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
        self.resize(820, 600)

        self.input_path = None
        self.loaded_image = None
        self.preview_qpix = None

        # ==== layout chính ====
        main = QVBoxLayout(self)

        # ==== menu ====
        self._make_menu()

        # ==== controls ====
        ctl = QHBoxLayout()
        main.addLayout(ctl)

        btn_open = QPushButton("Mở ảnh...")
        btn_open.clicked.connect(self.open_image)
        ctl.addWidget(btn_open)

        ctl.addWidget(QLabel("Chiều rộng (px, vuông):"))
        self.entry_width = QLineEdit("128")
        self.entry_width.setFixedWidth(80)
        ctl.addWidget(self.entry_width)

        btn_preview = QPushButton("Xem trước")
        btn_preview.clicked.connect(self.preview_convert)
        ctl.addWidget(btn_preview)

        btn_save = QPushButton("Lưu BMP 24-bit...")
        btn_save.clicked.connect(self.save_as_bmp)
        ctl.addWidget(btn_save)

        btn_multi = QPushButton("Chuyển nhiều ảnh...")
        btn_multi.clicked.connect(self.convert_multiple)
        ctl.addWidget(btn_multi)

        btn_quit = QPushButton("Thoát")
        btn_quit.clicked.connect(self.close)
        ctl.addWidget(btn_quit)

        ctl.addStretch(1)

        # === label thông tin ===
        self.lbl_info = QLabel("Chưa tải ảnh.")
        main.addWidget(self.lbl_info)

        # === vùng preview ===
        frame = QFrame()
        frame.setStyleSheet("border:1px solid gray;")
        main.addWidget(frame, 1)

        frm_layout = QVBoxLayout(frame)
        self.lbl_preview = QLabel("Chưa có ảnh.")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        frm_layout.addWidget(self.lbl_preview)

        # footer
        footer = QLabel("Lưu ý: Ảnh sẽ được crop chính giữa thành hình vuông rồi resize theo chiều rộng bạn nhập.")
        main.addWidget(footer)

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
            if w <= 0:
                raise Exception()
            return w
        except:
            QMessageBox.warning(self, "Lỗi", "Chiều rộng không hợp lệ.")
            return None

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
    # Save BMP
    # ====================
    def save_as_bmp(self):
        if self.loaded_image is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng mở ảnh trước.")
            return

        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)

        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu BMP",
            filter="BMP files (*.bmp)",
            )        
        if not path:
            return

        if not path.lower().endswith(".bmp"):
            path += ".bmp"

        try:
            im2.save(path, "BMP")
            QMessageBox.information(self, "OK", f"Đã lưu:\n{path}")
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

        count = 0
        for f in files:
            try:
                im = Image.open(f)
                im2 = self._convert_to_square_rgb(w, im)
                name = os.path.splitext(os.path.basename(f))[0] + ".bmp"
                out_path = os.path.join(out_dir, name)
                im2.save(out_path, "BMP")
                count += 1
            except Exception as e:
                print("Lỗi xử lý file:", f, e)

        QMessageBox.information(
            self,
            "Hoàn thành",
            f"Đã xử lý {count} ảnh\nLưu tại:\n{out_dir}"
        )


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
