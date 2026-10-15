from PySide6.QtCore import Qt
from PySide6.QtGui import QContextMenuEvent, QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy


class TextArea(QPlainTextEdit):
    # ----- Initialization -----
    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        read_only: bool = False,
        min_height: int = 64,
        max_height: int | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("textArea")
        self.setPlainText(str(text or ""))
        self.setPlaceholderText(placeholder)

        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTabChangesFocus(True)

        self.setMinimumHeight(min_height)

        if max_height is not None:
            self.setMaximumHeight(max_height)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.setStyleSheet("""
            QPlainTextEdit#textArea {
                background-color: #FFFFFF;
                color: #0F172A;
                border: 1px solid #DCE3EE;
                border-radius: 8px;
                padding: 8px;
            }

            QPlainTextEdit#textArea:focus {
                border-color: #2563EB;
            }

            QPlainTextEdit#textArea:read-only {
                background-color: #F8FAFC;
                color: #475569;
            }
        """)

        self.set_read_only(read_only)

    # ----- Read Only -----
    def set_read_only(self, read_only: bool = True):
        read_only = bool(read_only)
        self.setReadOnly(read_only)

        if read_only:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        else:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ----- Disable Context Menu -----
    def contextMenuEvent(self, event: QContextMenuEvent):
        if self.isReadOnly():
            event.accept()
            return

        super().contextMenuEvent(event)

    # ----- Disable Keyboard Interaction in Read Only -----
    def keyPressEvent(self, event: QKeyEvent):
        if self.isReadOnly():
            event.accept()
            return

        super().keyPressEvent(event)
