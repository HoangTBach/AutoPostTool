from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import (
    StatCard,
    TableCard,
)
from src.components.page_header import PageHeader
from src.components.table import Table
from src.configs.table import PAGE_TABLE_COLUMNS

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class PageAutoPage(QWidget):

    # ----- Setting -----
    MARGIN = (32, 32, 32, 32)
    SPACING = 24

    ACTION_SPACING = 8
    STAT_SPACING = 12
    CONTENT_SPACING = 20

    def __init__(self):
        super().__init__()

        # ----- Header -----
        header = PageHeader(
            title="Page Auto",
            subtitle="Manage and publish posts across your Pages.",
        )

        # ----- Action Buttons -----
        self.import_button = Button(
            text="Import Excel",
            icon=ICON_DIR / "upload.svg",
            variant="outline",
            color="green",
        )

        self.open_button = Button(
            text="Open Excel",
            icon=ICON_DIR / "folder-open.svg",
            variant="outline",
            color="blue",
        )

        self.run_button = Button(
            text="Run",
            icon=ICON_DIR / "play.svg",
            variant="primary",
            color="blue",
        )

        self.stop_button = Button(
            text="Stop",
            icon=ICON_DIR / "square.svg",
            variant="primary",
            color="red",
        )

        # ----- Default State -----
        self.stop_button.hide()

        # ----- Button Events -----
        self.run_button.clicked.connect(self.start_run)

        self.stop_button.clicked.connect(self.stop_run)

        # ----- Action Layout -----
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        action_layout.setSpacing(self.ACTION_SPACING)

        action_layout.addWidget(self.import_button)

        action_layout.addWidget(self.open_button)

        action_layout.addStretch()

        action_layout.addWidget(self.run_button)

        action_layout.addWidget(self.stop_button)

        # ----- Stat Cards -----
        self.active_pages_card = StatCard(
            title="Active pages",
            value="18 / 20",
            description="2 pages need review",
            icon=ICON_DIR / "file-text.svg",
            color="blue",
        )

        self.published_card = StatCard(
            title="Posts published",
            value="42",
            description="Published today",
            icon=ICON_DIR / "earth.svg",
            color="green",
        )

        self.automation_card = StatCard(
            title="Next automation",
            value="10:30",
            description="Starts in 2 min",
            icon=ICON_DIR / "clock-3.svg",
            color="purple",
        )

        self.failed_card = StatCard(
            title="Failed posts",
            value="1",
            description="Needs attention",
            icon=ICON_DIR / "triangle-alert.svg",
            color="red",
        )

        # ----- Stat Layout -----
        stat_layout = QHBoxLayout()
        stat_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        stat_layout.setSpacing(self.STAT_SPACING)

        stat_layout.addWidget(
            self.active_pages_card,
            1,
        )

        stat_layout.addWidget(
            self.published_card,
            1,
        )

        stat_layout.addWidget(
            self.automation_card,
            1,
        )

        stat_layout.addWidget(
            self.failed_card,
            1,
        )

        # ----- Page List Card -----
        self.table_card = TableCard(title="Page List")

        # ----- Table -----
        self.table = Table(columns=PAGE_TABLE_COLUMNS)

        self.table_card.set_table(self.table)

        # ----- Demo Data -----
        page_rows = [
            {
                "no": 1,
                "page": "Mark Diaz",
                "caption": "Ra mắt tính năng mới! Lên lịch đăng tự động.",
                "image": "https://example.com/launch-01.jpg",
                "comment": "Trải nghiệm ngay!",
                "status": "Done",
            },
            {
                "no": 2,
                "page": "Kamryn Martinez",
                "caption": "Ưu đãi mới dành cho khách hàng trong tuần này.",
                "image": "https://example.com/launch-02.jpg",
                "comment": "Xem chi tiết ngay!",
                "status": "Done",
            },
            {
                "no": 3,
                "page": "Avery Brooks",
                "caption": "Ra mắt chiến dịch mới với nhiều nội dung hấp dẫn.",
                "image": "https://example.com/launch-03.jpg",
                "comment": "Đừng bỏ lỡ!",
                "status": "Error",
            },
            {
                "no": 4,
                "page": "Elena Fisher",
                "caption": "Bài đăng đang được xử lý và chuẩn bị xuất bản.",
                "image": "https://example.com/launch-04.jpg",
                "comment": "Theo dõi để cập nhật.",
                "status": "Running",
            },
            {
                "no": 5,
                "page": "Noah Kim",
                "caption": "Nội dung đã sẵn sàng và đang chờ đến lượt đăng.",
                "image": "https://example.com/launch-05.jpg",
                "comment": "Xem thêm thông tin.",
                "status": "Queued",
            },
            {
                "no": 6,
                "page": "Logan Price",
                "caption": "Khám phá những cập nhật mới nhất của chúng tôi.",
                "image": "https://example.com/launch-06.jpg",
                "comment": "Tìm hiểu ngay!",
                "status": "Queued",
            },
            {
                "no": 7,
                "page": "Ruby Singh",
                "caption": "Một nội dung mới đang được lên lịch tự động.",
                "image": "https://example.com/launch-07.jpg",
                "comment": "Theo dõi ngay!",
                "status": "Queued",
            },
            {
                "no": 8,
                "page": "Caleb Turner",
                "caption": "Bài viết mới dành cho cộng đồng của chúng tôi.",
                "image": "https://example.com/launch-08.jpg",
                "comment": "Tham gia cùng chúng tôi!",
                "status": "Queued",
            },
            {
                "no": 9,
                "page": "Mia Carter",
                "caption": "Cập nhật sản phẩm và những tính năng mới nhất.",
                "image": "https://example.com/launch-09.jpg",
                "comment": "Khám phá ngay!",
                "status": "Queued",
            },
            {
                "no": 10,
                "page": "Ethan Walker",
                "caption": "Nội dung mới đã được chuẩn bị cho chiến dịch hôm nay.",
                "image": "https://example.com/launch-10.jpg",
                "comment": "Đọc thêm ngay!",
                "status": "Done",
            },
            {
                "no": 11,
                "page": "Olivia Bennett",
                "caption": "Chúng tôi vừa cập nhật thêm nhiều tính năng mới.",
                "image": "https://example.com/launch-11.jpg",
                "comment": "Khám phá chi tiết.",
                "status": "Running",
            },
            {
                "no": 12,
                "page": "Lucas Scott",
                "caption": "Bài đăng mới đã được thêm vào lịch tự động.",
                "image": "https://example.com/launch-12.jpg",
                "comment": "Theo dõi bài viết.",
                "status": "Queued",
            },
            {
                "no": 13,
                "page": "Sophia Adams",
                "caption": "Thông tin mới nhất dành cho cộng đồng hôm nay.",
                "image": "https://example.com/launch-13.jpg",
                "comment": "Xem ngay!",
                "status": "Done",
            },
            {
                "no": 14,
                "page": "Jackson Reed",
                "caption": "Chiến dịch mới sẽ bắt đầu trong ít phút nữa.",
                "image": "https://example.com/launch-14.jpg",
                "comment": "Đừng bỏ lỡ.",
                "status": "Running",
            },
            {
                "no": 15,
                "page": "Emma Wilson",
                "caption": "Nội dung đang chờ được xử lý trong hàng đợi.",
                "image": "https://example.com/launch-15.jpg",
                "comment": "Theo dõi trạng thái.",
                "status": "Queued",
            },
            {
                "no": 16,
                "page": "Liam Murphy",
                "caption": "Bài đăng mới dành cho người theo dõi của trang.",
                "image": "https://example.com/launch-16.jpg",
                "comment": "Xem thêm!",
                "status": "Queued",
            },
            {
                "no": 17,
                "page": "Grace Collins",
                "caption": "Một cập nhật quan trọng vừa được lên lịch.",
                "image": "https://example.com/launch-17.jpg",
                "comment": "Đọc ngay!",
                "status": "Error",
            },
            {
                "no": 18,
                "page": "Henry Foster",
                "caption": "Bài viết đang được chuẩn bị để xuất bản tự động.",
                "image": "https://example.com/launch-18.jpg",
                "comment": "Theo dõi thêm.",
                "status": "Running",
            },
            {
                "no": 19,
                "page": "Chloe Evans",
                "caption": "Nội dung mới đã sẵn sàng cho lượt đăng tiếp theo.",
                "image": "https://example.com/launch-19.jpg",
                "comment": "Khám phá ngay!",
                "status": "Queued",
            },
            {
                "no": 20,
                "page": "Daniel Cooper",
                "caption": "Cập nhật cuối ngày với nhiều thông tin mới.",
                "image": "https://example.com/launch-20.jpg",
                "comment": "Xem chi tiết.",
                "status": "Done",
            },
        ]

        self.table.set_data(page_rows)

        # ----- Content -----
        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(self.CONTENT_SPACING)

        content_layout.addLayout(action_layout)

        content_layout.addLayout(stat_layout)

        content_layout.addWidget(
            self.table_card,
            1,
        )

        # ----- Page Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(*self.MARGIN)

        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addWidget(
            content,
            1,
        )

    # ----- Start Run -----
    def start_run(self):
        self.run_button.hide()
        self.stop_button.show()

    # ----- Stop Run -----
    def stop_run(self):
        self.stop_button.hide()
        self.run_button.show()
