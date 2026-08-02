#!/usr/bin/env python3
"""
Point d'entrée principal pour lancer l'application Desktop PySide6.
Exécuter avec : python3 main.py
"""

import sys
import os

# Nécessaire sur macOS pour éviter les crashs Chromium
os.environ["QT_MAC_WANTS_LAYER"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"

# Ajouter le dossier courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from sandbox.app import MainWindow


def main():
    # Initialiser QWebEngine AVANT QApplication
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        QtWebEngineQuick.initialize()
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
