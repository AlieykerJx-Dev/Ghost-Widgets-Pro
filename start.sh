#!/bin/bash
# Obtener ruta absoluta de la carpeta de la app
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Entorno Virtual Portable
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install PyQt5 PyQtWebEngine psutil --quiet
else
    source venv/bin/activate
fi

# 2. Función para crear el lanzador .desktop
create_launcher() {
    local TARGET_PATH=$1
    echo "[Desktop Entry]
Type=Application
Name=Ghost Widgets Pro
Comment=Aesthetic Widgets by AlieykerJx
Exec=\"$DIR/start.sh\"
Icon=$DIR/assets/icons/ghost_icon.png
Terminal=false
Path=$DIR
Categories=Utility;
" > "$TARGET_PATH"
    chmod +x "$TARGET_PATH"
}

# 3. Crear lanzador en la carpeta de la app
create_launcher "$DIR/GhostWidgetsPro.desktop"

# 4. Crear lanzador en el Escritorio (Auto-detección de idioma)
if [ -d "$HOME/Escritorio" ]; then
    create_launcher "$HOME/Escritorio/GhostWidgetsPro.desktop"
elif [ -d "$HOME/Desktop" ]; then
    create_launcher "$HOME/Desktop/GhostWidgetsPro.desktop"
fi

# 5. Ejecutar App usando el binario del venv
python3 src/main.py

