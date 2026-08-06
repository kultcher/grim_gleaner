"""Application stylesheet."""

APP_STYLESHEET = """
QWidget {
    background: #17191d;
    color: #e8e8e8;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow { background: #111318; }
QListWidget#mainNavigation {
    background: #111318;
    border: 0;
    border-right: 1px solid #2c3038;
    padding: 16px 8px;
    outline: 0;
}
QListWidget#mainNavigation::item {
    border-radius: 6px;
    margin: 3px 0;
    padding: 12px 14px;
    color: #b8bdc7;
}
QListWidget#mainNavigation::item:selected {
    background: #323845;
    color: #ffffff;
}
QLabel#pageTitle { font-size: 19pt; font-weight: 650; color: #ffffff; }
QLabel#placeholderTitle { font-size: 16pt; font-weight: 600; }
QLabel#fieldLabel { color: #c9ced8; font-weight: 600; }
QLabel#pageHint { color: #a7adb8; }
QLabel#weightLegend {
    background: #242831;
    border: 1px solid #343a46;
    border-radius: 6px;
    color: #c8cdd6;
    padding: 7px 10px;
}
QLineEdit#profileName {
    background: #22262d;
    border: 1px solid #3a404c;
    border-radius: 5px;
    padding: 7px 9px;
}
QLineEdit#profileName:focus { border-color: #d4a843; }
QTabWidget#profileTabs::pane {
    border: 1px solid #303540;
    border-radius: 7px;
    background: #181b20;
}
QTabBar::tab {
    background: #20242b;
    color: #aeb4bf;
    border: 1px solid #303540;
    border-bottom: 0;
    padding: 9px 18px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #303642; color: #ffffff; }
QFrame#packageAccordion {
    border: 1px solid #303640;
    border-radius: 7px;
    background: #1b1e24;
}
QPushButton#packageHeader {
    background: #252a32;
    border: 0;
    border-radius: 6px;
    color: #eef0f4;
    font-weight: 600;
    padding: 10px 12px;
    text-align: left;
}
QPushButton#packageHeader:hover { background: #2c323c; }
QWidget#packageBody { background: #1b1e24; }
QToolButton#weightArrow {
    background: #292e37;
    border: 1px solid #3a414d;
    border-radius: 4px;
    min-width: 25px;
    min-height: 25px;
}
QToolButton#weightArrow:hover { background: #39404c; }
QToolButton#weightArrow:disabled { color: #545965; background: #202329; }
QToolButton#weightStar {
    background: transparent;
    border: 0;
    color: #686e79;
    font-size: 16pt;
    min-width: 22px;
    padding: 0;
}
QToolButton#weightStar[filled="true"] { color: #e0b44c; }
QToolButton#weightStar:hover { color: #f1ca6d; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #17191d; width: 11px; }
QScrollBar::handle:vertical { background: #3a404b; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
