from PySide6.QtCore import (
    QEasingCurve,
    QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
)
from PySide6.QtWidgets import (
    QAbstractButton,
)

from src.themes.color import COLORS
from src.themes.spacing import SPACING as SPACE


class ToggleSwitch(QAbstractButton):

    # ----- Settings -----
    WIDTH = 32
    HEIGHT = 18
    MARGIN = SPACE[2]
    DURATION = 160

    OFF_COLOR = COLORS["slate"][300]
    ON_COLOR = COLORS["blue"][600]
    KNOB_COLOR = COLORS["neutral"]["white"]

    def __init__(
        self,
        parent=None,
    ):
        super().__init__(parent)

        self.setCheckable(True)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # ----- State -----
        self._progress = 0.0

        # ----- Animation -----
        self.animation = QVariantAnimation(self)

        self.animation.setDuration(self.DURATION)

        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.animation.valueChanged.connect(self.update_progress)

        # ----- Events -----
        self.toggled.connect(self.animate_toggle)

    # ----- Size -----
    def sizeHint(self):
        return QSize(self.WIDTH, self.HEIGHT)

    # ----- Toggle -----
    def animate_toggle(self, checked: bool):
        self.animation.stop()

        self.animation.setStartValue(self._progress)

        self.animation.setEndValue(1.0 if checked else 0.0)

        self.animation.start()

    # ----- Progress -----
    def update_progress(self, value):
        self._progress = float(value)

        self.update()

    # ----- Paint -----
    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)

        # ----- Background -----
        off_color = QColor(self.OFF_COLOR)

        on_color = QColor(self.ON_COLOR)

        background = self.mix_color(off_color, on_color, self._progress)

        painter.setBrush(background)

        painter.drawRoundedRect(self.rect(), self.HEIGHT / 2, self.HEIGHT / 2)

        # ----- Knob -----
        knob_size = self.HEIGHT - self.MARGIN * 2

        start_x = self.MARGIN

        end_x = self.WIDTH - knob_size - self.MARGIN

        knob_x = start_x + (end_x - start_x) * self._progress

        painter.setBrush(QColor(self.KNOB_COLOR))

        painter.drawEllipse(int(knob_x), self.MARGIN, knob_size, knob_size)

        painter.end()

    # ----- Mix Color -----
    def mix_color(
        self,
        start: QColor,
        end: QColor,
        progress: float,
    ):
        red = start.red() + (end.red() - start.red()) * progress

        green = start.green() + (end.green() - start.green()) * progress

        blue = start.blue() + (end.blue() - start.blue()) * progress

        return QColor(
            int(red),
            int(green),
            int(blue),
        )
