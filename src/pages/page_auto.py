from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader


class PageAutoPage(QWidget):

    MARGIN = (32, 32, 32, 32)
    SPACING = 24

    def __init__(self):
        super().__init__()

        # ----- Header -----
        header = PageHeader(
            title="Page Auto",
            subtitle="Manage post content",
        )

        # ----- Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addStretch()
