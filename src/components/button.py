from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
)

from src.styles.button_style import (
    BUTTON_COLORS,
    BUTTON_STYLE,
    BUTTON_WHITE,
)
from src.themes.spacing import SPACING as SPACE


class ButtonIcon(QLabel):

    def __init__(self):
        super().__init__()

        self.icon_pixmap = QPixmap()

    def set_icon_pixmap(self, pixmap: QPixmap):
        self.icon_pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self.icon_pixmap.isNull():
            return

        painter = QPainter(self)

        x = (self.width() - self.icon_pixmap.width()) // 2
        y = (self.height() - self.icon_pixmap.height()) // 2

        painter.drawPixmap(x, y, self.icon_pixmap)


class Button(QPushButton):

    # ----- Settings -----
    ICON_SIZE = 16
    SPACING = SPACE[8]
    MARGIN = (
        SPACE[16],
        SPACE["legacy"][10],
        SPACE[16],
        SPACE["legacy"][10],
    )

    def __init__(
        self,
        text: str,
        icon: str | Path | None = None,
        variant: str = "outline",
        color: str = "blue",
        parent=None,
    ):
        super().__init__(parent)

        # ----- Data -----
        self.variant = variant
        self.color = color
        self.icon_path = Path(icon) if icon else None

        # ----- Button -----
        self.setObjectName("button")
        self.setStyleSheet(BUTTON_STYLE)

        self.setProperty("variant", self.variant)
        self.setProperty("color", self.color)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        super().setText("")

        # ----- Icon -----
        self.icon_label = ButtonIcon()

        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

        if self.icon_path:
            self.icon_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)

            self.render_icon(self.get_content_color())

        else:
            self.icon_label.hide()

        # ----- Text -----
        self.text_label = QLabel(text)
        self.text_label.setObjectName("buttonText")

        self.text_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )

        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

        self.set_text_color(self.get_content_color())

        # ----- Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING if self.icon_path else 0)

        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self.icon_path:
            layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.text_label, 0, Qt.AlignmentFlag.AlignCenter)

        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

    # ----- Content Color -----
    def get_content_color(self):
        if self.variant == "primary":
            return BUTTON_WHITE

        return BUTTON_COLORS[self.color]["base"]

    # ----- Text Color -----
    def set_text_color(self, color: str):
        self.text_label.setStyleSheet(f"""
            color: {color};
            background-color: transparent;
            border: none;
            """)

    # ----- Render Icon -----
    def render_icon(self, color: str):
        if not self.icon_path:
            return

        renderer = QSvgRenderer(str(self.icon_path))

        if not renderer.isValid():
            return

        pixmap = QPixmap(self.ICON_SIZE, self.ICON_SIZE)

        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)

        renderer.render(painter, QRectF(0, 0, self.ICON_SIZE, self.ICON_SIZE))

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)

        painter.fillRect(pixmap.rect(), QColor(color))

        painter.end()

        self.icon_label.set_icon_pixmap(pixmap)
