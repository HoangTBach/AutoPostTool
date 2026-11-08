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
        "mode": "locked",
    },
    {
        "key": "media",
        "title": "Media",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "mode": "locked",
    },
    {
        "key": "comment",
        "title": "Comment",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "mode": "read_only_copy",
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


# ----- Group Auto -----
GROUP_TABLE_COLUMNS = [
    {
        "key": "no",
        "title": "No",
        "width": 50,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignLeft,
    },
    {
        "key": "group",
        "title": "Group",
        "width": 190,
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
        "mode": "locked",
    },
    {
        "key": "image",
        "title": "Image",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "mode": "locked",
    },
    {
        "key": "comment",
        "title": "Comment",
        "resize": "stretch",
        "stretch": 2,
        "align": Qt.AlignmentFlag.AlignLeft,
        "type": "input",
        "mode": "read_only_copy",
    },
    {
        "key": "status",
        "title": "Status",
        "width": 90,
        "resize": "fixed",
        "align": Qt.AlignmentFlag.AlignRight,
        "type": "status",
    },
]


# ----- News Auto -----
NEWS_TABLE_COLUMNS = []
