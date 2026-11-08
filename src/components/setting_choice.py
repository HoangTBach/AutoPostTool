"""Selectable setting tiles and radio rows."""

from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from src.styles.setting_style import (
    SETTING_CHOICE_TILE_STYLE,
    SETTING_RADIO_CHOICE_STYLE,
)

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SettingRadioMark(QWidget):
    # ----- Settings -----
    SIZE = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected = False
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_selected(self, selected: bool):
        self._selected = bool(selected)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._selected:
            painter.setPen(QPen(QColor("#2466F4"), 1))
            painter.setBrush(QColor("#2466F4"))
        else:
            painter.setPen(QPen(QColor("#BFCFE2"), 1))
            painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawEllipse(self.rect().adjusted(5, 5, -5, -5))
        painter.end()


class SettingChoiceTile(QPushButton):
    """Checkable tile with an SVG preview and a radio indicator."""

    def __init__(
        self,
        title: str,
        preview: str | Path,
        *,
        description: str = "",
        tile_height: int = 93,
        preview_height: int = 52,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("settingChoiceTile")
        self.setStyleSheet(SETTING_CHOICE_TILE_STYLE)
        self.setAccessibleName(title)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(tile_height)
        self.setMinimumWidth(112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4 if description else 7)

        preview_label = QLabel()
        preview_label.setObjectName("settingChoicePreview")
        preview_label.setFixedHeight(preview_height)
        preview_label.setScaledContents(True)
        preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        preview_file = Path(preview)
        if preview_file.is_file():
            renderer = QSvgRenderer(str(preview_file))
            if renderer.isValid():
                natural = renderer.defaultSize()
                pixmap = QPixmap(max(1, natural.width()), preview_height)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                preview_label.setPixmap(pixmap)
        layout.addWidget(preview_label)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(4)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName("settingChoiceTitle")
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        texts.addWidget(title_label)
        if description:
            hint = QLabel(description)
            hint.setObjectName("settingChoiceSubtitle")
            hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            texts.addWidget(hint)
        footer.addLayout(texts, 1)
        self.mark = SettingRadioMark(self)
        footer.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(footer)
        self.toggled.connect(self.mark.set_selected)


class SettingRadioChoice(QPushButton):
    """Compact checkable option for language or split orientation."""

    def __init__(self, text: str, *, boxed: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("settingRadioChoice")
        self.setProperty("boxed", "true" if boxed else "false")
        self.setStyleSheet(SETTING_RADIO_CHOICE_STYLE)
        self.setAccessibleName(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(32 if boxed else 20)

        row = QHBoxLayout(self)
        row.setContentsMargins(7 if boxed else 0, 0, 6, 0)
        row.setSpacing(6 if boxed else 12)
        self.mark = SettingRadioMark(self)
        row.addWidget(self.mark)
        self.caption = QLabel(text)
        self.caption.setObjectName("settingRadioText")
        self.caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.caption, 1)
        self.toggled.connect(self._set_selection)

    def _set_selection(self, selected: bool):
        self.mark.set_selected(selected)
        self.caption.setProperty("selected", "true" if selected else "false")
        self.caption.style().unpolish(self.caption)
        self.caption.style().polish(self.caption)


class SettingWorkspacePreview(QWidget):
    def __init__(self, preview: str | Path | None = None, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setMaximumWidth(260)
        self.setFixedHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._svg_renderer = None
        if preview is not None:
            preview_file = Path(preview)
            if preview_file.is_file():
                renderer = QSvgRenderer(str(preview_file), self)
                if renderer.isValid():
                    self._svg_renderer = renderer

    def sizeHint(self) -> QSize:
        return QSize(260, 120)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._svg_renderer is not None:
            # Fit the original 260x120 SVG without stretching either axis.
            original = self._svg_renderer.defaultSize()
            if original.isValid():
                scale = min(
                    self.width() / original.width(),
                    self.height() / original.height(),
                )
                width = original.width() * scale
                height = original.height() * scale
                target = QRectF(
                    (self.width() - width) / 2,
                    (self.height() - height) / 2,
                    width,
                    height,
                )
                self._svg_renderer.render(painter, target)
            painter.end()
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width() / 260.0, self.height() / 120.0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E7EDF7"))
        painter.drawRoundedRect(QRectF(0, 0, 260, 120), 4, 4)
        painter.setBrush(QColor("#50749D"))
        painter.drawRoundedRect(QRectF(0, 0, 33, 120), 3, 3)
        painter.setBrush(QColor("#92A3C0"))
        painter.drawRect(QRectF(33, 0, 227, 10))

        for x, color in ((7, "#EF4444"), (15, "#F59E0B"), (23, "#10B981")):
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(x, 3, 4, 4))

        for x, title, color in ((41, "Page Auto", "#2563EB"), (150, "Group Auto", "#10B981")):
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(QRectF(x, 16, 101, 98), 5, 5)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(x + 38, 43, 24, 24))
            painter.setPen(QColor("#17243C"))
            font = painter.font()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(QRectF(x, 75, 101, 20), Qt.AlignmentFlag.AlignCenter, title)
            painter.setPen(Qt.PenStyle.NoPen)
        painter.end()
