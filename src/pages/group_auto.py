from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader
from src.themes.spacing import SPACING as SPACE


class GroupAutoPage(QWidget):

    # ----- Settings -----
    MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
    SPACING = SPACE[24]

    def __init__(self):
        super().__init__()

        # ----- Header -----
        header = PageHeader(
            title="Group Auto",
            subtitle="Publish one post to many groups and manage status in one workflow.",
        )

        # ----- Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(*self.MARGIN)

        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addStretch()
