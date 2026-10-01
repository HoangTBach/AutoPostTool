from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.components.input import Input
from src.styles.table_style import TABLE_STYLE


class ElideLabel(QLabel):

    def __init__(
        self,
        text: str = "",
    ):
        super().__init__(text)

        self.full_text = text

        # ----- Allow Text Elide -----
        self.setMinimumWidth(0)

        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

    # ----- Elide Text -----
    def resizeEvent(self, event):
        available_width = self.contentsRect().width()

        text = self.fontMetrics().elidedText(
            self.full_text,
            Qt.TextElideMode.ElideRight,
            available_width,
        )

        super().setText(text)
        super().resizeEvent(event)


class SmoothScrollArea(QScrollArea):

    # ----- Settings -----
    DURATION = 180
    SCROLL_STEP = 120

    def __init__(self):
        super().__init__()

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

        # ----- Animation -----
        self.animation.stop()

        self.animation.setStartValue(scrollbar.value())

        self.animation.setEndValue(target)

        self.animation.start()

        event.accept()


class Table(QWidget):

    # ----- Settings -----
    HEADER_MARGIN = (24, 8, 24, 8)
    ROW_MARGIN = (24, 0, 24, 0)

    COLUMN_SPACING = 12
    LIST_SPACING = 4

    DURATION = 180
    SCROLL_STEP = 120

    ROW_HEIGHT = 52
    LIST_ITEM_HEIGHT = 22
    LIST_VERTICAL_PADDING = 16

    def __init__(
        self,
        columns: list[dict],
    ):
        super().__init__()

        self.columns = columns

        # ----- Table -----
        self.setObjectName("table")
        self.setStyleSheet(TABLE_STYLE)

        # ----- Header -----
        self.header = QWidget()
        self.header.setObjectName("tableHeader")
        self.header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.header_layout = QGridLayout(self.header)

        self.header_layout.setContentsMargins(*self.HEADER_MARGIN)

        self.header_layout.setHorizontalSpacing(self.COLUMN_SPACING)

        self.header_layout.setVerticalSpacing(0)

        self.setup_grid_columns(self.header_layout)

        self.setup_header()

        # ----- Body -----
        self.body = QWidget()
        self.body.setObjectName("tableBody")

        self.body_layout = QVBoxLayout(self.body)

        self.body_layout.setContentsMargins(0, 0, 0, 0)

        self.body_layout.setSpacing(0)

        self.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

        # ----- Scroll Area -----
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setObjectName("tableScrollArea")

        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_area.setWidget(self.body)

        # ----- Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        layout.addWidget(self.header)

        layout.addWidget(self.scroll_area, 1)

    # ----- Setup Grid Columns -----
    def setup_grid_columns(self, layout: QGridLayout):
        for index, column in enumerate(self.columns):
            resize = column.get("resize", "stretch")

            if resize == "fixed":
                layout.setColumnMinimumWidth(index, column.get("width", 100))

                layout.setColumnStretch(index, 0)

            else:
                layout.setColumnMinimumWidth(index, 0)

                layout.setColumnStretch(index, column.get("stretch", 1))

    # ----- Header -----
    def setup_header(self):
        for index, column in enumerate(self.columns):
            label = QLabel(column["title"])

            label.setObjectName("tableHeaderCell")

            label.setAlignment(self.get_alignment(column))

            self.setup_column_widget(label, column)

            self.header_layout.addWidget(label, 0, index)

    # ----- Set Data -----
    def set_data(
        self,
        rows: list[dict],
    ):
        self.clear_rows()

        for row in rows:
            self.body_layout.addWidget(self.create_row(row))

    # ----- Clear Rows -----
    def clear_rows(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

    # ----- Create Row -----
    def create_row(
        self,
        data: dict,
    ):
        row = QWidget()
        row.setObjectName("tableRow")

        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row.setMinimumHeight(self.get_row_height(data))

        row_layout = QGridLayout(row)

        row_layout.setContentsMargins(*self.ROW_MARGIN)

        row_layout.setHorizontalSpacing(self.COLUMN_SPACING)

        row_layout.setVerticalSpacing(0)

        self.setup_grid_columns(row_layout)

        for index, column in enumerate(self.columns):
            value = self.get_cell_value(data, column)

            cell = self.create_cell(value, column)

            self.setup_column_widget(cell, column)

            row_layout.addWidget(cell, 0, index)

        return row

    # ----- Create Cell -----
    def create_cell(self, value, column: dict):
        cell_type = column.get("type", "text")

        if cell_type == "input":
            return self.create_input(str(value), column)

        if cell_type == "status":
            return self.create_status(str(value), column)

        if cell_type == "list":
            return self.create_list(value, column)

        if cell_type == "status_list":
            return self.create_status_list(value, column)

        return self.create_text(str(value), column)

    # ----- Text -----
    def create_text(self, text: str, column: dict):
        label = ElideLabel(text)

        label.setObjectName("tableText")

        label.setProperty("column", column.get("key", ""))

        label.setAlignment(self.get_alignment(column))

        return label

    # ----- Input -----
    def create_input(self, text: str, column: dict):
        input_field = Input(
            text=text,
            editable=column.get("editable", False),
        )

        return input_field

    # ----- Status -----
    def create_status(self, status: str, column: dict):
        label = QLabel(status)

        label.setObjectName("tableStatus")

        label.setProperty("status", status.lower())

        label.setAlignment(self.get_alignment(column))

        return label

    # ----- List -----
    def create_list(self, values, column: dict):
        if not isinstance(values, list):
            values = [values]

        container = QWidget()
        container.setObjectName("tableList")

        layout = QVBoxLayout(container)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(self.LIST_SPACING)

        for value in values:
            label = ElideLabel(str(value))

            label.setObjectName("tableListItem")

            label.setAlignment(self.get_alignment(column))

            layout.addWidget(label)

        layout.addStretch()

        return container

    # ----- Status List -----
    def create_status_list(self, values, column: dict):
        if not isinstance(values, list):
            values = [values]

        container = QWidget()
        container.setObjectName("tableList")

        layout = QVBoxLayout(container)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(self.LIST_SPACING)

        for value in values:
            status = str(value)

            label = QLabel(status)

            label.setObjectName("tableStatus")

            label.setProperty("status", status.lower())

            label.setAlignment(self.get_alignment(column))

            layout.addWidget(label)

        layout.addStretch()

        return container

    # ----- Get Cell Value -----
    def get_cell_value(
        self,
        row: dict,
        column: dict,
    ):
        source = column.get("source")

        if source:
            values = row.get(source, [])

            field = column.get("field")

            return [item.get(field, "") for item in values]

        return row.get(column.get("key"), "")

    # ----- Row Height -----
    def get_row_height(self, row: dict):
        max_items = 1

        for column in self.columns:
            value = self.get_cell_value(row, column)

            if isinstance(value, list):
                max_items = max(max_items, len(value))

        if max_items <= 1:
            return self.ROW_HEIGHT

        return max(
            self.ROW_HEIGHT,
            (max_items * self.LIST_ITEM_HEIGHT + self.LIST_VERTICAL_PADDING),
        )

    # ----- Column Size -----
    def setup_column_widget(self, widget: QWidget, column: dict):
        resize = column.get("resize", "stretch")

        # ----- Fixed Column -----
        if resize == "fixed":
            widget.setFixedWidth(column.get("width", 100))

            return

        # ----- Stretch Column -----
        widget.setMinimumWidth(0)

        if isinstance(widget, ElideLabel):
            return

        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    # ----- Alignment -----
    def get_alignment(
        self,
        column: dict,
    ):
        return (
            column.get("align", Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignVCenter
        )
