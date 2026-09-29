from PySide6.QtCore import Qt

# ----- Page Auto -----
PAGE_TABLE_COLUMNS = [
    {
        "key": "no",
        "title": "No",
        "width": 50,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignLeft,
    },
    {
        "key": "page",
        "title": "Page",
        "width": 170,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignLeft,
    },
    {
        "key": "caption",
        "title": "Caption",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "editable": False,
    },
    {
        "key": "image",
        "title": "Image",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "editable": False,
    },
    {
        "key": "comment",
        "title": "Comment",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "editable": False,
    },
    {
        "key": "status",
        "title": "Status",
        "width": 70,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignRight,
        "type": "status",
    },
]


# ----- Group Auto -----
GROUP_TABLE_COLUMNS = [
    {
        "key": "no",
        "title": "No",
        "width": 36,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignLeft,
    },
    {
        "key": "caption",
        "title": "Caption",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "box",
    },
    {
        "key": "image",
        "title": "Image / Link",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "box",
    },
    {
        "key": "comment",
        "title": "Comment",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "box",
    },
    {
        "source": "targets",
        "field": "name",
        "title": "Group targets",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "list",
    },
    {
        "source": "targets",
        "field": "status",
        "title": "Status",
        "width": 80,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignRight,
        "type": "status_list",
    },
]


# ----- News Auto -----
NEWS_TABLE_COLUMNS = [
    {
        "key": "no",
        "title": "No",
        "width": 36,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignLeft,
    },
    {
        "key": "caption",
        "title": "Caption",
        "resize": "stretch",
        "stretch": 3,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "box",
    },
    {
        "key": "image",
        "title": "Image / Link",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "box",
    },
    {
        "key": "status",
        "title": "Status",
        "width": 80,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignRight,
        "type": "status",
    },
]
