"""
Application Desktop PySide6 — Agent Affichage Sandbox.
DA premium : palette chaude ambre/crème, typographie propre, rendu Chromium étanche.
"""

import sys
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame, QLabel, QLineEdit, QPushButton,
    QRadioButton, QFileDialog, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect, QSizePolicy
)

from .utils import call_mistral_api
from agentAffichage.rendu.afficheur import afficherJoliment
from agentAffichage.pipeline import genererAffichage

# QWebEngineView est importé de manière lazy pour éviter les crashs macOS
_QWebEngineView = None

def _get_web_view_class():
    global _QWebEngineView
    if _QWebEngineView is None:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        _QWebEngineView = QWebEngineView
    return _QWebEngineView


# ─── Police propre ───────────────────────────────────────────────────────────

def _app_font() -> str:
    """Retourne la meilleure police disponible sur le système."""
    from PySide6.QtGui import QFontDatabase
    preferred = ["Helvetica Neue", "SF Pro Text", "Segoe UI", "Roboto", "Helvetica", "Arial"]
    available = QFontDatabase.families()
    for f in preferred:
        if f in available:
            return f
    return "Helvetica"


# ─── Widgets ─────────────────────────────────────────────────────────────────

class UserMessageWidget(QWidget):
    """Bulle de message utilisateur, alignée à droite."""

    def __init__(self, content: str, font_family: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(100, 6, 0, 6)
        layout.setSpacing(10)
        layout.addStretch(1)

        bubble = QFrame()
        bubble.setStyleSheet(
            "background-color: #F5F0EB; border: 1px solid #E8E2DB;"
            "border-radius: 20px; border-bottom-right-radius: 6px;"
        )
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(16, 12, 16, 12)

        lbl = QLabel(content)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setStyleSheet(
            f"color: #1a1a1a; font-size: 15px; background: transparent;"
            f"font-family: '{font_family}';"
        )
        b_lay.addWidget(lbl)
        layout.addWidget(bubble)

        avatar = QLabel("U")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: #78716C; color: #fff; border-radius: 15px;"
            f"font-weight: bold; font-size: 12px; font-family: '{font_family}';"
        )
        layout.addWidget(avatar, alignment=Qt.AlignTop)


class AgentMessageWidget(QWidget):
    """Message agent : rendu Chromium isolé via QWebEngineView."""

    def __init__(self, html_content: str, font_family: str, parent=None):
        super().__init__(parent)
        self._html_content = html_content

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 100, 2)
        layout.setSpacing(10)

        avatar = QLabel("A")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: #D97706; color: #fff; border-radius: 15px;"
            f"font-weight: bold; font-size: 12px; font-family: '{font_family}';"
        )
        layout.addWidget(avatar, alignment=Qt.AlignTop)

        WebView = _get_web_view_class()
        self.web_view = WebView()
        self.web_view.setHtml(html_content)
        self.web_view.setStyleSheet("background: transparent; border: none;")
        try:
            self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        except Exception:
            pass

        lines = max(html_content.count("\n"), html_content.count("<li"), 4)
        self.web_view.setFixedHeight(max(100, min(650, lines * 22 + 80)))
        self.web_view.loadFinished.connect(self._adjust_height)

        layout.addWidget(self.web_view, 1)

    def _adjust_height(self, success):
        if success:
            self.web_view.page().runJavaScript(
                "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)",
                self._apply_height
            )

    def _apply_height(self, height):
        if height and isinstance(height, (int, float)) and height > 0:
            self.web_view.setFixedHeight(int(height) + 6)


class PromptBarWidget(QWidget):
    """Barre de saisie fixe en bas — champ + bouton Envoyer."""

    submitted = Signal(str)

    def __init__(self, font_family: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #FAF9F7; border-top: 1px solid #E8E4DF;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(60, 12, 60, 16)

        pill = QFrame()
        pill.setStyleSheet(
            "QFrame {"
            "  background-color: #ffffff;"
            "  border: 1px solid #D6D3D1;"
            "  border-radius: 22px;"
            "}"
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 18))
        pill.setGraphicsEffect(shadow)

        p_lay = QHBoxLayout(pill)
        p_lay.setContentsMargins(18, 6, 6, 6)
        p_lay.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Envoyer un message...")
        self.input_field.setStyleSheet(
            f"QLineEdit {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  font-size: 15px;"
            f"  color: #1a1a1a;"
            f"  font-family: '{font_family}';"
            f"}}"
        )
        self.input_field.returnPressed.connect(self._submit)
        p_lay.addWidget(self.input_field, 1)

        btn = QPushButton("Envoyer")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #D97706;"
            f"  color: #ffffff;"
            f"  border: 1px solid #D97706;"
            f"  border-radius: 16px;"
            f"  padding: 0px 18px;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"  font-family: '{font_family}';"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #B45309;"
            f"  border-color: #B45309;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #92400E;"
            f"  border-color: #92400E;"
            f"}}"
        )
        btn.clicked.connect(self._submit)
        p_lay.addWidget(btn)

        outer.addWidget(pill)

    def _submit(self):
        t = self.input_field.text().strip()
        if t:
            self.submitted.emit(t)
            self.input_field.clear()

    def focus_input(self):
        self.input_field.setFocus()


# ─── Fenêtre Principale ─────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Affichage — Sandbox")
        self.resize(1200, 800)

        self.font_family = _app_font()
        self.messages: List[Dict[str, str]] = []
        self.mode = "Utilisateur"
        self.api_key: Optional[str] = os.getenv("MISTRAL_API_KEY")
        self.chat_history: List[Dict] = []
        self.current_chat_id: Optional[str] = None
        self.uploaded_files_objs: List = []

        self._build_ui()

    def _build_ui(self):
        ff = self.font_family
        root = QWidget()
        root.setStyleSheet(f"font-family: '{ff}'; background-color: #FAF9F7; color: #1a1a1a;")
        self.setCentralWidget(root)

        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setFixedWidth(270)
        sidebar.setStyleSheet(
            f"background-color: #F0EFED; border-right: 1px solid #E0DFDD;"
            f"font-family: '{ff}';"
        )
        s = QVBoxLayout(sidebar)
        s.setContentsMargins(16, 24, 16, 20)
        s.setSpacing(0)

        lbl_t = QLabel("Agent Affichage")
        lbl_t.setStyleSheet(f"font-size: 17px; font-weight: bold; color: #1a1a1a; background: transparent; font-family: '{ff}';")
        s.addWidget(lbl_t)

        lbl_s = QLabel("Sandbox de Visualisation")
        lbl_s.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #D97706; margin-bottom: 18px; background: transparent; font-family: '{ff}';")
        s.addWidget(lbl_s)

        btn_new = QPushButton("Nouveau chat")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet(
            f"background-color: #D97706; color: #fff; border: none; border-radius: 10px;"
            f"padding: 10px 14px; font-size: 14px; font-weight: 600; font-family: '{ff}';"
        )
        btn_new.clicked.connect(self._reset_chat)
        s.addWidget(btn_new)
        s.addSpacing(20)

        s.addWidget(self._sec("CONVERSATIONS"))
        s.addSpacing(4)

        self.chat_list = QListWidget()
        self.chat_list.setStyleSheet(
            f"background: transparent; border: none; outline: none; font-family: '{ff}';"
        )
        self.chat_list.itemClicked.connect(self._on_history_click)
        s.addWidget(self.chat_list, 1)
        s.addSpacing(16)

        s.addWidget(self._sec("CONFIGURATION"))
        s.addSpacing(6)

        self.radio_user = QRadioButton("Utilisateur (API Mistral)")
        self.radio_agent = QRadioButton("Agent (Rendu Direct)")
        self.radio_user.setChecked(True)
        for r in (self.radio_user, self.radio_agent):
            r.setStyleSheet(f"background: transparent; color: #44403C; font-size: 13px; font-family: '{ff}'; spacing: 8px;")
        self.radio_user.toggled.connect(self._on_mode)
        s.addWidget(self.radio_user)
        s.addWidget(self.radio_agent)
        s.addSpacing(8)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Clé API Mistral...")
        self.api_input.setEchoMode(QLineEdit.Password)
        if self.api_key:
            self.api_input.setText(self.api_key)
        self.api_input.textChanged.connect(lambda t: setattr(self, 'api_key', t.strip()))
        self.api_input.setStyleSheet(
            f"background: #fff; color: #1a1a1a; border: 1px solid #D6D3D1; border-radius: 8px;"
            f"padding: 7px 10px; font-size: 13px; font-family: '{ff}';"
        )
        s.addWidget(self.api_input)
        s.addSpacing(16)

        s.addWidget(self._sec("FICHIERS"))
        s.addSpacing(6)

        btn_f = QPushButton("Ajouter des fichiers")
        btn_f.setCursor(Qt.PointingHandCursor)
        btn_f.setStyleSheet(
            f"background: transparent; color: #44403C; border: 1px solid #D6D3D1;"
            f"border-radius: 10px; padding: 8px 12px; font-size: 13px; font-weight: 500;"
            f"font-family: '{ff}';"
        )
        btn_f.clicked.connect(self._select_files)
        s.addWidget(btn_f)
        s.addSpacing(4)

        self.files_lbl = QLabel("Aucun fichier sélectionné")
        self.files_lbl.setWordWrap(True)
        self.files_lbl.setStyleSheet(f"font-size: 12px; color: #78716C; background: transparent; font-family: '{ff}';")
        s.addWidget(self.files_lbl)

        root_lay.addWidget(sidebar)

        # ── Zone Centrale ───────────────────────────────────────────
        center = QWidget()
        center.setStyleSheet("background-color: #FAF9F7;")
        c_lay = QVBoxLayout(center)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setStyleSheet("background-color: #FAF9F7; border: none;")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #FAF9F7;")
        self.msg_layout = QVBoxLayout(self.scroll_content)
        self.msg_layout.setContentsMargins(40, 20, 40, 20)
        self.msg_layout.setSpacing(4)
        self.msg_layout.addStretch(1)

        self.scroll.setWidget(self.scroll_content)
        c_lay.addWidget(self.scroll, 1)

        self.prompt_bar = PromptBarWidget(ff)
        self.prompt_bar.submitted.connect(self._on_submit)
        c_lay.addWidget(self.prompt_bar)

        root_lay.addWidget(center, 1)
        self._show_welcome()

    def _sec(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: #A8A29E; letter-spacing: 1px;"
            f"background: transparent; font-family: '{self.font_family}';"
        )
        return lbl

    def _show_welcome(self):
        self._clear_msgs()
        ff = self.font_family
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(60, 80, 60, 40)

        t = QLabel("Comment puis-je vous aider ?")
        t.setStyleSheet(f"font-size: 26px; font-weight: 600; color: #1a1a1a; background: transparent; font-family: '{ff}';")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        sub = QLabel("Posez une question ou soumettez du contenu\npour générer une visualisation interactive.")
        sub.setStyleSheet(f"font-size: 14px; color: #A8A29E; margin-top: 10px; background: transparent; font-family: '{ff}';")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)

        self.msg_layout.insertWidget(0, w)

    def _clear_msgs(self):
        while self.msg_layout.count() > 1:
            c = self.msg_layout.takeAt(0)
            if c.widget():
                c.widget().deleteLater()

    def _scroll_bottom(self):
        QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    @Slot(str)
    def _on_submit(self, prompt: str):
        if not prompt:
            return
        if not self.messages:
            self.current_chat_id = str(uuid.uuid4())[:8]
            self._clear_msgs()

        self.messages.append({"role": "user", "content": prompt})
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, UserMessageWidget(prompt, self.font_family))

        fichiers = self.uploaded_files_objs if self.uploaded_files_objs else None

        if self.mode == "Utilisateur":
            # Le curseur d'attente couvre les deux appels réseau enchaînés
            # (conversation puis sélection de widget), pas juste le premier.
            QApplication.setOverrideCursor(Qt.WaitCursor)
            response = call_mistral_api(prompt, self.api_key)
            html = genererAffichage(response, fichiers, api_key=self.api_key)
            QApplication.restoreOverrideCursor()
        else:
            # Mode "Agent (Rendu Direct)" : on garde un accès direct au rendu
            # seul, sans passer par la sélection — pour taper un bloc widget à
            # la main et tester registre.py/afficheur.py isolément.
            response = prompt
            html = afficherJoliment(response, fichiers)

        self.messages.append({"role": "agent", "content": html})
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, AgentMessageWidget(html, self.font_family))

        self._scroll_bottom()
        self._save_chat()
        self.prompt_bar.focus_input()

    def _reset_chat(self):
        if self.messages:
            self._save_chat()
        self.messages = []
        self.current_chat_id = None
        self._show_welcome()
        self.prompt_bar.focus_input()

    def _save_chat(self):
        if not self.messages:
            return
        cid = self.current_chat_id or str(uuid.uuid4())[:8]
        first = self.messages[0]["content"]
        title = first[:28] + ("..." if len(first) > 28 else "")
        data = {"id": cid, "title": title, "messages": self.messages.copy(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        ids = [c["id"] for c in self.chat_history]
        if cid in ids:
            for i, c in enumerate(self.chat_history):
                if c["id"] == cid:
                    self.chat_history[i] = data
                    break
        else:
            self.chat_history.append(data)
        self.current_chat_id = cid
        self._refresh_history()

    def _refresh_history(self):
        self.chat_list.clear()
        for ch in reversed(self.chat_history):
            item = QListWidgetItem(ch["title"])
            item.setData(Qt.UserRole, ch["id"])
            self.chat_list.addItem(item)

    def _on_history_click(self, item: QListWidgetItem):
        cid = item.data(Qt.UserRole)
        for ch in self.chat_history:
            if ch["id"] == cid:
                self.messages = ch["messages"].copy()
                self.current_chat_id = cid
                self._rebuild()
                break

    def _rebuild(self):
        self._clear_msgs()
        for m in self.messages:
            if m["role"] == "user":
                w = UserMessageWidget(m["content"], self.font_family)
            else:
                w = AgentMessageWidget(m["content"], self.font_family)
            self.msg_layout.insertWidget(self.msg_layout.count() - 1, w)
        self._scroll_bottom()

    def _select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Sélectionner des fichiers")
        if paths:
            class _F:
                def __init__(self, p):
                    self.name = os.path.basename(p)
                    self._p = p
                def getvalue(self):
                    with open(self._p, "rb") as f:
                        return f.read()
            self.uploaded_files_objs = [_F(p) for p in paths]
            self.files_lbl.setText(f"{len(paths)} fichier(s)\n" + ", ".join(os.path.basename(p) for p in paths))

    def _on_mode(self):
        self.mode = "Utilisateur" if self.radio_user.isChecked() else "Agent"
        self.api_input.setVisible(self.mode == "Utilisateur")
