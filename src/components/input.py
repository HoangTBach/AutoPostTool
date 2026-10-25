from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QProxyStyle, QStyle

from src.styles.input_style import INPUT_STYLE


class InputMode(str, Enum):
    NORMAL = "normal"
    READ_ONLY_COPY = "read_only_copy"
    LOCKED = "locked"


class PasswordStyle(QProxyStyle):
    def styleHint(
        self,
        hint,
        option=None,
        widget=None,
        returnData=None,
    ):
        if hint == QStyle.StyleHint.SH_LineEdit_PasswordCharacter:
            return ord("•")

        return super().styleHint(
            hint,
            option,
            widget,
            returnData,
        )


class Input(QLineEdit):
    def __init__(
        self,
        text: str = "",
        editable: bool = True,
        password: bool = False,
        parent=None,
        *,
        mode: InputMode | str | None = None,
    ):
        super().__init__(text, parent)

        self.setObjectName("input")
        self.password_style = None
        self._mode = InputMode.NORMAL

        if password:
            self.password_style = PasswordStyle()
            self.setStyle(self.password_style)
            self.setEchoMode(QLineEdit.EchoMode.Password)

        self.setStyleSheet(INPUT_STYLE)

        if mode is None:
            mode = InputMode.NORMAL if editable else InputMode.LOCKED

        self.set_mode(mode)

    def set_mode(self, mode: InputMode | str) -> None:
        if not isinstance(mode, InputMode):
            mode = InputMode(mode)

        self._mode = mode

        self.setProperty("mode", mode.value)
        self.setProperty(
            "editable",
            mode == InputMode.NORMAL,
        )

        if mode == InputMode.NORMAL:
            self.setEnabled(True)
            self.setReadOnly(False)

            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False,
            )
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
            self.setCursor(Qt.CursorShape.IBeamCursor)

        elif mode == InputMode.READ_ONLY_COPY:
            self.setEnabled(True)
            self.setReadOnly(True)

            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                False,
            )
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
            self.setCursor(Qt.CursorShape.IBeamCursor)

        elif mode == InputMode.LOCKED:
            self.setReadOnly(True)
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
        self.update()

    def set_editable(self, editable: bool) -> None:
        self.set_mode(InputMode.NORMAL if editable else InputMode.LOCKED)

    def get_mode(self) -> InputMode:
        return self._mode
