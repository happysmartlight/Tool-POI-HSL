from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPalette, QFont, QPen, QImage, QFontMetrics
from PySide6.QtCore import Qt, QRect

class PixelPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.grid = True
        self.setAutoFillBackground(True)

    def setImage(self, qimg: QImage):
        self.image = qimg
        self.update()

    def clear(self):
        self.image = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        pal = self.palette()

        # ==========================
        # CHƯA CÓ ẢNH
        # ==========================
        if self.image is None:
            painter.fillRect(self.rect(), pal.color(QPalette.Window))
            painter.setPen(pal.color(QPalette.WindowText))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Khu vực hiển thị ảnh xem trước khi quay Poi"
            )
            return

        # ==========================
        # CÓ ẢNH → VẼ PIXEL
        # ==========================
        painter.setRenderHint(QPainter.Antialiasing, False)

        w, h = self.width(), self.height()
        img_w, img_h = self.image.width(), self.image.height()

        px = min(w // img_w, h // img_h)
        ox = (w - img_w * px) // 2
        oy = (h - img_h * px) // 2

        for y in range(img_h):
            for x in range(img_w):
                color = QColor(self.image.pixel(x, y))
                painter.fillRect(ox + x * px, oy + y * px, px, px, color)

                if self.grid and px >= 4:
                    painter.setPen(QColor(40, 40, 40))
                    painter.drawRect(ox + x * px, oy + y * px, px, px)

        # # ==========================
        # # OVERLAY THÔNG TIN ẢNH
        # # (1 dòng – Giữa – Dưới ảnh – Không đè)
        # # ==========================
        # src_name = getattr(self, "source_name", "Ảnh gốc")

        # info_text = f"{src_name}  →  POI Pixel Preview ({img_w} x {img_h} px)"

        # padding = 8
        # margin = 10
        # font = QFont("Arial", 7)
        # fm = QFontMetrics(font)

        # text_w = fm.horizontalAdvance(info_text)
        # text_h = fm.height()

        # rect_w = text_w + padding * 2
        # rect_h = text_h + padding * 2

        # # 🔥 CANH GIỮA NGANG
        # overlay_x = (self.width() - rect_w) // 2

        # # 🔥 NẰM NGAY DƯỚI ẢNH
        # overlay_y = oy + img_h * px + margin

        # # Nếu không đủ chỗ dưới → đẩy lên trên ảnh
        # if overlay_y + rect_h > self.height():
        #     overlay_y = max(0, oy - rect_h - margin)

        # info_rect = QRect(
        #     overlay_x,
        #     overlay_y,
        #     rect_w,
        #     rect_h
        # )

        # # nền mờ
        # painter.setBrush(QColor(0, 0, 0, 160))
        # painter.setPen(Qt.NoPen)
        # painter.drawRoundedRect(info_rect, 6, 6)

        # # text
        # painter.setPen(Qt.white)
        # painter.setFont(font)
        # painter.drawText(
        #     info_rect.adjusted(padding, padding, -padding, -padding),
        #     Qt.AlignLeft | Qt.AlignVCenter,
        #     info_text
        # )



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
        w, h = self.width(), self.height()

        painter.setPen(QPen(QColor(180,180,180),2))
        painter.setBrush(QColor(30,30,30))
        painter.drawRoundedRect(5,5,w-10,h-10,8,8)

        led_start, led_mid, led_end = 1, self.count//2, self.count
        xs = [w*(0.5/4), w*(1.5/4), w*(2.5/4), w*(3.5/4)]
        y = h//2 + 5
        font = painter.font()
        font.setPointSize(12); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        arrow = "➜"

        painter.drawText(int(xs[0]-50), y, "|| MẠCH ARGB HSL ||")
        painter.drawText(int(xs[1]-20), y, f"LED {led_start} {arrow}")
        painter.drawText(int(xs[2]-30), y, f"{arrow} LED {led_mid} {arrow}")
        painter.drawText(int(xs[3]-20), y, f"{arrow} LED {led_end}")
