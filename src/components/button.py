from pathlib import Path

from PySide6.QtCore import (
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
)

from src.styles.button_style import BUTTON_STYLE
from src.themes.color import (
    BUTTON_COLORS,
    BUTTON_WHITE,
)


class Button(QPushButton):

    # ----- Setting -----
    ICON_SIZE = 16
    SPACING = 8
    MARGIN = (16, 10, 16, 10)

    def __init__(
        self,
        text: str,
        icon: Path | None = None,
        variant: str = "outline",
        color: str = "blue",
    ):
        super().__init__()

        # ----- Button Data -----
        self.variant = variant
        self.color = color

        # ----- Button Setup -----
        self.setObjectName("button")
        self.setProperty("variant", variant)
        self.setProperty("color", color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(BUTTON_STYLE)

        # ----- Icon -----
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(
            self.ICON_SIZE,
            self.ICON_SIZE,
        )

        # ----- Text -----
        self.text_label = QLabel(text)
        self.text_label.setObjectName("buttonText")

        # ----- Allow Button Click Through Labels -----
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # ----- Content Color -----
        content_color = (
            BUTTON_WHITE if variant == "primary" else BUTTON_COLORS[color]["base"]
        )

        self.text_label.setStyleSheet(f"color: {content_color};")

        if icon:
            self.set_icon_color(
                icon,
                content_color,
            )

        # ----- Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

    # ----- Icon Color -----
    def set_icon_color(
        self,
        icon: Path,
        color: str,
    ):
        renderer = QSvgRenderer(str(icon))

        if not renderer.isValid():
            return

        # ----- Pixmap -----
        pixmap = QPixmap(
            self.ICON_SIZE,
            self.ICON_SIZE,
        )
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)

        # ----- Render SVG -----
        renderer.render(
            painter,
            QRectF(
                0,
                0,
                self.ICON_SIZE,
                self.ICON_SIZE,
            ),
        )

        # ----- Recolor SVG -----
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)

        painter.fillRect(
            pixmap.rect(),
            QColor(color),
        )

        painter.end()

        self.icon_label.setPixmap(pixmap)
