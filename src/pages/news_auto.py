from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader
from src.themes.spacing import SPACING as SPACE


class NewsAutoPage(QWidget):

    # ----- Settings -----
    MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
    SPACING = SPACE[24]

    def __init__(self):
        super().__init__()

        # ----- Header -----
        header = PageHeader(
            title="News Auto",
            subtitle="Manage news feeds and publish to Facebook destinations.",
        )

        # ----- Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(*self.MARGIN)

        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addStretch()
