from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QScrollArea

from src.styles.smooth_scroll_area_style import SMOOTH_SCROLLBAR_STYLE


class SmoothScrollArea(QScrollArea):

    # ----- Settings -----
    DURATION = 180
    SCROLL_STEP = 120

    def __init__(self):
        super().__init__()

        # ----- Scrollbar Style -----
        self.verticalScrollBar().setStyleSheet(SMOOTH_SCROLLBAR_STYLE)
        self.horizontalScrollBar().setStyleSheet(SMOOTH_SCROLLBAR_STYLE)

        self.animation = QPropertyAnimation(
            self.verticalScrollBar(),
            b"value",
            self,
        )

        self.animation.setDuration(self.DURATION)

        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ----- Smooth Wheel Scroll -----
    def wheelEvent(self, event):
        scrollbar = self.verticalScrollBar()

        delta = event.angleDelta().y()

        if delta == 0:
            super().wheelEvent(event)
            return

        # A nested scroll area with no overflow should not capture the wheel.
        # Qt can forward ignored wheel events to a scrolling parent.
        if scrollbar.maximum() <= scrollbar.minimum():
            event.ignore()
            return

        # ----- Current Target -----
        if self.animation.state() == QPropertyAnimation.State.Running:
            start_value = self.animation.endValue()
        else:
            start_value = scrollbar.value()

        steps = delta / 120

        target = int(start_value - steps * self.SCROLL_STEP)

        target = max(
            scrollbar.minimum(),
            min(
                target,
                scrollbar.maximum(),
            ),
        )

        # At either end of the scroll range, let an enclosing scroll area
        # handle further wheel movement instead of swallowing the event.
        if target == int(start_value):
            event.ignore()
            return

        # ----- Animation -----
        self.animation.stop()

        self.animation.setStartValue(scrollbar.value())

        self.animation.setEndValue(target)

        self.animation.start()

        event.accept()
