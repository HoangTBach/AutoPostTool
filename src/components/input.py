from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QProxyStyle, QStyle

from src.styles.input_style import INPUT_STYLE


class PasswordStyle(QProxyStyle):

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_LineEdit_PasswordCharacter:
            return ord("•")

        return super().styleHint(hint, option, widget, returnData)


class Input(QLineEdit):

    def __init__(
        self,
        text: str = "",
        editable: bool = False,
        password: bool = False,
    ):
        super().__init__(text)

        # ----- Input -----
        self.setObjectName("input")

        self.password_style = None

        if password:
            self.password_style = PasswordStyle()
            self.setStyle(self.password_style)
            self.setEchoMode(QLineEdit.EchoMode.Password)

        self.setStyleSheet(INPUT_STYLE)
        self.set_editable(editable)

    # ----- Editable -----
    def set_editable(self, editable: bool):
        self.setReadOnly(not editable)
        self.setProperty("editable", editable)

        if editable:
            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False,
            )

            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
            self.setCursor(Qt.CursorShape.IBeamCursor)

        else:
            self.deselect()
            self.setCursorPosition(0)

            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )

            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self.style().unpolish(self)
        self.style().polish(self)
