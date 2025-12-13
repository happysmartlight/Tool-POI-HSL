import sys, os, tempfile, requests, re
from PIL import Image
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from config import APP_TITLE, APP_VERSION, APP_COMPANY, resource_path
from widgets import PixelPreview, PixelIndexBar
from image_utils import convert_to_square_rgb

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
        main.addWidget(frame, 1)
        
        # ==== CHIA FRAME THÀNH 2 VÙNG ====
        layout_main = QHBoxLayout(frame)
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.setSpacing(10)

        # ========== VÙNG TRÁI (cột nhỏ chứa nút) ==========
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(8)


        # Các nút đồng bộ giao diện
        btn_load = QPushButton("🔄 Làm mới preview")
        btn_load.clicked.connect(lambda: (
            self.lbl_preview.setImage(None),
            self.index_bar.setCount(0),
            setattr(self, "loaded_image", None)         # xoá ảnh gốc → send_to_argb không gửi được nữa
        ))


        btn_save = QPushButton("💾 Lưu BMP từ preview")
        btn_save.clicked.connect(self.save_as_bmp)

        btn_refresh = QPushButton("📤 Gửi ảnh đang xem")
        btn_refresh.clicked.connect(self.send_to_argb)

        left_layout.addWidget(btn_load)
        left_layout.addWidget(btn_save)
        left_layout.addWidget(btn_refresh)

        # ====== Nhóm nút chức năng FN1 → FN10 ======
        lbl_fn = QLabel("Phím chức năng nhanh:")
        lbl_fn.setWordWrap(True)   # 👈 giú
        left_layout.addWidget(lbl_fn)

        for i in range(1, 11):
            btn = QPushButton(f"FN{i}  (F{i})")
            btn.setMinimumWidth(150)

            if i == 1:
                btn = QPushButton(f"Chạy tất cả Presets (F{i})")
                btn.clicked.connect(self.fn1_run_playlist)
            elif i == 2:
                btn = QPushButton(f"Xóa tất cả Presets (F{i})")
                btn.clicked.connect(self.fn2_clear_presets)
            elif i == 10:
                btn = QPushButton(f"Tắt LED và Reboot (F{i})")
                btn.clicked.connect(self.fn_reboot_device)
            else:
                btn.clicked.connect(lambda _, x=i: self.fn_placeholder(x))

            left_layout.addWidget(btn)


        left_layout.addStretch()
        # ==== Thiết lập phím tắt cho FN1 và FN2 ====
        self.shortcut_f1 = QShortcut(QKeySequence(Qt.Key_F1), self)
        self.shortcut_f1.activated.connect(self.fn1_run_playlist)
        self.shortcut_f2 = QShortcut(QKeySequence(Qt.Key_F2), self)
        self.shortcut_f2.activated.connect(self.fn2_clear_presets)
        self.shortcut_f10 = QShortcut(QKeySequence(Qt.Key_F10), self)
        self.shortcut_f10.activated.connect(self.fn_reboot_device)


        left_panel.setFixedWidth(180)
        layout_main.addWidget(left_panel)

        # ========== VÙNG PHẢI (INDEX BAR + PREVIEW) ==========
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

        # Thêm panel phải vào layout (chiếm toàn bộ phần còn lại)
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
    # FN2: Xóa Preset + Xóa file BMP trong bộ nhớ WLED
    # ====================
    def fn2_clear_presets(self):
        ip = self.combo_ip.currentData()
        if not ip:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn mạch ARGB hợp lệ.")
            return

        # -----------------------------
        # XÁC MINH LẦN 1
        # -----------------------------
        confirm_1 = QMessageBox.question(
            self,
            "Xác nhận lần 1",
            "⚠️ Bạn sắp XÓA TẤT CẢ PRESET (Preset 1 → N) trên thiết bị!\n\n"
            "Hành động này KHÔNG THỂ hoàn tác.\n"
            "Bạn có chắc muốn tiếp tục không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm_1 != QMessageBox.Yes:
            return

        # -----------------------------
        # XÁC MINH LẦN 2
        # -----------------------------
        confirm_2 = QMessageBox.question(
            self,
            "Xác nhận lần 2",
            "🚨 CẢNH BÁO CUỐI CÙNG!\nBạn thực sự muốn xóa TOÀN BỘ PRESET không?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm_2 != QMessageBox.Yes:
            return

        # 1️⃣ Kiểm tra online
        if not self._is_device_online(ip):
            QMessageBox.critical(self, "Không online", f"Mạch ARGB {ip} không phản hồi!")
            return

        # 2️⃣ Lấy danh sách preset
        try:
            r = requests.get(f"http://{ip}/presets.json", timeout=2)
            presets = r.json()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không đọc được presets.json:\n{e}")
            return

        # Lấy preset hợp lệ ID >= 1
        preset_ids = [int(k) for k in presets.keys() if k.isdigit() and int(k) >= 1]
        preset_ids.sort()

        if not preset_ids:
            QMessageBox.information(self, "Không có preset", "Thiết bị không có preset để xóa.")
            return

        # ===============================================================
        # ⭐ 3️⃣ ĐƯA THIẾT BỊ VỀ TRẠNG THÁI AN TOÀN
        # ===============================================================
        try:
            requests.post(f"http://{ip}/json/state", json={"ps": 0}, timeout=2)
            requests.post(f"http://{ip}/json/state", json={"on": False}, timeout=2)
        except:
            QMessageBox.critical(
                self,
                "Lỗi",
                "Không thể đưa thiết bị về trạng thái an toàn (preset 0 + tắt LED)."
            )
            return

        # ===============================================================
        # ⭐ 4️⃣ XÓA PRESET: { "pdel": ID }
        # ===============================================================
        failed = []

        for pid in preset_ids:
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

        # 5️⃣ Báo cáo preset
        if failed:
            QMessageBox.warning(
                self,
                "Xóa chưa hoàn tất",
                "Một số preset không xóa được:\n" + ", ".join(map(str, failed))
            )
        else:
            QMessageBox.information(
                self,
                "Preset đã xóa",
                f"🎉 Đã xóa {len(preset_ids)} preset thành công!"
            )

        # ===============================================================
        # ⭐ 6️⃣ HỎI NGƯỜI DÙNG CÓ MUỐN XÓA FILE BMP KHÔNG?
        # ===============================================================
        confirm_bmp = QMessageBox.question(
            self,
            "Xóa file ảnh BMP?",
            "Bạn có muốn xóa toàn bộ file ảnh (*.bmp) trong bộ nhớ thiết bị không?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm_bmp != QMessageBox.Yes:
            return

        # ===============================================================
        # ⭐ 7️⃣ LẤY DANH SÁCH FILE CHUẨN /edit?list (trả về LIST)
        # ===============================================================
        try:
            r = requests.get(f"http://{ip}/edit?list", timeout=3)
            if r.status_code != 200:
                QMessageBox.critical(self, "Lỗi", f"Không lấy được danh sách file! HTTP {r.status_code}")
                return

            files = r.json()
            if not isinstance(files, list):
                QMessageBox.critical(self, "Lỗi", "Phản hồi không đúng dạng list!")
                return

            # Lọc file *.bmp
            bmp_files = [
                f["name"]
                for f in files
                if isinstance(f, dict)
                and "name" in f
                and isinstance(f["name"], str)
                and f["name"].lower().endswith(".bmp")
            ]

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không đọc danh sách file:\n{e}")
            return

        if not bmp_files:
            QMessageBox.information(self, "Không có file BMP", "Thiết bị không có file ảnh BMP để xóa.")
            return

        # ===============================================================
        # ⭐ 8️⃣ XÓA FILE BMP BẰNG func=delete
        # ===============================================================
        failed_bmp = []

        for filename in bmp_files:
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

        # ===============================================================
        # ⭐ 9️⃣ Báo cáo kết quả
        # ===============================================================
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

        # ⭐ KIỂM TRA KẾT NỐI TRƯỚC: TRÁNH CONNECT TIMEOUT
        if not self._is_device_online(ip):
            QMessageBox.critical(
                self, 
                "Thiết bị không online",
                f"Không thể kết nối đến {ip}.\nThiết bị có thể đã tắt nguồn hoặc mất WiFi."
            )
            return

        # Chuẩn bị file tạm
        w = self._get_target_width()
        if not w:
            return

        im2 = self._convert_to_square_rgb(w, self.loaded_image)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
        im2.save(tmp.name, "BMP")
        tmp.close()

        output_name = os.path.basename(tmp.name)

        try:
            # ======================
            # 1) UPLOAD FILE — CÓ VÒNG LẶP XỬ LÝ 401
            # ======================
            while True:
                # Trước mỗi lần retry 401 — kiểm tra thiết bị còn sống không
                if not self._is_device_online(ip):
                    QMessageBox.critical(
                        self,
                        "Mất kết nối",
                        f"Thiết bị {ip} đã mất kết nối trong khi upload.\n"
                        "Vui lòng kiểm tra nguồn pin hoặc WiFi."
                    )
                    return

                url_upload = f"http://{ip}/upload"

                with open(tmp.name, "rb") as f:
                    files = {"data": f}
                    try:
                        r = requests.post(url_upload, files=files, timeout=5)
                    except Exception:
                        QMessageBox.critical(
                            self,
                            "Lỗi Upload",
                            "Không thể upload file (Timeout / thiết bị không phản hồi)."
                        )
                        return

                # -----------------------------
                # Lỗi 401 → yêu cầu PIN
                # -----------------------------
                if r.status_code == 401:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Thiết bị đang bị khóa (401)")
                    msg.setText("Thiết bị yêu cầu mã PIN để truy cập.\nBạn muốn làm gì?")

                    btn_open = msg.addButton("Mở trang PIN", QMessageBox.ActionRole)
                    btn_retry = msg.addButton("Gửi lại", QMessageBox.AcceptRole)
                    btn_cancel = msg.addButton("Hủy", QMessageBox.RejectRole)
                    msg.exec()

                    clicked = msg.clickedButton()

                    if clicked == btn_open:
                        QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
                        # ⭐ KHÔNG RETURN → tiếp tục hiện popup lại / retry
                        continue  

                    elif clicked == btn_retry:
                        # ⭐ Thử lại ngay
                        continue
                
                    else:
                        return

                # -----------------------------
                # Lỗi HTTP khác ≠ 200
                # -----------------------------
                elif r.status_code != 200:
                    QMessageBox.warning(
                        self, 
                        "Lỗi Upload",
                        f"Upload không thành công!\nHTTP {r.status_code}"
                    )
                    return

                # Upload thành công → break
                break

            # ======================
            # 2) POST JSON cấu hình LED
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
                        "n": f"/{output_name}",
                        "fx": 48
                    }
                ],
                "psave": 1
            }

            try:
                r2 = requests.post(url_state, json=json_payload, timeout=3)
                if r2.status_code != 200:
                    print(f"[WARN] POST JSON thất bại HTTP {r2.status_code}")
            except Exception:
                QMessageBox.critical(
                    self,
                    "Lỗi JSON API",
                    "Không thể gửi lệnh cấu hình LED.\nThiết bị có thể đã mất kết nối."
                )
                return

            QMessageBox.information(self, "Hoàn tất", f"Đã gửi BMP đến {ip} thành công!")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể gửi BMP:\n{e}")

        finally:
            os.unlink(tmp.name)



    # ====================
    # Gửi nhiều ảnh đến ARGB (Preset tăng dần, đặt tên preset theo tên ảnh)
    # ====================
    def send_multiple_to_argb(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PIL import Image
        import tempfile, os, requests, re

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

        # 5️⃣ Gửi từng ảnh theo thứ tự
        for idx, (path, img) in enumerate(images, start=1):

            # 🧩 A) Tạo tên preset từ tên file
            base = os.path.basename(path)
            name_no_ext = os.path.splitext(base)[0]

            # Giữ lại ký tự hợp lệ
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name_no_ext)

            # Giới hạn 20 ký tự
            preset_name = safe_name[:20] if len(safe_name) > 20 else safe_name
            if not preset_name:
                preset_name = f"Preset_{idx}"

            # 🧩 B) Tạo tên file BMP upload (dễ nhìn trong /edit)
            upload_filename = preset_name + ".bmp"

            while True:  # Vòng lặp hỗ trợ Retry nếu 401
                try:
                    # Chuyển ảnh sang vuông RGB
                    bmp_image = self._convert_to_square_rgb(w, img)

                    # Lưu ảnh BMP tạm
                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".bmp")
                    bmp_image.save(tmp_file.name, "BMP")
                    tmp_file.close()

                    # 📌 C) Upload file BMP với tên customs
                    url_upload = f"http://{ip}/upload"
                    with open(tmp_file.name, "rb") as f:
                        files = {
                            "data": (upload_filename, f, "image/bmp")
                        }
                        r = requests.post(url_upload, files=files, timeout=5)

                    # --- Xử lý lỗi PIN (401) ---
                    if r.status_code == 401:
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Thiết bị đang bị khóa (401)")
                        msg.setText(
                            "Thiết bị yêu cầu mã PIN để truy cập.\n"
                            "Bạn muốn làm gì?"
                        )
                        btn_open = msg.addButton("Mở trang PIN", QMessageBox.ActionRole)
                        btn_retry = msg.addButton("Gửi lại", QMessageBox.AcceptRole)
                        btn_cancel = msg.addButton("Hủy", QMessageBox.RejectRole)
                        msg.exec()

                        clicked = msg.clickedButton()

                        if clicked == btn_open:
                            QDesktopServices.openUrl(QUrl(f"http://{ip}/settings/sec"))
                            continue
                        elif clicked == btn_retry:
                            continue
                        else:
                            return

                    elif r.status_code != 200:
                        QMessageBox.warning(self, "Lỗi Upload",
                            f"Upload thất bại!\nHTTP {r.status_code}")
                        return

                    # 🌟 D) Lưu preset
                    url_state = f"http://{ip}/json/state"
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
                        "psave": idx,        # Lưu preset ID tăng dần
                        "n": preset_name      # 🌟 Đặt tên preset
                    }

                    r2 = requests.post(url_state, json=payload, timeout=5)
                    if r2.status_code != 200:
                        QMessageBox.warning(self, "Lỗi", f"Không lưu preset! HTTP {r2.status_code}")

                    # Thành công → break vòng retry
                    break

                except Exception as e:
                    QMessageBox.critical(self, "Lỗi", f"Lỗi khi gửi ảnh:\n{e}")
                    break

                finally:
                    # Xóa file tạm
                    if os.path.exists(tmp_file.name):
                        os.unlink(tmp_file.name)

        QMessageBox.information(self, "Hoàn tất", "🎉 Tất cả ảnh đã gửi và lưu preset thành công!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon = resource_path("assets/favicon.ico")
    app.setWindowIcon(QIcon(icon))
    win = BMPConverter()
    win.setWindowIcon(QIcon(icon))
    win.show()
    sys.exit(app.exec())
