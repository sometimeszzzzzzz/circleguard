from pathlib import Path
import sys

from PyQt5.QtWidgets import QLayout, QFrame
from PyQt5.QtGui import QPainter

# placed above local imports to avoid circular import errors
ROOT_PATH = Path(__file__).parent.parent.absolute()
def resource_path(path):
    """
    Get the resource path for a given file.

    This location changes if the program is run from an application built with
    pyinstaller.

    Returns
    -------
    string
        The absolute path (as a string) to the given file, after taking into
        account whether we are running in a development setting.
        Return string because this function is almost always used in a ``QIcon``
        context, which does not accept a ``Path``.
    """

    if hasattr(sys, '_MEIPASS'): # being run from a pyinstall'd app
        return str(Path(sys._MEIPASS) / "resources" / Path(path)) # pylint: disable=no-member
    return str(ROOT_PATH / "resources" / Path(path))


# TODO figure out if ``delete_widget`` (and ``clear_layout``) are really
# necessary instead of just using ``widget.deleteLater``
def delete_widget(widget):
    if widget.layout is not None:
        clear_layout(widget.layout)
        widget.layout = None
    widget.deleteLater()


def clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.layout() is not None:
            clear_layout(child.layout())
        if child.widget() is not None:
            if isinstance(child.widget().layout, QLayout):
                clear_layout(child.widget().layout)
            child.widget().deleteLater()


class DebugWidget(QFrame):
    """
    A class intended to be subclassed by widgets when debugging. This draws
    rectangles around all items of the class's layout.
    """

    # methods adapted from https://doc.qt.io/qt-5/qlayout.html#itemAt
    def paintEvent(self, paintEvent):
        painter = QPainter(self)
        self.paintLayout(painter, self.layout)

    def paintLayout(self, painter, item):
        layout = item.layout()
        if layout:
            for i in range(layout.count()):
                self.paintLayout(painter, layout.itemAt(i))
        painter.drawRect(item.geometry())


class AnalysisResult():
    def __init__(self, replays):
        self.replays = replays
