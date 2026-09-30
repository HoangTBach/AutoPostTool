from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader


class UpdatePage(QWidget):

    # ----- Settings -----
    MARGIN = (32, 32, 32, 32)
    SPACING = 24

    def __init__(self):
        super().__init__()

        # ----- Header -----
        header = PageHeader(
            title="Update",
            subtitle="Track the current version, release history, and changes for Auto Post Tool.",
        )

        # ----- Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(*self.MARGIN)

        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addStretch()
