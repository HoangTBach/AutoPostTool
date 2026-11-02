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
from PySide6.QtWidgets import QAbstractButton

from src.styles.toggle_switch_style import (
    TOGGLE_COLORS,
    TOGGLE_DURATION,
    TOGGLE_HEIGHT,
    TOGGLE_MARGIN,
    TOGGLE_WIDTH,
)


class ToggleSwitch(QAbstractButton):

    # ----- Settings -----
    WIDTH = TOGGLE_WIDTH
    HEIGHT = TOGGLE_HEIGHT
    MARGIN = TOGGLE_MARGIN
    DURATION = TOGGLE_DURATION

    OFF_COLOR = TOGGLE_COLORS["off"]
    ON_COLOR = TOGGLE_COLORS["on"]
    KNOB_COLOR = TOGGLE_COLORS["knob"]

    DISABLED_COLOR = TOGGLE_COLORS["disabled"]
    DISABLED_KNOB_COLOR = TOGGLE_COLORS["disabled_knob"]

    def __init__(
        self,
        parent=None,
        *,
        disabled: bool = False,
    ):
        super().__init__(parent)

        # ----- Toggle -----
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # ----- State -----
        self._progress = 1.0 if self.isChecked() else 0.0
        self._disabled = False
        self._painting = False

        # ----- Animation -----
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(self.DURATION)
        self.animation.setEasingCurve(
            QEasingCurve.Type.OutCubic,
        )
        self.animation.valueChanged.connect(
            self.update_progress,
        )

        # ----- Events -----
        self.toggled.connect(self.animate_toggle)

        self.set_disabled(disabled)

    # ----- Size -----
    def sizeHint(self):
        return QSize(self.WIDTH, self.HEIGHT)

    # ----- Enable / Disable -----
    def set_disabled(self, disabled: bool = True) -> None:
        disabled = bool(disabled)

        if self._disabled == disabled:
            return

        self._disabled = disabled
        self.setEnabled(not disabled)

        self.setCursor(
            Qt.CursorShape.ArrowCursor
            if disabled
            else Qt.CursorShape.PointingHandCursor
        )

        if disabled:
            self.animation.stop()
            self._progress = 1.0 if self.isChecked() else 0.0

        self.update()

    # ----- Toggle -----
    def animate_toggle(self, checked: bool) -> None:
        end_value = 1.0 if checked else 0.0

        if not self.isEnabled():
            self.animation.stop()
            self._progress = end_value
            self.update()
            return

        self.animation.stop()
        self.animation.setStartValue(self._progress)
        self.animation.setEndValue(end_value)
        self.animation.start()

    # ----- Progress -----
    def update_progress(self, value) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    # ----- Paint -----
    def paintEvent(self, event):
        if self._painting:
            return

        self._painting = True
        painter = QPainter()

        try:
            if not painter.begin(self):
                return

            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing,
                True,
            )
            painter.setPen(Qt.PenStyle.NoPen)

            # ----- Colors -----
            if self.isEnabled():
                off_color = QColor(self.OFF_COLOR)
                on_color = QColor(self.ON_COLOR)
                knob_color = QColor(self.KNOB_COLOR)
            else:
                off_color = QColor(self.DISABLED_COLOR)
                on_color = QColor(self.DISABLED_COLOR)
                knob_color = QColor(self.DISABLED_KNOB_COLOR)

            # ----- Background -----
            background = self.mix_color(
                off_color,
                on_color,
                self._progress,
            )

            painter.setBrush(background)
            painter.drawRoundedRect(
                self.rect(),
                self.HEIGHT / 2,
                self.HEIGHT / 2,
            )

            # ----- Knob -----
            knob_size = self.HEIGHT - self.MARGIN * 2
            start_x = self.MARGIN
            end_x = self.WIDTH - knob_size - self.MARGIN

            knob_x = start_x + (end_x - start_x) * self._progress

            painter.setBrush(knob_color)
            painter.drawEllipse(
                int(knob_x),
                self.MARGIN,
                knob_size,
                knob_size,
            )

        finally:
            if painter.isActive():
                painter.end()

            self._painting = False

    # ----- Mix Color -----
    @staticmethod
    def mix_color(
        start: QColor,
        end: QColor,
        progress: float,
    ) -> QColor:
        progress = max(0.0, min(1.0, progress))

        red = start.red() + (end.red() - start.red()) * progress

        green = start.green() + (end.green() - start.green()) * progress

        blue = start.blue() + (end.blue() - start.blue()) * progress

        return QColor(
            round(red),
            round(green),
            round(blue),
        )
