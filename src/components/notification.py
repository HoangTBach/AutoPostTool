from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QIcon, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.styles.notification_style import (
    NOTIFICATION_GAP,
    NOTIFICATION_PADDING_X,
    NOTIFICATION_PADDING_Y,
    NOTIFICATION_STYLES,
    get_notification_card_style,
)


# ----- Notification Icon -----
class NotificationIcon(QWidget):
    def __init__(self, style: dict, parent=None):
        super().__init__(parent)

        self.surface = style["surface"]
        self.setFixedSize(32, 32)

        icon_path = (
            Path(__file__).resolve().parents[1] / "assets" / "icons" / "bell.svg"
        )
        icon = QIcon(str(icon_path))

        self.icon_pixmap = QPixmap(18, 18)
        self.icon_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self.icon_pixmap)
        icon.paint(
            painter,
            self.icon_pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
        )
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(
            self.icon_pixmap.rect(),
            QColor(style["accent"]),
        )
        painter.end()

    # ----- Paint Icon -----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.surface))
        painter.drawRoundedRect(self.rect(), 8, 8)
        painter.drawPixmap(7, 7, self.icon_pixmap)
        painter.end()


# ----- Notification Card -----
class NotificationCard(QFrame):
    expired = Signal(object)

    def __init__(
        self,
        kind: str,
        title: str,
        message: str,
        parent=None,
    ):
        super().__init__(parent)

        if kind not in NOTIFICATION_STYLES:
            raise ValueError(f"Unsupported notification type: {kind}")

        style = NOTIFICATION_STYLES[kind]

        self.setObjectName("notificationCard")
        self.setMinimumHeight(64)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self.setStyleSheet(get_notification_card_style(kind))

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.icon = NotificationIcon(style, self)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("notificationTitle")
        self.title_label.setWordWrap(True)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("notificationMessage")
        self.message_label.setWordWrap(True)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            NOTIFICATION_PADDING_X,
            NOTIFICATION_PADDING_Y,
            NOTIFICATION_PADDING_X,
            NOTIFICATION_PADDING_Y,
        )
        layout.setSpacing(NOTIFICATION_GAP)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_layout, 1)
        layout.setAlignment(text_layout, Qt.AlignmentFlag.AlignTop)

        # ----- Timer -----
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit_expired)

    # ----- Timer -----
    def start_timer(self, duration_ms: int = 5000):
        self._timer.stop()

        if duration_ms > 0:
            self._timer.start(duration_ms)

    def stop_timer(self):
        self._timer.stop()

    def _emit_expired(self):
        self.expired.emit(self)


# ----- Notification Slot -----
class NotificationSlot(QWidget):
    def __init__(
        self,
        width: int,
        height: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedSize(width, height)


# ----- Notification Manager -----
class NotificationManager(QWidget):
    ENTER_DURATION = 280
    EXIT_DURATION = 220
    SLIDE_DISTANCE = 12

    def __init__(
        self,
        parent: QWidget,
        max_visible: int = 4,
        width: int = 380,
        top_margin: int = 32,
        right_margin: int = 32,
    ):
        super().__init__(parent)

        self._slots: dict[NotificationCard, NotificationSlot] = {}
        self._pending_notifications: list[tuple[str, str, str, int]] = []

        self.max_visible = max(1, max_visible)
        self.top_margin = top_margin
        self.right_margin = right_margin
        self.cards: list[NotificationCard] = []
        self._closing_cards: set[NotificationCard] = set()
        self._animations: dict[NotificationCard, QParallelAnimationGroup] = {}

        self.setFixedWidth(width)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(NOTIFICATION_GAP)
        self.layout_box.setAlignment(Qt.AlignmentFlag.AlignTop)

        if parent is not None:
            parent.installEventFilter(self)

        self.hide()

    # ----- Parent Events -----
    def eventFilter(self, watched, event):
        if watched == self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._position_overlay()

        return super().eventFilter(watched, event)

    # ----- Position -----
    def _position_overlay(self):
        parent = self.parentWidget()

        if parent is None:
            return

        self.layout_box.activate()
        self.adjustSize()

        x = max(
            0,
            parent.width() - self.width() - self.right_margin,
        )
        self.move(x, self.top_margin)

    # ----- Entrance Animation -----
    def _animate_in(self, card: NotificationCard):
        if card not in self.cards or card in self._closing_cards:
            return

        start = QPoint(0, self.SLIDE_DISTANCE)
        end = QPoint(0, 0)

        card.move(start)
        card.opacity_effect.setOpacity(0.0)

        animation = QParallelAnimationGroup(self)

        slide = QPropertyAnimation(card, b"pos", animation)
        slide.setDuration(self.ENTER_DURATION)
        slide.setStartValue(start)
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade = QPropertyAnimation(card.opacity_effect, b"opacity", animation)
        fade.setDuration(self.ENTER_DURATION)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._animations[card] = animation
        animation.finished.connect(
            lambda c=card, a=animation: self._finish_entrance(c, a)
        )
        animation.start()

    def _finish_entrance(
        self,
        card: NotificationCard,
        animation: QParallelAnimationGroup,
    ):
        if self._animations.get(card) is animation:
            self._animations.pop(card, None)

        if card in self.cards:
            card.move(0, 0)
            card.opacity_effect.setOpacity(1.0)

        self._position_overlay()
        animation.deleteLater()

    # ----- Show Notification -----
    def show_notification(
        self,
        kind: str,
        title: str,
        message: str,
        duration_ms: int = 5000,
    ):
        if kind not in NOTIFICATION_STYLES:
            raise ValueError(f"Unsupported notification type: {kind}")

        if self._pending_notifications or len(self._slots) >= self.max_visible:
            self._pending_notifications.append((kind, title, message, duration_ms))
            return None

        return self._create_notification(
            kind,
            title,
            message,
            duration_ms,
        )

    # ----- Pending Notifications -----
    def _show_next_pending(self):
        while self._pending_notifications and len(self._slots) < self.max_visible:
            notification = self._pending_notifications.pop(0)
            self._create_notification(*notification)

    # ----- Create Notification -----
    def _create_notification(
        self,
        kind: str,
        title: str,
        message: str,
        duration_ms: int,
    ):
        width = self.width()

        card = NotificationCard(
            kind=kind,
            title=title,
            message=message,
        )
        card.setFixedWidth(width)
        card.ensurePolished()

        card_layout = card.layout()
        card_layout.activate()

        margins = card_layout.contentsMargins()
        icon_width = card_layout.itemAt(0).sizeHint().width()
        icon_height = card_layout.itemAt(0).sizeHint().height()
        text_layout = card_layout.itemAt(1).layout()

        text_width = max(
            1,
            width
            - margins.left()
            - margins.right()
            - icon_width
            - card_layout.spacing(),
        )

        title_height = card.title_label.heightForWidth(text_width)
        message_height = card.message_label.heightForWidth(text_width)

        if title_height <= 0:
            title_height = card.title_label.sizeHint().height()

        if message_height <= 0:
            message_height = card.message_label.sizeHint().height()

        text_height = title_height + text_layout.spacing() + message_height

        height = max(
            64,
            max(icon_height, text_height) + margins.top() + margins.bottom() + 2,
        )

        card.setFixedSize(width, height)

        slot = NotificationSlot(width, height, self)
        card.setParent(slot)
        card.setGeometry(0, 0, width, height)
        card.expired.connect(self._remove_card)

        self._slots[card] = slot
        self.cards.append(card)
        self.layout_box.addWidget(slot)

        card.start_timer(duration_ms)

        self.layout_box.activate()
        self._position_overlay()

        parent_widget = self.parentWidget()
        if parent_widget is not None:
            self.resize(width, max(1, parent_widget.height()))

        self.show()
        self.raise_()
        slot.show()
        card.show()

        QTimer.singleShot(
            0,
            lambda current=card: self._animate_in(current),
        )

        return card

    # ----- Remove Notification -----
    def _remove_card(self, card: NotificationCard):
        if card not in self.cards:
            return

        self.cards.remove(card)
        self._closing_cards.add(card)
        card.stop_timer()

        previous = self._animations.pop(card, None)
        if previous is not None:
            previous.stop()
            previous.deleteLater()

        start = card.pos()
        end = start - QPoint(0, self.SLIDE_DISTANCE)

        animation = QParallelAnimationGroup(self)

        slide = QPropertyAnimation(card, b"pos", animation)
        slide.setDuration(self.EXIT_DURATION)
        slide.setStartValue(start)
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.Type.InCubic)

        fade = QPropertyAnimation(card.opacity_effect, b"opacity", animation)
        fade.setDuration(self.EXIT_DURATION)
        fade.setStartValue(card.opacity_effect.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)

        self._animations[card] = animation
        animation.finished.connect(
            lambda c=card, a=animation: self._finish_removal(c, a)
        )
        animation.start()

    # ----- Finish Removal -----
    def _finish_removal(
        self,
        card: NotificationCard,
        animation: QParallelAnimationGroup,
    ):
        if self._animations.get(card) is animation:
            self._animations.pop(card, None)

        slot = self._slots.pop(card, None)

        if slot is not None:
            slot.hide()
            self.layout_box.removeWidget(slot)
            slot.deleteLater()

        card.stop_timer()
        self._closing_cards.discard(card)
        animation.deleteLater()

        self.layout_box.activate()
        self._show_next_pending()

        if not self._slots and not self._pending_notifications:
            self.hide()
        else:
            self._position_overlay()

    # ----- Notification Shortcuts -----
    def info(
        self,
        title: str,
        message: str,
        duration_ms: int = 5000,
    ):
        return self.show_notification("info", title, message, duration_ms)

    def success(
        self,
        title: str,
        message: str,
        duration_ms: int = 5000,
    ):
        return self.show_notification("success", title, message, duration_ms)

    def error(
        self,
        title: str,
        message: str,
        duration_ms: int = 5000,
    ):
        return self.show_notification("error", title, message, duration_ms)

    def warning(
        self,
        title: str,
        message: str,
        duration_ms: int = 5000,
    ):
        return self.show_notification("warning", title, message, duration_ms)
