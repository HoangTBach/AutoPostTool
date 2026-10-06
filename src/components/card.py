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
    QVBoxLayout,
    QWidget,
)

from src.styles.card_style import CARD_STYLE, STAT_COLORS
from src.themes.color import COLORS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING as SPACE

TRANSPARENT = COLORS["transparent"]


class Card(QWidget):

    def __init__(self):
        super().__init__()

        # ----- Card -----
        self.setObjectName("card")

        # ----- Styled Background -----
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        self.setStyleSheet(CARD_STYLE)


class StatCard(Card):

    # ----- Settings -----
    MARGIN = (SPACE[16], SPACE[16], SPACE[16], SPACE[16])
    SPACING = SPACE[12]

    ICON_SIZE = 20
    ICON_BOX_SIZE = 40
    TEXT_SPACING = SPACE["legacy"][1]

    def __init__(
        self,
        title: str,
        value: str,
        description: str,
        icon: Path,
        color: str = "blue",
    ):
        super().__init__()

        stat_color = STAT_COLORS[color]

        # ----- Icon -----
        self.icon_box = QLabel()

        self.icon_box.setFixedSize(
            self.ICON_BOX_SIZE,
            self.ICON_BOX_SIZE,
        )

        self.icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_box.setStyleSheet(f"""
            background-color: {stat_color["bg"]};
            border-radius: {RADIUS["icon"]}px;
            """)

        self.set_svg_icon(
            self.icon_box,
            icon,
            stat_color["base"],
        )

        # ----- Title -----
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statTitle")

        # ----- Value -----
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")

        # ----- Description -----
        self.description_label = QLabel(description)
        self.description_label.setObjectName("statDescription")

        # ----- Text Layout -----
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        text_layout.setSpacing(self.TEXT_SPACING)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        text_layout.addWidget(self.description_label)

        # ----- Card Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(
            self.icon_box,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addLayout(text_layout)

        layout.addStretch()

    # ----- SVG Icon -----
    def set_svg_icon(
        self,
        label: QLabel,
        icon: Path,
        color: str,
    ):
        renderer = QSvgRenderer(str(icon))

        if not renderer.isValid():
            return

        pixmap = QPixmap(
            self.ICON_SIZE,
            self.ICON_SIZE,
        )

        pixmap.fill(QColor(TRANSPARENT))

        painter = QPainter(pixmap)

        renderer.render(
            painter,
            QRectF(
                0,
                0,
                self.ICON_SIZE,
                self.ICON_SIZE,
            ),
        )

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)

        painter.fillRect(
            pixmap.rect(),
            QColor(color),
        )

        painter.end()

        label.setPixmap(pixmap)


class TableCard(Card):

    # ----- Settings -----
    HEADER_MARGIN = (
        SPACE[24],
        SPACE[12],
        SPACE[24],
        SPACE["legacy"][10],
    )
    BODY_MARGIN = (0, 0, 0, 0)
    SPACING = SPACE[0]

    def __init__(
        self,
        title: str,
    ):
        super().__init__()

        self.table = None

        # ----- Title -----
        self.title_label = QLabel(title)
        self.title_label.setObjectName("tableCardTitle")

        # ----- Header -----
        self.header = QWidget()
        self.header.setObjectName("tableCardHeader")

        header_layout = QHBoxLayout(self.header)

        header_layout.setContentsMargins(*self.HEADER_MARGIN)

        header_layout.setSpacing(0)

        header_layout.addWidget(self.title_label)

        # ----- Body -----
        self.body = QWidget()
        self.body.setObjectName("tableCardBody")

        self.body_layout = QVBoxLayout(self.body)

        self.body_layout.setContentsMargins(*self.BODY_MARGIN)

        self.body_layout.setSpacing(0)

        # ----- Card Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(self.SPACING)

        layout.addWidget(self.header)

        layout.addWidget(
            self.body,
            1,
        )

    # ----- Set Table -----
    def set_table(
        self,
        table: QWidget,
    ):
        if self.table is not None:
            self.body_layout.removeWidget(self.table)

            self.table.setParent(None)

        self.table = table

        self.body_layout.addWidget(
            self.table,
            1,
        )
