import sys, json, os, psutil, gc
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QListWidget, QListWidgetItem, QLabel,
                             QInputDialog, QSystemTrayIcon, QMenu, QComboBox,
                             QDialog, QFileDialog, QFrame, QLineEdit)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtCore import Qt, QUrl, QTimer, QPoint, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPalette, QBrush, QColor

# --- OPTIMIZACIÓN EXTREMA ---
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-gpu-vsync --enable-gpu-rasterization --no-sandbox "
    "--ignore-gpu-blocklist --disable-2d-canvas-antialiasing "
    "--num-raster-threads=1"
)

# --- LÓGICA DE PORTABILIDAD MAESTRA ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
os.chdir(BASE_DIR)

CONFIG_FILE = os.path.join(BASE_DIR, "config", "config.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "config", "settings.json")
ICON_PATH = os.path.join(BASE_DIR, "assets", "icons", "ghost_icon.png")
HEADER_PATH = os.path.join(BASE_DIR, "assets", "icons", "app_header.png")

TRAD = {
    "es": {"add": "Añadir Widget +", "set": "Ajustes", "move": "mover", "done": "LISTO", "act": "Activos", "follow": "SÍGUEME", "save": "GUARDAR", "start_all": "Iniciar Todos", "stop_all": "Detener Todos", "edit": "Editar", "w_name": "Nombre", "w_url": "URL/Ruta", "browse": "Explorar"},
    "en": {"add": "Add Widget +", "set": "Settings", "move": "move", "done": "DONE", "act": "Active", "follow": "FOLLOW ME", "save": "SAVE", "start_all": "Play All", "stop_all": "Pause All", "edit": "Edit", "w_name": "Name", "w_url": "URL/Path", "browse": "Browse"},
    "pt": {"add": "Adicionar Widget +", "set": "Ajustes", "move": "mover", "done": "PRONTO", "act": "Ativos", "follow": "SIGA-ME", "save": "SALVAR", "start_all": "Iniciar Todos", "stop_all": "Parar Todos", "edit": "Editar", "w_name": "Nome", "w_url": "Caminho", "browse": "Procurar"}
}

class OverlayWidget(QWidget):
    def __init__(self, data, save_callback):
        super().__init__()
        self.data, self.save_callback = data, save_callback
        self.web = QWebEngineView(self)
        s = self.web.settings()
        s.setAttribute(QWebEngineSettings.ShowScrollBars, False)
        self.web.page().setBackgroundColor(Qt.transparent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.addWidget(self.web)

        u = data['url']
        target_url = QUrl.fromLocalFile(os.path.abspath(u)) if os.path.exists(u) else QUrl(u if "://" in u else "http://"+u)
        self.web.setUrl(target_url)
        self.setGeometry(data.get('x', 100), data.get('y', 100), data.get('w', 400), data.get('h', 300))
        self.init_ghost_mode()

    def init_ghost_mode(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.web.setEnabled(False)
        self.show()

    def set_edit_mode(self, mode):
        if mode:
            self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.web.setEnabled(True)
            self.show()
        else:
            self.data.update({"x": self.x(), "y": self.y(), "w": self.width(), "h": self.height()})
            self.init_ghost_mode()
            self.save_callback()

class GhostManager(QWidget):
    def __init__(self):
        super().__init__()
        self.active_widgets, self.edit_states = {}, {}
        self.load_data()
        self.init_ui()
        self.init_tray()
        QTimer.singleShot(500, self.restore_widgets)

    def load_data(self):
        try:
            self.st = json.load(open(SETTINGS_FILE)) if os.path.exists(SETTINGS_FILE) else {"lang": "es", "bg": ""}
            self.widgets_data = json.load(open(CONFIG_FILE)) if os.path.exists(CONFIG_FILE) else []
        except: self.st, self.widgets_data = {"lang": "es", "bg": ""}, []

    def save_all(self):
        with open(CONFIG_FILE, 'w') as f: json.dump(self.widgets_data, f, indent=4)
        with open(SETTINGS_FILE, 'w') as f: json.dump(self.st, f, indent=4)

    def restore_widgets(self):
        for i, d in enumerate(self.widgets_data):
            if d.get("active"): self.toggle_widget(i)

    def init_ui(self):
        self.setFixedSize(430, 800)
        self.setWindowTitle("Ghost Widgets Pro")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.main_container = QVBoxLayout(self)
        self.render_content()
        self.stat_timer = QTimer(); self.stat_timer.timeout.connect(self.update_stats); self.stat_timer.start(2000)

    def render_content(self):
        while self.main_container.count():
            child = self.main_container.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            elif child.layout(): self.clear_layout(child.layout())

        with open(os.path.join(BASE_DIR, "config", "strings.json"), "r") as f: translations = json.load(f); t = translations[self.st["lang"]]
        if self.st.get("bg"): self.apply_bg(self.st["bg"])

        header = QLabel()
        if os.path.exists(HEADER_PATH):
            header.setPixmap(QPixmap(HEADER_PATH).scaledToWidth(410, Qt.SmoothTransformation))
        header.setAlignment(Qt.AlignCenter); self.main_container.addWidget(header)

        # MARCO DE ESTADÍSTICAS PRO
        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet("background: rgba(0,0,0,220); border: 2px solid #00ff00; border-radius: 10px;")
        self.stats_frame.setFixedHeight(50)
        s_lay = QHBoxLayout(self.stats_frame)
        self.lbl_stats = QLabel("CARGANDO..."); self.lbl_stats.setAlignment(Qt.AlignCenter)
        self.lbl_stats.setStyleSheet("color: #00ff00; font-family: 'Consolas'; font-size: 13px; font-weight: bold; border: none;")
        s_lay.addWidget(self.lbl_stats); self.main_container.addWidget(self.stats_frame)

        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { background: rgba(0,0,0,160); border-radius: 12px; border: 1px solid #333; }")
        self.main_container.addWidget(self.list)

        # BOTONES DE CONTROL (START/STOP ALL)
        ctrl_lay = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(self.create_btn(t["start_all"], self.start_all_w, "#111", "#00ff00"))
        row1.addWidget(self.create_btn(t["stop_all"], self.stop_all_w, "#111", "#ff4d4d"))
        row2 = QHBoxLayout()
        row2.addWidget(self.create_btn(t["add"], self.add_w, "#000", "#00ff00", pro=True))
        row2.addWidget(self.create_btn(t["set"], self.open_settings, "#000", "#00ff00", pro=True))
        ctrl_lay.addLayout(row1); ctrl_lay.addLayout(row2)
        self.main_container.addLayout(ctrl_lay)

        # FOOTER CON REDES SOCIALES
        footer = QVBoxLayout()
        follow = QLabel(t["follow"]); follow.setStyleSheet("color: #00ff00; font-size: 10px; font-weight: bold;"); follow.setAlignment(Qt.AlignCenter)
        links = QHBoxLayout()
        fb = QLabel("<a href='https://www.facebook.com/AlieykerJx1/' style='color:#00ff00; text-decoration:none;'>FACEBOOK</a>")
        tw = QLabel("<a href='https://www.twitch.tv/jexuslivee' style='color:#00ff00; text-decoration:none;'>TWITCH</a>")
        for l in [fb, tw]: l.setOpenExternalLinks(True); l.setAlignment(Qt.AlignCenter); links.addWidget(l)
        footer.addWidget(follow); footer.addLayout(links)
        self.main_container.addLayout(footer)

        self.refresh_list()

    def create_btn(self, text, func, bg, col, pro=False):
        btn = QPushButton(text); btn.clicked.connect(func)
        p = "14px" if pro else "10px"
        btn.setStyleSheet(f"QPushButton{{background: {bg}; color: {col}; border: 2px solid {col}; border-radius: 8px; font-weight: bold; padding: {p};}} QPushButton:hover{{background: {col}; color: #000;}}")
        return btn

    def refresh_list(self):
        self.list.clear(); with open(os.path.join(BASE_DIR, "config", "strings.json"), "r") as f: translations = json.load(f); t = translations[self.st["lang"]]
        for i, d in enumerate(self.widgets_data):
            item = QListWidgetItem(self.list); w = QWidget(); l = QHBoxLayout(w)
            active, editing = i in self.active_widgets, self.edit_states.get(i, False)
            btn = QPushButton("STOP" if active else "START"); btn.setFixedSize(70, 32)
            btn.setStyleSheet(f"background: {'#ff4d4d' if active else '#2ecc71'}; color: white; border-radius: 6px; font-weight: bold;")
            btn.clicked.connect(lambda _, x=i: self.toggle_widget(x))
            mv = QPushButton(t["done"] if editing else t["move"]); mv.setFixedSize(70, 32)
            mv.setStyleSheet(f"background: {'#00ff00' if editing else '#f1c40f'}; color: black; border-radius: 6px; font-weight: bold;")
            mv.setEnabled(active); mv.clicked.connect(lambda _, x=i: self.toggle_edit(x))
            l.addWidget(QLabel(f"<b style='color:white;'>{d['nombre']}</b>")); l.addStretch(); l.addWidget(btn); l.addWidget(mv)
            item.setSizeHint(w.sizeHint()); self.list.setItemWidget(item, w)

    def toggle_widget(self, i):
        if i in self.active_widgets:
            self.active_widgets[i].close(); del self.active_widgets[i]
            self.widgets_data[i]["active"] = False
        else:
            self.active_widgets[i] = OverlayWidget(self.widgets_data[i], self.save_all)
            self.widgets_data[i]["active"] = True
        self.save_all(); self.refresh_list(); gc.collect()

    def toggle_edit(self, i):
        curr = self.edit_states.get(i, False)
        self.edit_states[i] = not curr
        self.active_widgets[i].set_edit_mode(not curr)
        self.refresh_list()

    def start_all_w(self):
        for i in range(len(self.widgets_data)):
            if i not in self.active_widgets: self.toggle_widget(i)

    def stop_all_w(self):
        for i in list(self.active_widgets.keys()): self.toggle_widget(i)

    def add_w(self):
        with open(os.path.join(BASE_DIR, "config", "strings.json"), "r") as f: translations = json.load(f); t = translations[self.st["lang"]]
        name, ok1 = QInputDialog.getText(self, t["add"], t["w_name"]+":")
        if ok1 and name:
            url, ok2 = QInputDialog.getText(self, t["add"], t["w_url"]+":")
            if ok2 and url:
                self.widgets_data.append({"nombre": name, "url": url, "x": 100, "y": 100, "w": 400, "h": 300, "active": False})
                self.save_all(); self.refresh_list()

    def update_stats(self):
        with open(os.path.join(BASE_DIR, "config", "strings.json"), "r") as f: translations = json.load(f); t = translations[self.st["lang"]]
        try: self.lbl_stats.setText(f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}% | {t['act']}: {len(self.active_widgets)}")
        except: pass

    def apply_bg(self, path):
        full_path = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
        if os.path.exists(full_path):
            pix = QPixmap(full_path).scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            pal = self.palette(); pal.setBrush(QPalette.Window, QBrush(pix)); self.setPalette(pal)

    def open_settings(self):
        with open(os.path.join(BASE_DIR, "config", "strings.json"), "r") as f: translations = json.load(f); t = translations[self.st["lang"]]; dlg = QDialog(self); l = QVBoxLayout(dlg)
        btn_bg = QPushButton("Cambiar Fondo"); btn_bg.clicked.connect(self.pick_bg); l.addWidget(btn_bg)
        cmb = QComboBox(); cmb.addItems(["es", "en", "pt"]); cmb.setCurrentText(self.st['lang']); l.addWidget(cmb)
        btn_ok = QPushButton(t["save"]); btn_ok.clicked.connect(lambda: self.apply_set(cmb.currentText(), dlg)); l.addWidget(btn_ok)
        dlg.exec_()

    def pick_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Fondo", BASE_DIR, "Images (*.png *.jpg *.jpeg)")
        if path:
            if BASE_DIR in path: path = os.path.relpath(path, BASE_DIR)
            self.st['bg'] = path; self.apply_bg(path); self.save_all()

    def apply_set(self, lang, dlg):
        self.st['lang'] = lang; self.save_all(); dlg.accept(); self.render_content()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else self.style().standardIcon(60))
        m = QMenu(); m.addAction("Abrir", self.show); m.addAction("Salir", QApplication.quit)
        self.tray.setContextMenu(m); self.tray.show()

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            elif child.layout(): self.clear_layout(child.layout())

    def closeEvent(self, event):
        event.ignore(); self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    m = GhostManager(); m.show(); sys.exit(app.exec_())
