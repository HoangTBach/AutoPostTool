from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QRectF,
    Qt,
    QVariantAnimation,
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
    QSizePolicy,
)

from src.styles.sidebar_menu_style import SIDEBAR_MENU_STYLE
from src.themes.color import (
    MENU_BG_ACTIVE,
    MENU_BG_HOVER,
    MENU_TEXT,
    MENU_TEXT_ACTIVE,
    MENU_TEXT_HOVER,
)
from src.themes.font import (
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
)

ACTIVE_BAR_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "icons" / "active-bar.svg"
)


class MenuButton(QPushButton):

    # ----- Settings -----
    ICON_SIZE = 20
    ACTIVE_BAR_HEIGHT = 20
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

        # ----- Active Bar -----
        self.active_bar_label = QLabel()
        self.active_bar_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.set_active_bar()
        self.active_bar_label.hide()

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

        layout.addWidget(self.active_bar_label)

        # ----- Default State -----
        self.set_icon_color(MENU_TEXT)

        self.set_text_style(
            MENU_TEXT,
            FONT_WEIGHT_MEDIUM,
        )

        # ----- Hover Animation -----
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(self.DURATION)

        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.animation.valueChanged.connect(self.update_background)

    # ----- Icon Color -----
    def set_icon_color(self, color):
        renderer = QSvgRenderer(str(self.icon_path))

        if not renderer.isValid():
            return

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

    # ----- Active Bar -----
    def set_active_bar(self):
        renderer = QSvgRenderer(str(ACTIVE_BAR_PATH))

        if not renderer.isValid():
            return

        svg_size = renderer.defaultSize()

        if svg_size.height() <= 0:
            return

        width = round(self.ACTIVE_BAR_HEIGHT * svg_size.width() / svg_size.height())

        pixmap = QPixmap(
            width,
            self.ACTIVE_BAR_HEIGHT,
        )
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)

        renderer.render(
            painter,
            QRectF(
                0,
                0,
                width,
                self.ACTIVE_BAR_HEIGHT,
            ),
        )

        painter.end()

        self.active_bar_label.setPixmap(pixmap)

    # ----- Text Style -----
    def set_text_style(self, color, weight):
        self.text_label.setStyleSheet(f"""
            color: {color};
            font-weight: {weight};
            """)

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
            self.active_bar_label.show()

            self.set_icon_color(MENU_TEXT_ACTIVE)

            self.set_text_style(
                MENU_TEXT_ACTIVE,
                FONT_WEIGHT_SEMIBOLD,
            )

            self.animate_background(MENU_BG_ACTIVE)

        else:
            self.active_bar_label.hide()

            self.set_icon_color(MENU_TEXT)

            self.set_text_style(
                MENU_TEXT,
                FONT_WEIGHT_MEDIUM,
            )

            self.animate_background("transparent")

    # ----- Hover Enter -----
    def enterEvent(self, event):
        if not self.active:
            self.set_icon_color(MENU_TEXT_HOVER)

            self.set_text_style(
                MENU_TEXT_HOVER,
                FONT_WEIGHT_SEMIBOLD,
            )

            self.animate_background(MENU_BG_HOVER)

        super().enterEvent(event)

    # ----- Hover Leave -----
    def leaveEvent(self, event):
        if not self.active:
            self.set_icon_color(MENU_TEXT)

            self.set_text_style(
                MENU_TEXT,
                FONT_WEIGHT_MEDIUM,
            )

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
