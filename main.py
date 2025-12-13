import sys, os, tempfile, requests, re
from PIL import Image
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QColorDialog

from config import APP_TITLE, APP_VERSION, APP_COMPANY, resource_path
from widgets import PixelPreview, PixelIndexBar
from image_utils import convert_to_square_rgb

class BMPConverter(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("favicon.ico"))

        # ==== Thiết lập kích thước cửa sổ ====
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

        # ==== màu LED theo chuẩn col[] ====
        self.col = [
            QColor(255, 0, 0),    # col[0] - Primary
            QColor(0, 0, 0),      # col[1] - Secondary
            QColor(64, 64, 64)    # col[2] - Tertiary
        ]
        self.color_buttons = []


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

        # ==== GROUP MÀU LED (COLOR WHEEL) ====
        grp_color = QGroupBox("🎨 Màu LED")
        layout_color = QVBoxLayout(grp_color)
        layout_color.setSpacing(6)

        labels = [
            "🎨 Màu chính",
            "🌑 Màu nền",
            "✨ Màu điểm nhấn"
        ]

        self.color_buttons = []
        self.color_previews = []

        for i, label in enumerate(labels):
            row = QHBoxLayout()
            row.setSpacing(6)

            # ===== NÚT CHỌN MÀU =====
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2b2b2b;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding-left: 8px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                }
            """)
            btn.clicked.connect(lambda _, x=i: self.pick_color(x))

            # ===== Ô HIỂN THỊ MÀU =====
            preview = QLabel()
            preview.setFixedSize(32, 30)
            preview.setStyleSheet("""
                background-color: black;
                border: 1px solid #666;
                border-radius: 4px;
            """)

            self.color_buttons.append(btn)
            self.color_previews.append(preview)

            row.addWidget(btn, 1)
            row.addWidget(preview, 0)

            layout_color.addLayout(row)

        layout_color.addStretch(1)


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
        top_row.addWidget(grp_color, stretch=1)   # 👈 BÁNH XE MÀU Ở GIỮA
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
        # Tự động load info khi chọn IP
        self.combo_ip.currentIndexChanged.connect(self.refresh_device_data)
        # self.combo_ip.currentIndexChanged.connect(self.load_preset_list)

        btn_scan = QPushButton("🔍 Tìm ARGB")
        btn_scan.clicked.connect(self.scan_argb_mdns)
        layout_mach.addWidget(btn_scan)

        btn_open = QPushButton("📁 Chọn ảnh...")
        btn_open.clicked.connect(self.open_image)
        layout_mach.addWidget(btn_open)

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
        main.addWidget(frame, 1)

        # ==== CHIA FRAME THÀNH 3 VÙNG ====
        layout_main = QHBoxLayout(frame)
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.setSpacing(10)

        # ==========================================================
        # ========== CỘT 1 – FN (GIỮ NGUYÊN) ========================
        # ==========================================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(8)


        # ---------- THÔNG TIN THIẾT BỊ (CHUYỂN SANG CỘT TRÁI) ----------
        lbl_info_title = QLabel("ℹ️ Thông tin thiết bị")
        lbl_info_title.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(lbl_info_title)

        self.lbl_device_info = QLabel("Chưa kết nối")
        self.lbl_device_info.setWordWrap(True)
        self.lbl_device_info.setMinimumHeight(70)
        self.lbl_device_info.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px;
                color: #ddd;
                font-size: 11px;
            }
        """)
        left_layout.addWidget(self.lbl_device_info)

        # ====== Đường phân cách ngang ======
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        left_layout.addWidget(line)

        # Các nút đồng bộ giao diện
        btn_load = QPushButton("🔄 Làm mới preview")
        btn_load.clicked.connect(lambda: (
            self.lbl_preview.setImage(None),
            self.index_bar.setCount(0),
            setattr(self, "loaded_image", None)
        ))
        left_layout.addWidget(btn_load)

        btn_save = QPushButton("🔄 Làm mới thông tin")
        btn_save.clicked.connect(self.refresh_device_data)
        left_layout.addWidget(btn_save)


        # ====== Đường phân cách ngang ======
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        left_layout.addWidget(line)

        for i in range(1, 11):
            btn = QPushButton(f"FN{i}  (F{i})")
            btn.setMinimumWidth(150)

            if i == 1:
                btn.setText("Chạy tất cả Presets (F1)")
                btn.clicked.connect(self.fn1_run_playlist)
            elif i == 2:
                btn.setText("Xóa tất cả Presets (F2)")
                btn.clicked.connect(self.fn2_clear_presets)
            elif i == 10:
                btn.setText("Tắt LED và Reboot (F10)")
                btn.clicked.connect(self.fn_reboot_device)
            else:
                btn.clicked.connect(lambda _, x=i: self.fn_placeholder(x))

            left_layout.addWidget(btn)

        left_layout.addStretch()

        # Phím tắt
        self.shortcut_f1 = QShortcut(QKeySequence(Qt.Key_F1), self)
        self.shortcut_f1.activated.connect(self.fn1_run_playlist)
        self.shortcut_f2 = QShortcut(QKeySequence(Qt.Key_F2), self)
        self.shortcut_f2.activated.connect(self.fn2_clear_presets)
        self.shortcut_f10 = QShortcut(QKeySequence(Qt.Key_F10), self)
        self.shortcut_f10.activated.connect(self.fn_reboot_device)

        left_panel.setFixedWidth(180)
        layout_main.addWidget(left_panel)

        # ==========================================================
        # ========== CỘT 2 – INFO / EFFECT / PRESET =================
        # ==========================================================
        mid_panel = QWidget()
        mid_layout = QVBoxLayout(mid_panel)
        mid_layout.setContentsMargins(5, 5, 5, 5)
        mid_layout.setSpacing(6)
        mid_panel.setFixedWidth(180)   # 👈 bằng cột FN

        # ---------- HÀNG 1: EFFECT LIST ----------
        lbl_fx = QLabel("✨ Hiệu ứng (Effects)")
        lbl_fx.setStyleSheet("font-weight: bold;")
        mid_layout.addWidget(lbl_fx)

        self.list_effects = QListWidget()
        self.list_effects.setSelectionMode(QListWidget.SingleSelection)
        self.list_effects.itemClicked.connect(self.on_effect_selected)
        mid_layout.addWidget(self.list_effects, 1)   # scroll được
        # Khi Double-click effect → lưu thành preset
        self.list_effects.itemDoubleClicked.connect(self.on_effect_double_clicked)

        # ---------- HÀNG 2: PRESET LIST ----------
        lbl_ps = QLabel("📦 Presets")
        lbl_ps.setStyleSheet("font-weight: bold;")
        mid_layout.addWidget(lbl_ps)

        self.list_presets = QListWidget()
        self.list_presets.setSelectionMode(QListWidget.SingleSelection)
        self.list_presets.itemClicked.connect(self.on_preset_selected)
        mid_layout.addWidget(self.list_presets, 1)

        layout_main.addWidget(mid_panel)

        # ---------- HÀNG 4: PALETTE ----------
        lbl_palette_title = QLabel("🎨 Bảng màu (Palette)")
        lbl_palette_title.setStyleSheet("font-weight: bold;")
        mid_layout.addWidget(lbl_palette_title)

        self.list_palettes = QListWidget()
        self.list_palettes.setMinimumHeight(150)
        self.list_palettes.itemClicked.connect(self.on_palette_selected)
        mid_layout.addWidget(self.list_palettes, 1)



        # ==========================================================
        # ========== CỘT 3 – PREVIEW (GIỮ NGUYÊN) ===================
        # ==========================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Index bar
        self.index_bar = PixelIndexBar()
        self.index_bar.setFixedHeight(30)
        right_layout.addWidget(self.index_bar)

        # Preview
        self.lbl_preview = PixelPreview()
        right_layout.addWidget(self.lbl_preview)

        layout_main.addWidget(right_panel, 1)



        # ==== footer ====
        footer_widget = QWidget()
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0,0,0,0)
        footer_layout.setSpacing(10)

        # Logo HSL
        pixmap_hsl = QPixmap(resource_path("assets/hsl_logo.png")).scaledToWidth(80)
        lbl_logo_hsl = QLabel()
        lbl_logo_hsl.setPixmap(pixmap_hsl)
        lbl_logo_hsl.setAlignment(Qt.AlignVCenter)

        # Logo thứ 2
        pixmap_logo2 = QPixmap(resource_path("assets/qrcode_with_logo.png")).scaledToWidth(80)
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

    def send_current_effect(self):
        item = self.list_effects.currentItem()
        if item:
            self.on_effect_selected(item)


    def pick_color(self, index):
        color = QColorDialog.getColor(
            self.col[index],
            self,
            f"Chọn màu cho col[{index}]",
            QColorDialog.ShowAlphaChannel
        )

        if not color.isValid():
            return

        self.col[index] = color
        self.update_color_button(index)
        self.send_current_effect()



    def update_color_button(self, index):
        c = self.col[index]

        preview = self.color_previews[index]
        preview.setStyleSheet(
            f"""
            background-color: rgb({c.red()}, {c.green()}, {c.blue()});
            border: 1px solid #666;
            border-radius: 4px;
            """
        )


    # ====================
    # Mở popup nhập PIN với trình duyệt nhúng
    def open_pin_browser_popup(self, ip):
        dlg = QDialog(self)
        dlg.setWindowTitle("🔐 Nhập mã PIN thiết bị")
        dlg.resize(450, 450)

        layout = QVBoxLayout(dlg)

        browser = QWebEngineView()
        start_url = f"http://{ip}/settings/sec"
        browser.setUrl(QUrl(start_url))
        layout.addWidget(browser)

        # ===== Timer kiểm tra PIN đúng =====
        timer = QTimer(dlg)
        timer.setInterval(1000)  # 1s

        def check_pin_ok():
            try:
                r = requests.get(f"http://{ip}/edit", timeout=0.5)
                if r.status_code == 200:
                    timer.stop()
                    dlg.accept()   # 🔓 PIN ĐÚNG → ĐÓNG
                    self.refresh_device_data()
            except:
                pass

        timer.timeout.connect(check_pin_ok)
        timer.start()

        # ===== BẮT SỰ KIỆN CHUYỂN HƯỚNG URL =====
        def on_url_changed(url: QUrl):
            url_str = url.toString()
            print("[PIN Browser] URL:", url_str)

            # 👉 Nếu quay về /settings (rời khỏi /settings/sec)
            if "/settings" in url_str and "/settings/sec" not in url_str:
                print("[PIN] Redirect về /settings → đóng popup")
                timer.stop()
                dlg.reject()   # ❌ PIN SAI → ĐÓNG POPUP

        browser.urlChanged.connect(on_url_changed)

        dlg.exec()



    
    # ====================
    # Kiểm tra mạch ARGB online
    def _is_device_online(self, ip):
        """Ping nhanh bằng cách GET /json (ARGB luôn trả về JSON)."""
        try:
            r = requests.get(f"http://{ip}/json", timeout=1)
            return r.status_code == 200
        except:
            return False


    # ====================
    # Tải dữ liệu thiết bị (name, ver, wifi, filesystem)
    def load_device_info(self):
        ip = self.combo_ip.currentData()
        if not ip:
            self.lbl_device_info.setText("❌ Chưa chọn mạch")
            return

        try:
            r = requests.get(f"http://{ip}/json", timeout=3)

            if r.status_code != 200:
                self.lbl_device_info.setText(f"❌ Lỗi HTTP {r.status_code}")
                return

            data = r.json()
            info = data.get("info", {})

            # --- Thông tin thiết bị ---
            name = info.get("name", "N/A")
            ver = info.get("ver", "N/A")

            # --- WiFi ---
            wifi = info.get("wifi", {})
            signal = wifi.get("signal", None)   # %
            rssi = wifi.get("rssi", None)       # dBm

            if signal is not None:
                signal_str = f"{signal}%"
            elif rssi is not None:
                signal_str = f"{rssi} dBm"
            else:
                signal_str = "N/A"

            # --- Filesystem ---
            fs = info.get("fs", {})
            fs_used = fs.get("u", None)   # kB
            fs_total = fs.get("t", None)  # kB

            if fs_used is not None and fs_total:
                fs_percent = int(fs_used * 100 / fs_total)
                fs_str = f"{fs_used} / {fs_total} kB ({fs_percent}%)"
            else:
                fs_str = "N/A"

            # --- Hiển thị ---
            self.lbl_device_info.setText(
                f"📛 Tên: {name}\n"
                f"🧩 FW: {ver}\n"
                f"📶 WiFi: {signal_str}\n"
                f"📁 Bộ nhớ: {fs_str}"
            )

        except requests.exceptions.Timeout:
            self.lbl_device_info.setText("⏱️ Timeout kết nối")

        except requests.exceptions.ConnectionError:
            self.lbl_device_info.setText("❌ Không kết nối được")

        except Exception as e:
            self.lbl_device_info.setText(f"⚠️ Lỗi:\n{e}")


    
    # ====================
    # Tải danh sách effect
    def load_effect_list(self):
        ip = self.combo_ip.currentData()
        if not ip:
            return

        self.list_effects.clear()

        try:
            r = requests.get(f"http://{ip}/json", timeout=3)
            if r.status_code != 200:
                return

            data = r.json()

            # WLED/HSL: effects là list, index = fx id
            effects = data.get("effects", [])
            if not isinstance(effects, list):
                return

            for fx_id, fx_name in enumerate(effects):
                # Hiển thị: [ID] Tên effect
                item = QListWidgetItem(f"[{fx_id}] {fx_name}")
                item.setData(Qt.UserRole, fx_id)
                item.setToolTip(f"Effect ID: {fx_id}")
                self.list_effects.addItem(item)

            # ⭐ highlight effect đang chạy
            self.highlight_current_effect()

        except Exception as e:
            print(f"[load_effect_list] Lỗi: {e}")


    # ====================
    # Khi click chọn effect → chạy ngay + gửi col[]
    def on_effect_selected(self, item):
        ip = self.combo_ip.currentData()
        if not ip or not item:
            return

        fx_id = item.data(Qt.UserRole)
        if fx_id is None:
            return

        # ====================
        # Convert QColor -> JSON col
        col_json = [
            [c.red(), c.green(), c.blue()]
            for c in self.col
        ]

        payload = {
            "on": True,
            "bri": 128,
            "seg": [
                {
                    "id": 0,
                    "fx": fx_id,
                    "col": col_json
                }
            ]
        }

        try:
            r = requests.post(
                f"http://{ip}/json/state",
                json=payload,
                timeout=2
            )

            # 🔐 Nếu bị khóa PIN
            if r.status_code == 401:
                QMessageBox.warning(
                    self,
                    "Thiết bị bị khóa",
                    "🔒 Thiết bị đang bị khóa bằng mã PIN.\n"
                    "Vui lòng mở khóa rồi thử lại."
                )
                return

            if r.status_code != 200:
                QMessageBox.warning(
                    self,
                    "Lỗi",
                    f"Không chạy được effect!\nHTTP {r.status_code}"
                )
                return

            # (Optional) highlight effect đang chạy
            self.highlight_current_effect()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


    # ====================
    # Double-click effect → lưu thành preset (user nhập ID)
    def on_effect_double_clicked(self, item):
        ip = self.combo_ip.currentData()
        if not ip or not item:
            return

        fx_id = item.data(Qt.UserRole)
        fx_name = item.text()

        # ---- Popup nhập Preset ID ----
        preset_id, ok = QInputDialog.getInt(
            self,
            "Lưu Preset",
            f"Lưu effect:\n{fx_name}\n\nNhập Preset ID muốn lưu:",
            1,      # default value
            1,      # min
            250,    # max
            1       # step
        )

        if not ok:
            return

        # ---- Xác nhận lần cuối ----
        if QMessageBox.question(
            self,
            "Xác nhận lưu Preset",
            f"⚠️ Preset ID: {preset_id}\n"
            f"Effect: {fx_name}\n\n"
            f"Nếu ID đã tồn tại, preset sẽ bị GHI ĐÈ.\n"
            f"Bạn tự chịu trách nhiệm.\n\n"
            f"Tiếp tục?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        try:
            payload = {
                "psave": preset_id
            }

            r = requests.post(
                f"http://{ip}/json/state",
                json=payload,
                timeout=2
            )

            if r.status_code == 200:
                QMessageBox.information(
                    self,
                    "Đã lưu preset",
                    f"✅ Đã lưu effect thành preset ID {preset_id}\n\n{fx_name}"
                )
                self.load_preset_list()

            else:
                QMessageBox.warning(
                    self,
                    "Lỗi",
                    f"Lưu preset thất bại (HTTP {r.status_code})"
                )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))




    # ====================
    # Highlight effect đang chạy
    def highlight_current_effect(self):
        ip = self.combo_ip.currentData()
        if not ip:
            return

        try:
            r = requests.get(f"http://{ip}/json", timeout=2)
            if r.status_code != 200:
                return

            data = r.json()
            segs = data.get("state", {}).get("seg", [])
            if not segs:
                return

            current_fx = segs[0].get("fx", None)
            if current_fx is None:
                return

            for i in range(self.list_effects.count()):
                item = self.list_effects.item(i)
                if item.data(Qt.UserRole) == current_fx:
                    self.list_effects.setCurrentRow(i)
                    break

        except Exception:
            pass


    # ==================
    # Tải danh sách preset (chuẩn theo JSON HSL/WLED thực tế)
    def load_preset_list(self):
        ip = self.combo_ip.currentData()
        if not ip:
            return

        self.list_presets.clear()

        try:
            r = requests.get(f"http://{ip}/presets.json", timeout=3)
            if r.status_code != 200:
                print(f"[preset] HTTP {r.status_code}")
                return

            presets = r.json()
            # print("[preset] RAW JSON:", presets)

            if not isinstance(presets, dict):
                print("[preset] ❌ presets.json không phải dict")
                return

            # ---- Lọc + sort preset ID hợp lệ ----
            preset_items = []

            for pid_str, pdata in presets.items():
                # key phải là số
                if not pid_str.isdigit():
                    continue

                pid = int(pid_str)

                # ❌ Bỏ qua preset 0 hoặc object rỗng
                if pid == 0 or not isinstance(pdata, dict) or not pdata:
                    continue

                # Tên preset nằm ở level top: "n"
                name = pdata.get("n", f"Preset {pid}")

                preset_items.append((pid, name))

            # Sort theo ID tăng dần
            preset_items.sort(key=lambda x: x[0])

            # ---- Đưa lên UI ----
            for pid, name in preset_items:
                item = QListWidgetItem(f"[{pid}] {name}")
                item.setData(Qt.UserRole, pid)
                item.setToolTip(f"Preset ID: {pid}")

                self.list_presets.addItem(item)

            print(f"[preset] ✔ Load {len(preset_items)} preset")

        except Exception as e:
            print(f"[load_preset_list] ❌ Exception: {e}")


    # ====================
    # Khi click chọn preset → chạy ngay
    def on_preset_selected(self, item):
        ip = self.combo_ip.currentData()
        if not ip or not item:
            return

        preset_id = item.data(Qt.UserRole)
        if preset_id is None:
            return

        payload = {
            "on": True,
            "ps": preset_id
        }

        try:
            r = requests.post(
                f"http://{ip}/json/state",
                json=payload,
                timeout=2
            )

            if r.status_code != 200:
                print(f"[Preset] HTTP {r.status_code}")

        except Exception as e:
            print(f"[Preset] Lỗi chạy preset {preset_id}: {e}")


    # ====================
    # Tải danh sách palette
    def load_palette_list(self):
        ip = self.combo_ip.currentData()
        if not ip:
            return

        self.list_palettes.clear()

        try:
            r = requests.get(f"http://{ip}/json", timeout=3)
            if r.status_code != 200:
                return

            j = r.json()
            palettes = j.get("palettes", [])

            if not isinstance(palettes, list):
                return

            for pid, name in enumerate(palettes):
                item = QListWidgetItem(f"[{pid}] {name}")
                item.setData(Qt.UserRole, pid)
                item.setToolTip(f"Palette ID: {pid}")
                self.list_palettes.addItem(item)

        except Exception as e:
            print(f"[load_palette_list] Lỗi: {e}")


    # ====================
    # Khi click chọn palette → áp dụng ngay
    def on_palette_selected(self, item):
        ip = self.combo_ip.currentData()
        if not ip or not item:
            return

        pal_id = item.data(Qt.UserRole)

        payload = {
            "seg": [
                {
                    "id": 0,
                    "pal": pal_id
                }
            ]
        }

        try:
            r = requests.post(
                f"http://{ip}/json/state",
                json=payload,
                timeout=2
            )

            if r.status_code != 200:
                QMessageBox.warning(
                    self,
                    "Lỗi",
                    f"Không áp dụng được palette!\nHTTP {r.status_code}"
                )
                return

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))


    def refresh_device_data(self):
        self.load_device_info()
        self.load_effect_list()
        self.load_preset_list()
        self.load_palette_list()
        self.highlight_current_effect()

    # ====================
    # Mở trang cài đặt ARGB (KIỂM TRA ONLINE TRƯỚC)
    # ====================
    def settings_led(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Lỗi", "Không có IP để mở trang Cài đặt.")
            return

        # ⭐ Kiểm tra thiết bị còn online không
        if not self._is_device_online(ip):
            QMessageBox.critical(
                self,
                "Không kết nối",
                f"Không thể truy cập thiết bị {ip}.\n"
                "Thiết bị có thể đã tắt nguồn hoặc mất WiFi."
            )
            return

        # ⭐ Nếu online → mở trang cấu hình
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
    # FN1: Kiểm tra IP → đọc preset → popup → nhập thời gian → chạy playlist
    # ====================
    def fn1_run_playlist(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn mạch ARGB trong danh sách!")
            return

        # 1️⃣ Kiểm tra online
        if not self._is_device_online(ip):
            QMessageBox.critical(self, "Không online", f"Mạch ARGB {ip} không phản hồi!")
            return

        # 2️⃣ Tải presets.json
        try:
            r = requests.get(f"http://{ip}/presets.json", timeout=2)
            presets = r.json()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không đọc được presets.json:\n{e}")
            return

        # 3️⃣ Lọc preset hợp lệ (ID >= 1)
        valid = []
        for k, v in presets.items():
            if k.isdigit() and int(k) >= 1 and isinstance(v, dict) and len(v) > 0:
                name = v.get("n", f"Preset {k}")
                valid.append((int(k), name))

        valid.sort(key=lambda x: x[0])

        if not valid:
            QMessageBox.information(self, "Không có preset", "Thiết bị không có preset hợp lệ!")
            return

        # 4️⃣ Popup danh sách preset
        msg = f"Số preset hợp lệ: <b>{len(valid)}</b><br><br>"
        for pid, name in valid:
            msg += f"ID {pid}: {name}<br>"

        QMessageBox.information(self, "Danh sách preset", msg)

        # ⭐ 5️⃣ Popup nhập số giây chuyển preset
        seconds, ok = QInputDialog.getInt(
            self,
            "Thời gian chạy mỗi preset",
            "Nhập số giây cho mỗi preset:",
            5,      # default
            1,      # min
            3600,   # max
            1       # step
        )

        if not ok:
            return  # Người dùng bấm Cancel


        # ⭐ Convert giây → dur WLED (1s = 10 đơn vị)
        dur_value = seconds * 10  

        # 6️⃣ Chuẩn bị playlist
        preset_ids = [pid for pid, _ in valid]
        dur_list   = [dur_value] * len(preset_ids)

        payload = {
            "on": True,
            "playlist": {
                "ps": preset_ids,
                "dur": dur_list,
                "repeat": 0
            }
        }

        # 7️⃣ Gửi playlist
        try:
            url = f"http://{ip}/json/state"
            r = requests.post(url, json=payload, timeout=2)

            if r.status_code == 200:
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Playlist đã bắt đầu chạy!\n"
                    f"Mỗi preset chạy {seconds} giây."
                )
            else:
                QMessageBox.critical(self, "Lỗi", f"Gửi playlist thất bại!\nHTTP {r.status_code}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không gửi được playlist:\n{e}")


    # ====================
    # FN2: Xóa Preset + Xóa file BMP (có Progress)
    # ====================
    def fn2_clear_presets(self):
        from PySide6.QtWidgets import QMessageBox, QProgressDialog, QApplication
        from PySide6.QtCore import Qt
        import requests

        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn mạch ARGB hợp lệ.")
            return

        # -----------------------------
        # XÁC MINH LẦN 1
        # -----------------------------
        if QMessageBox.question(
            self,
            "Xác nhận lần 1",
            "⚠️ Bạn sắp XÓA TẤT CẢ PRESET (Preset 1 → N) trên thiết bị!\n\n"
            "Hành động này KHÔNG THỂ hoàn tác.\n"
            "Bạn có chắc muốn tiếp tục không?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        # -----------------------------
        # XÁC MINH LẦN 2
        # -----------------------------
        if QMessageBox.question(
            self,
            "Xác nhận lần 2",
            "🚨 CẢNH BÁO CUỐI CÙNG!\nBạn thực sự muốn xóa TOÀN BỘ PRESET không?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        # 1️⃣ Kiểm tra online
        if not self._is_device_online(ip):
            QMessageBox.critical(self, "Không online", f"Mạch ARGB {ip} không phản hồi!")
            return

        # ===============================================================
        # ⭐ 2️⃣ LẤY DANH SÁCH PRESET
        # ===============================================================
        preset_ids = []
        try:
            r = requests.get(f"http://{ip}/presets.json", timeout=2)
            if r.status_code == 200:
                presets = r.json()
                preset_ids = sorted(
                    int(k) for k in presets.keys()
                    if k.isdigit() and int(k) >= 1
                )
        except:
            pass

        # ===============================================================
        # ⭐ 3️⃣ XÓA PRESET (CÓ PROGRESS)
        # ===============================================================
        if preset_ids:
            progress = QProgressDialog(
                "🧹 Đang xóa preset...",
                "Hủy",
                0,
                len(preset_ids),
                self
            )
            progress.setWindowTitle("Xóa Preset")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            try:
                # đưa về trạng thái an toàn
                requests.post(f"http://{ip}/json/state", json={"ps": 0}, timeout=2)
                requests.post(f"http://{ip}/json/state", json={"on": False}, timeout=2)
            except:
                pass

            failed = []

            for idx, pid in enumerate(preset_ids, start=1):
                if progress.wasCanceled():
                    progress.close()
                    QMessageBox.information(self, "Đã hủy", "⛔ Người dùng đã hủy xóa preset.")
                    return

                progress.setLabelText(f"🧹 Xóa preset {pid} ({idx}/{len(preset_ids)})")
                QApplication.processEvents()

                try:
                    r = requests.post(
                        f"http://{ip}/json/state",
                        json={"pdel": pid},
                        timeout=2
                    )
                    if r.status_code != 200:
                        failed.append(pid)
                except:
                    failed.append(pid)

                progress.setValue(idx)
                QApplication.processEvents()

            progress.close()

            if failed:
                QMessageBox.warning(
                    self,
                    "Xóa preset chưa hoàn tất",
                    "Một số preset không xóa được:\n" + ", ".join(map(str, failed))
                )
            else:
                QMessageBox.information(
                    self,
                    "Preset đã xóa",
                    f"🎉 Đã xóa {len(preset_ids)} preset thành công!"
                )

        # ===============================================================
        # ⭐ 4️⃣ HỎI CÓ MUỐN XÓA FILE BMP KHÔNG
        # ===============================================================
        if QMessageBox.question(
            self,
            "Xóa file ảnh BMP?",
            "Bạn có muốn xóa toàn bộ file ảnh (*.bmp) trong bộ nhớ thiết bị không?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            self.refresh_device_data()
            return

        # ===============================================================
        # ⭐ 5️⃣ LẤY DANH SÁCH FILE BMP
        # ===============================================================
        try:
            r = requests.get(f"http://{ip}/edit?list", timeout=3)

            if r.status_code == 401:
                self.open_pin_browser_popup(ip)
                r = requests.get(f"http://{ip}/edit?list", timeout=3)

            if r.status_code != 200:
                QMessageBox.critical(self, "Lỗi", f"Không lấy được danh sách file! HTTP {r.status_code}")
                return

            files = r.json()
            bmp_files = [
                f["name"]
                for f in files
                if isinstance(f, dict)
                and "name" in f
                and f["name"].lower().endswith(".bmp")
            ]
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không đọc danh sách file:\n{e}")
            return

        if not bmp_files:
            QMessageBox.information(self, "Không có file BMP", "Không có file BMP để xóa.")
            self.refresh_device_data()
            return

        # ===============================================================
        # ⭐ 6️⃣ XÓA FILE BMP (CÓ PROGRESS)
        # ===============================================================
        progress = QProgressDialog(
            "🗑️ Đang xóa file BMP...",
            "Hủy",
            0,
            len(bmp_files),
            self
        )
        progress.setWindowTitle("Xóa ảnh BMP")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        failed_bmp = []

        for idx, filename in enumerate(bmp_files, start=1):
            if progress.wasCanceled():
                progress.close()
                QMessageBox.information(self, "Đã hủy", "⛔ Người dùng đã hủy xóa file BMP.")
                return

            progress.setLabelText(f"🗑️ Xóa {filename} ({idx}/{len(bmp_files)})")
            QApplication.processEvents()

            try:
                rr = requests.get(
                    f"http://{ip}/edit",
                    params={"func": "delete", "path": filename},
                    timeout=3
                )
                if rr.status_code != 200:
                    failed_bmp.append(filename)
            except:
                failed_bmp.append(filename)

            progress.setValue(idx)
            QApplication.processEvents()

        progress.close()

        if failed_bmp:
            QMessageBox.warning(
                self,
                "Xóa ảnh chưa hoàn tất",
                "Một số file BMP không xóa được:\n" + "\n".join(failed_bmp)
            )
        else:
            QMessageBox.information(
                self,
                "Hoàn tất",
                f"🎉 Đã xóa toàn bộ {len(bmp_files)} file BMP thành công!"
            )

        self.refresh_device_data()


    # ====================
    # FN: Tắt LED và Khởi động lại thiết bị WLED (2 bước xác minh)
    # ====================
    def fn_reboot_device(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # 1️⃣ Kiểm tra online
        if not self._is_device_online(ip):
            QMessageBox.critical(self, "Không online", f"Mạch ARGB {ip} không phản hồi!")
            return

        # -----------------------------
        # XÁC MINH LẦN 1
        # -----------------------------
        confirm_1 = QMessageBox.question(
            self,
            "Xác nhận lần 1",
            "⚠️ Bạn sắp KHỞI ĐỘNG LẠI thiết bị!\n\n"
            "• LED sẽ tắt\n"
            "• Mạch ARGB sẽ reboot\n\n"
            "Bạn có chắc muốn tiếp tục không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm_1 != QMessageBox.Yes:
            return

        # -----------------------------
        # XÁC MINH LẦN 2 (cuối cùng)
        # -----------------------------
        confirm_2 = QMessageBox.question(
            self,
            "Xác nhận lần 2",
            "🚨 CẢNH BÁO CUỐI CÙNG!\n"
            "Bạn THỰC SỰ muốn khởi động lại thiết bị này không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm_2 != QMessageBox.Yes:
            return

        # 2️⃣ Tắt LED trước khi reboot
        try:
            requests.post(
                f"http://{ip}/json/state",
                json={"on": False},
                timeout=2
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Lỗi khi tắt LED:\n{e}"
            )
            return

        # 3️⃣ Gửi lệnh reset
        try:
            r = requests.get(f"http://{ip}/reset", timeout=2)

            # WLED thường trả 200 hoặc 302 Redirect
            if r.status_code not in (200, 302):
                QMessageBox.warning(
                    self,
                    "Lỗi reboot",
                    f"Không thể reboot thiết bị.\nHTTP {r.status_code}"
                )
                return

        except Exception:
            # Thiết bị ngắt kết nối khi reboot → hành vi bình thường
            QMessageBox.information(
                self,
                "Đang khởi động lại",
                "Thiết bị đã nhận lệnh reset và đang khởi động lại..."
            )
            return

        # 4️⃣ Nếu request không lỗi
        QMessageBox.information(
            self,
            "Hoàn tất",
            "Thiết bị đã được tắt LED và khởi động lại thành công!"
        )


    # ====================
    # Chức năng FN placeholder
    def fn_placeholder(self, index):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            f"FN{index}",
            f"Chức năng FN{index} đang được phát triển…"
        )

    # ====================
    # Tắt LED ARGB (có kiểm tra ONLINE trước)
    # ====================
    def turn_off_led(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # ⭐ KIỂM TRA ONLINE TRƯỚC
        if not self._is_device_online(ip):
            QMessageBox.critical(
                self,
                "Không kết nối",
                f"Không thể tắt LED vì thiết bị {ip} không phản hồi.\n"
                "Thiết bị có thể đã tắt nguồn hoặc mất WiFi."
            )
            return

        # ⭐ THIẾT BỊ ONLINE → gửi lệnh tắt
        try:
            url_state = f"http://{ip}/json/state"
            json_payload = {"on": False}

            r = requests.post(url_state, json=json_payload, timeout=3)

            if r.status_code == 200:
                QMessageBox.information(self, "OK", "Đã tắt LED ARGB thành công!")
            else:
                QMessageBox.warning(
                    self,
                    "Lỗi",
                    f"Tắt LED thất bại!\nHTTP {r.status_code}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể gửi lệnh tắt LED:\n{e}"
            )


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
                if not info or not info.addresses:
                    return

                ip_bytes = info.addresses[0]
                ip = ".".join(str(b) for b in ip_bytes)

                if ip in found_devices:
                    return

                try:
                    r = requests.get(f"http://{ip}/json", timeout=0.3)
                    if r.status_code != 200:
                        return

                    j = r.json()
                    info_j = j.get("info", {})

                    # ⚠️ đúng theo firmware HSL của bạn
                    if info_j.get("name") and info_j.get("repo") == "HappySmartLight":
                        dev_name = info_j.get("name", "ARGB")
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
                    self.combo_ip.addItem(f"{dev_name} ({ip})", userData=ip)

                # ⭐ TỰ ĐỘNG CHỌN THIẾT BỊ ĐẦU TIÊN
                self.combo_ip.setCurrentIndex(0)

                # # ⭐ GỌI LOAD INFO NGAY
                # self.load_device_info()
                # # ⭐ LOAD EFFECT + PRESET
                # self.load_effect_list()
                # # ⭐ LOAD PRESET
                # self.load_preset_list()
                # ⭐ refresh data
                self.refresh_device_data()

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

            # ====== GÁN THÔNG TIN CHO PREVIEW ======
            # ảnh gốc
            self.lbl_preview.source_name = os.path.basename(file)
            self.lbl_preview.source_size = (
                self.loaded_image.width,
                self.loaded_image.height
            )
            # ======================================

            self.lbl_info.setText(
                f"Đã tải: {os.path.basename(file)} — "
                f"kích thước {self.loaded_image.width}x{self.loaded_image.height}"
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
    # Gửi BMP đến ARGB và cập nhật trạng thái
    def send_to_argb(self):
        if self.loaded_image is None:
            QMessageBox.warning(self, "Chưa có ảnh", "Vui lòng mở ảnh trước.")
            return

        # Lấy IP từ combobox userData
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # ⭐ KIỂM TRA KẾT NỐI TRƯỚC
        if not self._is_device_online(ip):
            QMessageBox.critical(
                self,
                "Thiết bị không online",
                f"Không thể kết nối đến {ip}.\nThiết bị có thể đã tắt nguồn hoặc mất WiFi."
            )
            return

        # ======================
        # 🧩 A) TẠO TÊN PRESET TỪ TÊN FILE ẢNH GỐC
        # ======================
        import re

        base_name = os.path.basename(self.input_path)            # vd: logo_hsl_demo.png
        name_no_ext = os.path.splitext(base_name)[0]             # logo_hsl_demo

        # chỉ giữ ký tự an toàn
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name_no_ext)

        # giới hạn 20 ký tự
        preset_name = safe_name[:20] if len(safe_name) > 20 else safe_name
        if not preset_name:
            preset_name = "Preset_1"

        upload_filename = preset_name + ".bmp"   # tên file BMP upload

        # ======================
        # Chuẩn bị file BMP
        # ======================
        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
        im2.save(tmp.name, "BMP")
        tmp.close()

        try:
            # ======================
            # 1) UPLOAD FILE — HỖ TRỢ 401
            # ======================
            while True:
                if not self._is_device_online(ip):
                    QMessageBox.critical(
                        self,
                        "Mất kết nối",
                        f"Thiết bị {ip} đã mất kết nối trong khi upload."
                    )
                    return

                url_upload = f"http://{ip}/upload"

                with open(tmp.name, "rb") as f:
                    files = {
                        "data": (upload_filename, f, "image/bmp")
                    }
                    try:
                        r = requests.post(url_upload, files=files, timeout=5)
                    except Exception:
                        QMessageBox.critical(
                            self,
                            "Lỗi Upload",
                            "Không thể upload file (Timeout / thiết bị không phản hồi)."
                        )
                        return

                # ---- 401 PIN ----
                if r.status_code == 401:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Thiết bị đang bị khóa (401)")
                    msg.setText("Thiết bị yêu cầu mã PIN để truy cập.\nBạn muốn làm gì?")

                    btn_open = msg.addButton("Mở trang PIN", QMessageBox.ActionRole)
                    btn_retry = msg.addButton("Gửi lại", QMessageBox.AcceptRole)
                    btn_cancel = msg.addButton("Hủy", QMessageBox.RejectRole)
                    msg.exec()

                    if msg.clickedButton() == btn_open:
                        # QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
                        self.open_pin_browser_popup(ip)
                        continue
                    elif msg.clickedButton() == btn_retry:
                        continue
                    else:
                        return

                elif r.status_code != 200:
                    QMessageBox.warning(
                        self,
                        "Lỗi Upload",
                        f"Upload không thành công!\nHTTP {r.status_code}"
                    )
                    return

                break  # upload OK

            # ======================
            # 2) POST JSON CẤU HÌNH + LƯU PRESET
            # ======================
            url_state = f"http://{ip}/json/state"
            json_payload = {
                "on": True,
                "bri": 100,
                "seg": [
                    {
                        "id": 0,
                        "on": True,
                        "bri": 60,
                        "n": f"/{upload_filename}",
                        "fx": 48
                    }
                ],
                "psave": 1,
                "n": preset_name        # ⭐ TÊN PRESET RÕ RÀNG
            }

            r2 = requests.post(url_state, json=json_payload, timeout=3)
            if r2.status_code != 200:
                print(f"[WARN] POST JSON thất bại HTTP {r2.status_code}")

            QMessageBox.information(
                self,
                "Hoàn tất",
                f"Đã gửi ảnh và lưu preset:\n{preset_name}"
            )
            # Cập nhật lại danh sách preset
            self.refresh_device_data()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể gửi BMP:\n{e}")

        finally:
            os.unlink(tmp.name)




    # ====================
    # Gửi nhiều ảnh đến ARGB (Preset tăng dần, có Progress)
    # ====================
    def send_multiple_to_argb(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QDesktopServices
        from PIL import Image
        import tempfile, os, requests, re
        from PySide6.QtWidgets import QApplication

        # 1️⃣ Lấy IP mạch
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Chưa chọn mạch", "Vui lòng chọn mạch ARGB hợp lệ.")
            return

        # 2️⃣ Lấy width mục tiêu
        w = self._get_target_width()
        if not w:
            return

        # 3️⃣ Chọn nhiều ảnh
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh để gửi ARGB", "", "Images (*.png *.jpg *.bmp)"
        )
        if not file_paths:
            return

        # 4️⃣ Load ảnh PIL
        try:
            images = [(p, Image.open(p)) for p in file_paths]
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load ảnh: {e}")
            return

        total = len(images)

        # ====================
        # PROGRESS DIALOG
        progress = QProgressDialog(
            "Chuẩn bị gửi ảnh...",
            "Hủy",
            0,
            total,
            self
        )
        progress.setWindowTitle("📤 Đang gửi ảnh lên ARGB")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        # ====================
        # 5️⃣ Gửi từng ảnh
        for idx, (path, img) in enumerate(images, start=1):

            if progress.wasCanceled():
                QMessageBox.information(self, "Đã hủy", "⛔ Người dùng đã hủy quá trình gửi.")
                return

            progress.setLabelText(
                f"📤 Đang gửi ảnh {idx}/{total}\n"
                f"{os.path.basename(path)}"
            )
            QApplication.processEvents()

            # 🧩 A) Tạo tên preset
            base = os.path.basename(path)
            name_no_ext = os.path.splitext(base)[0]
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name_no_ext)
            preset_name = safe_name[:20] if len(safe_name) > 20 else safe_name
            if not preset_name:
                preset_name = f"Preset_{idx}"

            upload_filename = preset_name + ".bmp"

            while True:  # retry loop (PIN / retry)
                tmp_file = None
                try:
                    # 🧩 B) Convert ảnh
                    bmp_image = self._convert_to_square_rgb(w, img)

                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
                    bmp_image.save(tmp_file.name, "BMP")
                    tmp_file.close()

                    # 🧩 C) Upload BMP
                    with open(tmp_file.name, "rb") as f:
                        files = {"data": (upload_filename, f, "image/bmp")}
                        r = requests.post(
                            f"http://{ip}/upload",
                            files=files,
                            timeout=10
                        )

                    # --- PIN 401 ---
                    if r.status_code == 401:
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Thiết bị đang bị khóa (401)")
                        msg.setText("Thiết bị yêu cầu mã PIN.\nBạn muốn làm gì?")
                        btn_open = msg.addButton("Nhập mã PIN", QMessageBox.ActionRole)
                        btn_retry = msg.addButton("Gửi lại", QMessageBox.AcceptRole)
                        btn_cancel = msg.addButton("Hủy", QMessageBox.RejectRole)
                        msg.exec()

                        clicked = msg.clickedButton()
                        if clicked == btn_open:
                            self.open_pin_browser_popup(ip)
                            continue
                        elif clicked == btn_retry:
                            continue
                        else:
                            progress.close()
                            return

                    elif r.status_code != 200:
                        QMessageBox.warning(
                            self, "Lỗi Upload",
                            f"Upload thất bại!\nHTTP {r.status_code}"
                        )
                        progress.close()
                        return

                    # 🧩 D) Lưu preset
                    payload = {
                        "on": True,
                        "bri": 100,
                        "seg": [
                            {
                                "id": 0,
                                "on": True,
                                "bri": 60,
                                "n": f"/{upload_filename}",
                                "fx": 48
                            }
                        ],
                        "psave": idx,
                        "n": preset_name
                    }

                    r2 = requests.post(
                        f"http://{ip}/json/state",
                        json=payload,
                        timeout=10
                    )

                    if r2.status_code != 200:
                        QMessageBox.warning(
                            self, "Lỗi",
                            f"Không lưu preset!\nHTTP {r2.status_code}"
                        )

                    break  # ✅ xong ảnh này

                except Exception as e:
                    QMessageBox.critical(self, "Lỗi", f"Lỗi khi gửi ảnh:\n{e}")
                    progress.close()
                    return

                finally:
                    if tmp_file and os.path.exists(tmp_file.name):
                        os.unlink(tmp_file.name)

            progress.setValue(idx)
            QApplication.processEvents()

        progress.close()

        QMessageBox.information(
            self,
            "Hoàn tất",
            f"🎉 Đã gửi và lưu {total} ảnh thành công!"
        )

        self.refresh_device_data()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon = resource_path("assets/favicon.ico")
    app.setWindowIcon(QIcon(icon))
    win = BMPConverter()
    win.setWindowIcon(QIcon(icon))
    win.show()
    sys.exit(app.exec())
