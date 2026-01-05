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

# --- LÓGICA DE PORTABILIDAD 10,000,000% ---
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
        # Si la ruta es local, asegurar que sea absoluta para el motor web
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
            item = self.main_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        t = TRAD[self.st['lang']]
        if self.st.get("bg"): self.apply_bg(self.st["bg"])

        header = QLabel()
        if os.path.exists(HEADER_PATH):
            header.setPixmap(QPixmap(HEADER_PATH).scaledToWidth(410, Qt.SmoothTransformation))
        header.setAlignment(Qt.AlignCenter); self.main_container.addWidget(header)

        self.lbl_stats = QLabel("CARGANDO..."); self.lbl_stats.setStyleSheet("color: #00ff00; font-family: 'Consolas';")
        self.main_container.addWidget(self.lbl_stats)

        self.list = QListWidget(); self.main_container.addWidget(self.list)

        btn_lay = QHBoxLayout()
        btn_lay.addWidget(self.create_btn(t["add"], self.add_w, "#000", "#00ff00"))
        btn_lay.addWidget(self.create_btn(t["set"], self.open_settings, "#000", "#00ff00"))
        self.main_container.addLayout(btn_lay)
        self.refresh_list()

    def create_btn(self, text, func, bg, col):
        btn = QPushButton(text); btn.clicked.connect(func)
        btn.setStyleSheet(f"background: {bg}; color: {col}; border: 2px solid {col}; border-radius: 8px; padding: 10px; font-weight: bold;")
        return btn

    def refresh_list(self):
        self.list.clear()
        for i, d in enumerate(self.widgets_data):
            item = QListWidgetItem(self.list); w = QWidget(); l = QHBoxLayout(w)
            active = i in self.active_widgets
            btn = QPushButton("STOP" if active else "START")
            btn.clicked.connect(lambda _, x=i: self.toggle_widget(x))
            l.addWidget(QLabel(d['nombre'])); l.addStretch(); l.addWidget(btn)
            item.setSizeHint(w.sizeHint()); self.list.setItemWidget(item, w)

    def add_w(self):
        t = TRAD[self.st['lang']]
        name, ok1 = QInputDialog.getText(self, t["add"], t["w_name"]+":")
        if ok1 and name:
            url, ok2 = QInputDialog.getText(self, t["add"], t["w_url"]+":")
            if ok2 and url:
                self.widgets_data.append({"nombre": name, "url": url, "x": 100, "y": 100, "w": 400, "h": 300, "active": False})
                self.save_all(); self.refresh_list()

    def toggle_widget(self, i):
        if i in self.active_widgets:
            self.active_widgets[i].close(); del self.active_widgets[i]
            self.widgets_data[i]["active"] = False
        else:
            self.active_widgets[i] = OverlayWidget(self.widgets_data[i], self.save_all)
            self.widgets_data[i]["active"] = True
        self.save_all(); self.refresh_list(); gc.collect()

    def update_stats(self):
        try: self.lbl_stats.setText(f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")
        except: pass

    def apply_bg(self, path):
        # Convertir a ruta absoluta para visualización si es relativa
        full_path = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
        if os.path.exists(full_path):
            pix = QPixmap(full_path).scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            pal = self.palette(); pal.setBrush(QPalette.Window, QBrush(pix)); self.setPalette(pal)

    def open_settings(self):
        t = TRAD[self.st['lang']]; dlg = QDialog(self); l = QVBoxLayout(dlg)
        btn_bg = QPushButton("Cambiar Fondo"); btn_bg.clicked.connect(self.pick_bg); l.addWidget(btn_bg)
        cmb = QComboBox(); cmb.addItems(["es", "en", "pt"]); cmb.setCurrentText(self.st['lang']); l.addWidget(cmb)
        btn_ok = QPushButton(t["save"]); btn_ok.clicked.connect(lambda: self.apply_set(cmb.currentText(), dlg)); l.addWidget(btn_ok)
        dlg.exec_()

    def pick_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Fondo", BASE_DIR, "Images (*.png *.jpg *.jpeg)")
        if path:
            # SI LA IMAGEN ESTÁ EN LA APP, GUARDAR RUTA RELATIVA PARA PORTABILIDAD
            if BASE_DIR in path: path = os.path.relpath(path, BASE_DIR)
            self.st['bg'] = path; self.apply_bg(path); self.save_all()

    def apply_set(self, lang, dlg):
        self.st['lang'] = lang; self.save_all(); dlg.accept(); self.render_content()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else self.style().standardIcon(60))
        m = QMenu(); m.addAction("Abrir", self.show); m.addAction("Salir", QApplication.quit)
        self.tray.setContextMenu(m); self.tray.show()

    def closeEvent(self, event):
        event.ignore(); self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    m = GhostManager(); m.show(); sys.exit(app.exec_())
