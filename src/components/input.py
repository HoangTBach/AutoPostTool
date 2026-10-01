from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from src.styles.input_style import INPUT_STYLE


class Input(QLineEdit):

    def __init__(
        self,
        text: str = "",
        editable: bool = False,
    ):
        super().__init__(text)

        # ----- Input -----
        self.setObjectName("input")
        self.setStyleSheet(INPUT_STYLE)

        # ----- Editable State -----
        self.set_editable(editable)

    # ----- Set Editable -----
    def set_editable(
        self,
        editable: bool,
    ):
        self.setReadOnly(not editable)

        self.setProperty("editable", editable)

        if editable:
            # ----- Editable -----
            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False,
            )

            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

            self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

            self.setCursor(Qt.CursorShape.IBeamCursor)

        else:
            # ----- Read Only -----
            self.deselect()
            self.setCursorPosition(0)

            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

            self.setCursor(Qt.CursorShape.ArrowCursor)

        # ----- Refresh Style -----
        self.style().unpolish(self)
        self.style().polish(self)
