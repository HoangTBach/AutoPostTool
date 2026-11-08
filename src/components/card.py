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
<<<<<<< Updated upstream
=======
    QFrame,
>>>>>>> Stashed changes
    QVBoxLayout,
    QWidget,
)

<<<<<<< Updated upstream
from src.styles.card_style import CARD_STYLE, STAT_COLORS
=======
from src.components.smooth_scroll_area import SmoothScrollArea
from src.styles.card_style import (
    CARD_BG,
    CARD_BORDER,
    CARD_STYLE,
    SCROLLABLE_CARD_STYLE,
    SECTION_CARD_STYLE,
    STAT_COLORS,
)
>>>>>>> Stashed changes
from src.themes.color import COLORS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING as SPACE

TRANSPARENT = COLORS["transparent"]


class Card(QWidget):
<<<<<<< Updated upstream

    def __init__(self):
=======

    # ----- Settings -----
    OVERLAY_COLOR = "rgba(15, 23, 42, 40)"

    BLOCKED_EVENTS = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.MouseMove,
        # Let ignored wheel events bubble up to the enclosing SmoothScrollArea.
        # Disabled cards must block clicks, not scrolling of the entire page.
        QEvent.Type.ContextMenu,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.Shortcut,
        QEvent.Type.ShortcutOverride,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.DragLeave,
        QEvent.Type.Drop,
        QEvent.Type.InputMethod,
    }

    def __init__(self, disabled: bool = False):
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
        self.body_layout.addWidget(
            self.table,
            1,
=======
        self.body_layout.addWidget(self.table, 1)


class SectionCard(Card):
    """Card with a reusable heading, optional divider and optional smooth scrolling."""

    DEFAULT_HEADER_MARGIN = (20, 16, 20, 14)
    DEFAULT_BODY_MARGIN = (20, 20, 20, 20)

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        header_border: bool = True,
        scrollable: bool = False,
        trailing_widget: QWidget | None = None,
        header_margin: tuple[int, int, int, int] = DEFAULT_HEADER_MARGIN,
        body_margin: tuple[int, int, int, int] = DEFAULT_BODY_MARGIN,
        header_spacing: int = 2,
        body_spacing: int = 0,
        header_height: int | None = None,
        title_height: int | None = None,
        subtitle_height: int | None = None,
        title_object_name: str = "sectionCardTitle",
        description_object_name: str = "sectionCardDescription",
        disabled: bool = False,
    ):
        super().__init__(disabled=disabled)
        self.setStyleSheet(CARD_STYLE + SECTION_CARD_STYLE + SCROLLABLE_CARD_STYLE)

        # ----- Card Header -----
        self.header = QWidget(self)
        self.header.setObjectName("sectionCardHeader")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(*header_margin)
        self.header_layout.setSpacing(8)
        if header_height is not None:
            self.header.setFixedHeight(header_height)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(header_spacing)

        self.title_label = QLabel(title, self.header)
        self.title_label.setObjectName(title_object_name)
        if title_height is not None:
            self.title_label.setFixedHeight(title_height)
        heading.addWidget(self.title_label)

        self.description_label = QLabel(description, self.header)
        self.description_label.setObjectName(description_object_name)
        self.description_label.setWordWrap(True)
        if subtitle_height is not None:
            self.description_label.setFixedHeight(subtitle_height)
        self.description_label.setVisible(bool(description))
        heading.addWidget(self.description_label)

        self.header_layout.addLayout(heading, 1)
        if trailing_widget is not None:
            self.header_layout.addWidget(
                trailing_widget, 0, Qt.AlignmentFlag.AlignVCenter
            )

        # ----- Header Divider -----
        self.header_divider = QFrame(self)
        self.header_divider.setObjectName("sectionCardHeaderDivider")
        self.header_divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.header_divider.setFixedHeight(1)
        self.header_divider.setVisible(header_border)

        # ----- Card Body -----
        self.body = QWidget(self)
        self.body.setObjectName("sectionCardBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(*body_margin)
        self.body_layout.setSpacing(body_spacing)
        self.scroll_area = None

        if scrollable:
            self.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.scroll_area = SmoothScrollArea()
            self.scroll_area.setObjectName("sectionCardScrollArea")
            self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self.scroll_area.setWidget(self.body)

        # ----- Card Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        if header_border:
            layout.addWidget(self.header_divider)
        layout.addWidget(
            self.scroll_area if self.scroll_area is not None else self.body, 1
        )
        self.setMinimumWidth(0)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body_layout.addWidget(widget, stretch)


class ScrollableCard(SectionCard):
    """SectionCard with a fixed header and SmoothScrollArea body."""

    DEFAULT_HEADER_MARGIN = (24, 24, 24, 0)
    DEFAULT_BODY_MARGIN = (24, 20, 24, 24)

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        header_border: bool = False,
        trailing_widget: QWidget | None = None,
        header_margin: tuple[int, int, int, int] = DEFAULT_HEADER_MARGIN,
        body_margin: tuple[int, int, int, int] = DEFAULT_BODY_MARGIN,
        header_spacing: int = 4,
        body_spacing: int = 0,
        subtitle_height: int | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            title,
            description,
            header_border=header_border,
            scrollable=True,
            trailing_widget=trailing_widget,
            header_margin=header_margin,
            body_margin=body_margin,
            header_spacing=header_spacing,
            body_spacing=body_spacing,
            title_height=23,
            subtitle_height=subtitle_height,
            title_object_name="scrollableCardTitle",
            description_object_name="scrollableCardDescription",
            disabled=disabled,
>>>>>>> Stashed changes
        )
