from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
)

from src.styles.sidebar_menu_style import SIDEBAR_MENU_STYLE
from src.themes.color import (
    MENU_TEXT,
    MENU_TEXT_HOVER,
    MENU_TEXT_ACTIVE,
    MENU_BG_HOVER,
    MENU_BG_ACTIVE,
)


class MenuButton(QPushButton):

    # ----- Settings -----
    ICON_SIZE = 20
    SPACING = 12
    DURATION = 150

    def __init__(
        self,
        icon: Path,
        name: str,
        page: str,
    ):
        super().__init__()

        # ----- Button Data -----
        self.page = page
        self.icon_path = icon
        self.active = False
        self.background_color = QColor("transparent")

        # ----- Button Setup -----
        self.setObjectName("menuButton")
        self.setStyleSheet(SIDEBAR_MENU_STYLE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        # ----- Icon -----
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(
            self.ICON_SIZE,
            self.ICON_SIZE,
        )

        # ----- Text -----
        self.text_label = QLabel(name)
        self.text_label.setObjectName("menuButtonText")

        # ----- Allow Button Click Through Labels -----
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # ----- Button Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(self.SPACING)

        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()

        # ----- Default State -----
        self.set_icon_color(MENU_TEXT)
        self.set_text_color(MENU_TEXT)

        # ----- Hover Animation -----
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(self.DURATION)
        self.animation.valueChanged.connect(self.update_background)

    # ----- Icon Color -----
    def set_icon_color(self, color):
        pixmap = QPixmap(str(self.icon_path))

        if pixmap.isNull():
            return

        pixmap = pixmap.scaled(
            self.ICON_SIZE,
            self.ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        painter = QPainter(pixmap)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)

        painter.fillRect(
            pixmap.rect(),
            QColor(color),
        )

        painter.end()

        self.icon_label.setPixmap(pixmap)

    # ----- Text Color -----
    def set_text_color(self, color):
        self.text_label.setStyleSheet(f"color: {color};")

    # ----- Background Animation -----
    def animate_background(self, color):
        self.animation.stop()

        self.animation.setStartValue(self.background_color)

        self.animation.setEndValue(QColor(color))

        self.animation.start()

    # ----- Update Background -----
    def update_background(self, color):
        self.background_color = color
        self.update()

    # ----- Active State -----
    def set_active(self, active):
        self.active = active

        if active:
            self.set_icon_color(MENU_TEXT_ACTIVE)
            self.set_text_color(MENU_TEXT_ACTIVE)
            self.animate_background(MENU_BG_ACTIVE)

        else:
            self.set_icon_color(MENU_TEXT)
            self.set_text_color(MENU_TEXT)
            self.animate_background("transparent")

    # ----- Hover Enter -----
    def enterEvent(self, event):
        if not self.active:
            self.set_icon_color(MENU_TEXT_HOVER)
            self.set_text_color(MENU_TEXT_HOVER)
            self.animate_background(MENU_BG_HOVER)

        super().enterEvent(event)

    # ----- Hover Leave -----
    def leaveEvent(self, event):
        if not self.active:
            self.set_icon_color(MENU_TEXT)
            self.set_text_color(MENU_TEXT)
            self.animate_background("transparent")

        super().leaveEvent(event)

    # ----- Draw Background -----
    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.background_color)

        painter.drawRoundedRect(
            self.rect(),
            8,
            8,
        )

        painter.end()

        super().paintEvent(event)
