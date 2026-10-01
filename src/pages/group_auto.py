from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader


class GroupAutoPage(QWidget):

    # ----- Settings -----
    MARGIN = (32, 32, 32, 32)
    SPACING = 24

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
