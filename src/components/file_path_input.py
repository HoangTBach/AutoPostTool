from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGridLayout, QToolButton, QWidget


from src.components.input import Input, InputMode
from src.styles.file_path_input_style import (
    FILE_PATH_INPUT_STYLE,
    FILE_PATH_INPUT_ICON_SIZE,
    FILE_PATH_INPUT_ICON_COLOR,
)


def _find_folder_open_icon() -> Path | None:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        candidates = (
            parent / "assets" / "icons" / "folder-open.svg",
            parent / "src" / "assets" / "icons" / "folder-open.svg",
        )

        for candidate in candidates:
            if candidate.is_file():
                return candidate

    return None


def _render_tinted_svg(
    icon_path: Path,
    size: int,
    color: str,
) -> QPixmap:
    renderer = QSvgRenderer(str(icon_path))

    if not renderer.isValid():
        return QPixmap()

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()

    return pixmap


class FilePathInput(QWidget):
    def __init__(
        self, text: str | None = None, parent=None, *, variant: str | None = None
    ):
        super().__init__(parent)
        self.setObjectName("filePathInput")
        self.setStyleSheet(FILE_PATH_INPUT_STYLE)

        display_text = text if text is not None else str(Path.home() / "Downloads")

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setColumnStretch(0, 1)

        self.path_input = Input(
            text=display_text,
            mode=InputMode.LOCKED,
            variant=variant,
            parent=self,
        )
        self.path_input.setPlaceholderText("Select media folder")
        self.path_input.setMinimumWidth(120)

        button_size = max(28, self.path_input.sizeHint().height())
        self.path_input.setMinimumHeight(button_size)
        self.path_input.setTextMargins(0, 0, button_size + 4, 0)
        layout.setColumnMinimumWidth(1, button_size)
        layout.setColumnStretch(1, 0)
        layout.addWidget(self.path_input, 0, 0, 1, 2)

        self.browse_button = QToolButton(self)
        self.browse_button.setObjectName("filePathInputBrowseButton")

        folder_icon = _find_folder_open_icon()

        if folder_icon is not None:
            tinted_pixmap = _render_tinted_svg(
                icon_path=folder_icon,
                size=FILE_PATH_INPUT_ICON_SIZE,
                color=FILE_PATH_INPUT_ICON_COLOR,
            )

            self.browse_button.setIcon(
                QIcon(tinted_pixmap) if not tinted_pixmap.isNull() else QIcon()
            )
        else:
            self.browse_button.setIcon(QIcon())

        self.browse_button.setIconSize(
            QSize(FILE_PATH_INPUT_ICON_SIZE, FILE_PATH_INPUT_ICON_SIZE)
        )
        self.browse_button.setFixedSize(button_size, button_size)
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.browse_button, 0, 1)
