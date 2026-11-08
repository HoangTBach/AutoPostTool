from pathlib import Path
from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.components.card import ScrollableCard
from src.components.smooth_scroll_area import SmoothScrollArea
from src.components.page_header import PageHeader
from src.configs.setting import APP_VERSION
from src.styles.page_header_style import PAGE_HEADER_STYLE
from src.styles.update_style import (
    UPDATE_COLUMN_GAP,
    UPDATE_CONTENT_GAP,
    UPDATE_LAYOUT_SPACING,
    UPDATE_MARGIN,
    UPDATE_STYLE,
)

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

# ----- Detailed Update Notes: Figma sample data -----
UPDATE_NOTES = (
    (
        "UI IMPROVEMENTS",
        "green",
        "smartphone.svg",
        (
            "Optimized version details for smaller screens to improve "
            "readability and layout.",
        ),
    ),
    (
        "BUG FIXES",
        "red",
        "clock.svg",
        (
            "Fixed time display in the update history so release dates are "
            "shown accurately.",
        ),
    ),
    (
        "PERFORMANCE",
        "blue",
        "refresh-cw.svg",
        (
            "Improved sync after successful posting to keep the queue and "
            "history in a consistent state.",
        ),
    ),
)

# ----- Update History: Figma sample data -----
UPDATE_HISTORY = (
    (
        "v1",
        "v1.0.1",
        "Sep 12, 2026",
        "Fix",
        "blue",
        (
            "Improved sync after successful posting.",
            "Fixed time display in the update history.",
            "Optimized version details for smaller screens.",
        ),
    ),
    (
        "v1",
        "v1.0.0",
        "Aug 26, 2026",
        "Stable",
        "blue",
        (
            "Launched the official Update page.",
            "Added update history with release notes for each version.",
            "Improved version status and install date display.",
        ),
    ),
    (
        "v0",
        "v0.9.8",
        "Aug 02, 2026",
        "Fix",
        "green",
        (
            "Fixed queue status loss after app restart.",
            "Improved data sync after updating to a new version.",
            "Optimized performance when reviewing update history.",
        ),
    ),
    (
        "v0",
        "v0.9.5",
        "Jul 15, 2026",
        "Fix",
        "green",
        (
            "Improved version and update date display.",
            "Fixed inaccurate display in some history items.",
            "Optimized the experience for viewing release details.",
        ),
    ),
)


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return label


def _svg_icon(filename: str, size: int, object_name: str) -> QLabel:
    label = QLabel()
    label.setObjectName(object_name)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_file = ICON_DIR / filename
    if not icon_file.is_file():
        return label
    renderer = QSvgRenderer(str(icon_file))
    if renderer.isValid():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        label.setPixmap(pixmap)
    return label


class UpdatePage(QWidget):
    MARGIN = UPDATE_MARGIN
    SPACING = UPDATE_LAYOUT_SPACING

    def __init__(self):
        super().__init__()
        self.setObjectName("updatePage")
        self.setStyleSheet(UPDATE_STYLE)

        # ----- Header -----
        header = PageHeader(
            title="Updates",
            subtitle=(
                "Track the current version, release history, "
                "and changes for Auto Post Tool."
            ),
        )
        header.setFixedHeight(78)
        header.setStyleSheet(
            PAGE_HEADER_STYLE + "\nQLabel#pageHeaderTitle {font-size: 28px;}"
        )

        # ----- Left: Overview and Detailed Notes -----
        left = QWidget()
        left.setObjectName("updateLeftColumn")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(UPDATE_CONTENT_GAP)
        left_layout.addWidget(self._build_overview(), 0)
        left_layout.addWidget(self._build_detailed_notes(), 1)

        # ----- Right: Update History -----
        history = self._build_history()
        # ----- Content: Two Columns -----
        content = QWidget()
        content.setObjectName("updateContentRow")
        content.setMinimumHeight(734)
        columns = QHBoxLayout(content)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(UPDATE_COLUMN_GAP)
        columns.addWidget(left, 6)
        columns.addWidget(history, 5)

        # ----- Responsive Scroll Area -----
        self.content_scroll = SmoothScrollArea()
        self.content_scroll.setObjectName("updateContentScroll")
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.content_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.content_scroll.setStyleSheet(
            "QScrollArea#updateContentScroll, "
            "QScrollArea#updateContentScroll > QWidget, "
            "QWidget#updateContentRow, QWidget#updateLeftColumn "
            "{ background: transparent; border: none; }"
        )
        self.content_scroll.setWidget(content)

        # ----- Root Layout -----
        root = QVBoxLayout(self)
        root.setContentsMargins(*self.MARGIN)
        root.setSpacing(self.SPACING)
        root.addWidget(header)
        root.addWidget(self.content_scroll, 1)

    # ----- Update Overview -----
    def _build_overview(self) -> QWidget:
        overview = QWidget()
        overview.setObjectName("updateHero")
        overview.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        overview.setFixedHeight(182)

        layout = QHBoxLayout(overview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        feature = QFrame()
        feature.setObjectName("updateHeroFeature")
        feature.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        feature_layout = QVBoxLayout(feature)
        feature_layout.setContentsMargins(28, 28, 28, 26)
        feature_layout.setSpacing(0)

        badge = _label("● Update available", "updateAvailable")
        badge.setFixedHeight(23)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        channel = _label("Stable channel", "updateChannel")
        status = QHBoxLayout()
        status.setContentsMargins(0, 0, 0, 0)
        status.addWidget(badge)
        status.addStretch(1)
        status.addWidget(channel)
        feature_layout.addLayout(status)
        feature_layout.addSpacing(18)
        title = _label("Auto Post Tool", "updateHeroTitle")
        feature_layout.addWidget(title)
        feature_layout.addSpacing(8)
        description = _label(
            "A focused release for multi-group workflows, news "
            "automation and stronger queue reliability.",
            "updateHeroDescription",
            wrap=True,
        )
        feature_layout.addWidget(description)
        feature_layout.addStretch(1)

        version_panel = QFrame()
        version_panel.setObjectName("updateHeroVersion")
        version_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        version_layout = QHBoxLayout(version_panel)
        version_layout.setContentsMargins(28, 28, 28, 20)
        version_layout.setSpacing(8)

        version_info = QVBoxLayout()
        version_info.setContentsMargins(0, 0, 0, 0)
        version_info.setSpacing(5)
        version_info.addWidget(_label("CURRENT VERSION", "updateCurrentLabel"))
        version_info.addWidget(_label(APP_VERSION, "updateCurrentValue"))
        version_info.addWidget(_label("Installed Sep 12, 2026", "updateInstalledDate"))
        version_info.addStretch(1)
        version_layout.addLayout(version_info, 1)

        icon_bg = QLabel()
        icon_bg.setObjectName("updateCurrentIcon")
        icon_bg.setFixedSize(48, 48)
        icon_bg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_inner_layout = QHBoxLayout(icon_bg)
        icon_inner_layout.setContentsMargins(13, 13, 13, 13)
        icon_inner_layout.addWidget(
            _svg_icon("package-check.svg", 22, "updatePackageSvg")
        )
        version_layout.addWidget(icon_bg, 0, Qt.AlignmentFlag.AlignTop)

        layout.addWidget(feature, 37)
        layout.addWidget(version_panel, 23)
        return overview

    # ----- Detailed Update Notes -----
    def _build_detailed_notes(self) -> ScrollableCard:
        card = ScrollableCard(
            title="Detailed update notes",
            header_border=False,
            description=(
                "Review the release details, improvements, and fixes "
                "included in the current version."
            ),
            header_margin=(28, 20, 28, 0),
            body_margin=(28, 20, 28, 20),
            header_spacing=6,
            subtitle_height=20,
        )
        card.setMinimumHeight(536)

        for index, (tag, color, icon, description) in enumerate(UPDATE_NOTES):
            card.add_widget(
                self._build_note_row(
                    tag,
                    color,
                    icon,
                    description,
                    last=(index == len(UPDATE_NOTES) - 1),
                )
            )
        card.body_layout.addStretch(1)
        return card

    @staticmethod
    def _build_note_row(
        tag: str,
        color: str,
        icon: str,
        description: tuple[str, ...],
        *,
        last: bool,
    ) -> QFrame:
        row = QFrame()
        row.setObjectName("updateChangeRowLast" if last else "updateChangeRow")
        # Hug contents: height follows the label after text wraps.
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        icon_bg = QLabel()
        icon_bg.setObjectName(f"updateChangeIcon{color.capitalize()}")
        icon_bg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_bg.setFixedSize(36, 36)
        icon_layout = QHBoxLayout(icon_bg)
        icon_layout.setContentsMargins(9, 9, 9, 9)
        icon_layout.addWidget(_svg_icon(icon, 18, "updateChangeSvg"))
        layout.addWidget(icon_bg, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)
        tag_label = _label(tag, f"updateTag{color.capitalize()}")
        tag_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        info.addWidget(tag_label, 0, Qt.AlignmentFlag.AlignLeft)
        description_label = _label(
            "\n".join(description), "updateChangeDescription", wrap=True
        )
        info.addWidget(description_label)
        layout.addLayout(info, 1)
        return row

    # ----- Update History -----
    @staticmethod
    def _history_fields(item):
        """Normalize one release record before passing it to the item widget."""
        names = ("avatar", "version", "date", "status", "avatar_color", "changes")
        if isinstance(item, Mapping):
            fields = tuple(item.get(name) for name in names)
        elif isinstance(item, (tuple, list)) and len(item) == 6:
            fields = tuple(item)
        elif (
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[1], Mapping)
        ):
            details = {**item[1], "version": item[0]}
            fields = tuple(details.get(name) for name in names)
        else:
            return None

        if any(field is None for field in fields):
            return None
        if not isinstance(fields[5], (tuple, list)):
            return None
        return (*fields[:5], tuple(fields[5]))

    def _build_history(self) -> ScrollableCard:
        # ----- History Items -----
        history_items = []
        seen_versions = set()
        invalid_count = 0
        for item in UPDATE_HISTORY:
            fields = self._history_fields(item)
            if fields is None:
                invalid_count += 1
                continue
            version = str(fields[1]).strip()
            if not version or version in seen_versions:
                continue
            seen_versions.add(version)
            history_items.append(fields)

        count_label = _label(f"{len(history_items)} entries", "updateHistoryCount")
        count_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        card = ScrollableCard(
            title="Update history",
            header_border=False,
            description="Review recent changes and release details for each version.",
            trailing_widget=count_label,
            header_margin=(24, 24, 24, 0),
            body_margin=(24, 20, 24, 24),
            header_spacing=4,
            body_spacing=12,
            subtitle_height=16,
        )
        card.setMinimumHeight(734)

        for fields in history_items:
            card.add_widget(self._build_history_item(*fields))
        if invalid_count:
            card.add_widget(
                _label(
                    f"{invalid_count} update history item(s) have incomplete data.",
                    "updateSectionDescription",
                    wrap=True,
                )
            )
        card.body_layout.addStretch(1)
        return card

    @staticmethod
    def _build_history_item(
        avatar: str,
        version: str,
        date: str,
        status: str,
        avatar_color: str,
        changes: tuple[str, ...],
    ) -> QFrame:
        row = QFrame()
        row.setObjectName("updateHistoryItem")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setFixedHeight(142)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(12)
        avatar_label = _label(
            avatar,
            (
                "updateHistoryAvatarBlue"
                if avatar_color == "blue"
                else "updateHistoryAvatarGreen"
            ),
        )
        avatar_label.setFixedSize(32, 32)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.addWidget(avatar_label)

        version_copy = QVBoxLayout()
        version_copy.setContentsMargins(0, 0, 0, 0)
        version_copy.setSpacing(0)
        version_copy.addWidget(_label(version, "updateHistoryVersion"))
        version_copy.addWidget(_label(date, "updateHistoryDate"))
        heading.addLayout(version_copy, 1)
        badge_name = (
            "updateHistoryBadgeStable"
            if status == "Stable"
            else "updateHistoryBadgeFix"
        )
        badge = _label(status, badge_name)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        heading.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(heading)

        bullets = QVBoxLayout()
        bullets.setContentsMargins(0, 0, 0, 0)
        bullets.setSpacing(6)
        for change in changes:
            bullet_row = QHBoxLayout()
            bullet_row.setContentsMargins(0, 0, 0, 0)
            bullet_row.setSpacing(8)
            dot = _label("•", "updateHistoryBulletDot")
            dot.setFixedWidth(5)
            bullet_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
            entry = _label(change, "updateHistoryBullet", wrap=True)
            bullet_row.addWidget(entry, 1)
            bullets.addLayout(bullet_row)
        layout.addLayout(bullets)
        layout.addStretch(1)
        return row
