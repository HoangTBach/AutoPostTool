from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.styles.page_header_style import PAGE_HEADER_STYLE
from src.themes.spacing import SPACING as SPACE


class PageHeader(QWidget):

    # ----- Setting -----
    SPACING = SPACE[4]

    def __init__(self, title: str, subtitle: str):
        super().__init__()

        self.setStyleSheet(PAGE_HEADER_STYLE)

        # ----- Title -----
        title_label = QLabel(title)
        title_label.setObjectName("pageHeaderTitle")

        # ----- Subtitle -----
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageHeaderSubtitle")

        # ----- Divider -----
        divider = QFrame()
        divider.setObjectName("pageHeaderDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        # ----- Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        layout.addSpacing(SPACE[12])
        layout.addWidget(divider)
