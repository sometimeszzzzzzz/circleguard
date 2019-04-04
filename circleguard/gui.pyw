import sys
from pathlib import Path
from multiprocessing.pool import ThreadPool
from multiprocessing.context import TimeoutError
from queue import Queue, Empty
from functools import partial

from circleguard import *
from circleguard import __version__ as cg_version

# pylint: disable=no-name-in-module
from PyQt5.QtCore import Qt, QRegExp, QTimer, QSettings
from PyQt5.QtWidgets import (QWidget, QTabWidget, QTextEdit, QPushButton, QLabel,
                             QSpinBox, QVBoxLayout, QSlider, QDoubleSpinBox, QLineEdit,
                             QCheckBox, QGridLayout, QApplication)
from PyQt5.QtGui import QPalette, QColor, QRegExpValidator
# pylint: enable=no-name-in-module

ROOT_PATH = Path(__file__).parent
__version__ = "0.1d"
print(f"backend {cg_version}, frontend {__version__}")


def reset_defaults():
    settings.setValue("ran", True)
    settings.setValue("threshold", 18)
    settings.setValue("api_key", "")
    settings.setValue("dark_theme", 0)
    settings.setValue("caching", 0)


settings = QSettings("Circleguard", "Circleguard")
RAN_BEFORE = settings.value("ran")
if not RAN_BEFORE:
    reset_defaults()

THRESHOLD = settings.value("threshold")
API_KEY = settings.value("api_key")
DARK_THEME = settings.value("dark_theme")
CACHING = settings.value("caching")


class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.tabWidget = QTabWidget()
        self.tabWidget.addTab(MainTab(), "Main Tab")
        self.tabWidget.addTab(SettingsWindow(), "Settings Tab")

        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.tabWidget)
        self.setLayout(self.mainLayout)

        self.setWindowTitle(f"Circleguard (Backend v{cg_version} / Frontend v{__version__})")

        # use this if we have an icon for the program
        # self.setWindowIcon(QIcon(os.path.join(ROOT_PATH, "resources", "icon.png")))


class MainTab(QWidget):
    def __init__(self):
        super(MainTab, self).__init__()
        self.q = Queue()

        self.tabWidget = QTabWidget()
        self.map_tab = MapTab()
        self.tabWidget.addTab(self.map_tab, "Check Map")
        self.tabWidget.addTab(UserTab(), "Screen User")
        self.tabWidget.addTab(UserOnMapTab(), "Check User on Map")
        self.tabWidget.addTab(LocalTab(), "Check Local Replays")
        self.tabWidget.addTab(VerifyTab(), "Verify")

        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)

        self.run_button = QPushButton()
        self.run_button.setText("Run")
        self.run_button.clicked.connect(self.run)

        self.mainLayout = QVBoxLayout()
        self.mainLayout.addWidget(self.tabWidget)
        self.mainLayout.addWidget(self.terminal)
        self.mainLayout.addWidget(self.run_button)
        self.setLayout(self.mainLayout)

        self.start_timer()

    def start_timer(self):
        timer = QTimer(self)
        timer.timeout.connect(self.print_results)
        timer.start(250)

    def write(self, text):
        if text != "":
            self.terminal.append(str(text).strip())
        return None

    def reset_scrollbar(self):
        self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())
        return None

    def run(self):
        pool = ThreadPool(processes=1)
        pool.apply_async(self.run_circleguard)

    def run_circleguard(self):
        cg = Circleguard(API_KEY, ROOT_PATH / "db" / "cache.db")
        map_id = int(self.map_tab.map_id_field.text())
        num = self.map_tab.top_slider.value()
        cg_map = cg.map_check(map_id, num=num, thresh=self.map_tab.thresh_value.value())
        self.write(f"Getting replays of map {map_id}")
        for result in cg_map:
            self.q.put(result)
        self.write(f"Finished getting replays of map {map_id}")

    def print_results(self):
        try:
            while(True):
                result = self.q.get(block=False)
                if(result.ischeat):
                    self.write(f"{result.similiarity:0.1f} similarity. {result.replay1.username} vs {result.replay2.username}, {result.later_name} set later")
        except Empty:
            return 1


class IDLineEdit(QLineEdit):
    def __init__(self, parent):
        super(IDLineEdit, self).__init__(parent)
        # r prefix isn't necessary but pylint was annoying
        validator = QRegExpValidator(QRegExp(r"\d*"))
        self.setValidator(validator)


class MapTab(QWidget):
    def __init__(self):
        super(MapTab, self).__init__()

        self.info = QLabel(self)
        self.info.setText("Compare the top n plays of a Map's leaderboard")

        self.map_id_label = QLabel(self)
        self.map_id_label.setText("Map Id:")
        self.map_id_label.setToolTip("Beatmap id, not the mapset id!")

        self.map_id_field = IDLineEdit(self)
        self.thresh_label = QLabel(self)
        self.thresh_label.setText("Threshold:")
        self.thresh_label.setToolTip(
            "Cutoff for how similar two replays must be to be printed")

        self.thresh_slider = QSlider(Qt.Horizontal)
        self.thresh_slider.setRange(0, 30)
        self.thresh_slider.setValue(THRESHOLD)
        self.thresh_slider.valueChanged.connect(self.update_thresh_value)

        self.thresh_value = QSpinBox()
        self.thresh_value.setValue(THRESHOLD)
        self.thresh_value.setAlignment(Qt.AlignCenter)
        self.thresh_value.setRange(0, 30)
        self.thresh_value.setSingleStep(1)
        self.thresh_value.valueChanged.connect(self.update_thresh_slider)

        self.auto_thresh_label = QLabel(self)
        self.auto_thresh_label.setText("Automatic Threshold:")
        self.auto_thresh_label.setToolTip("This will automatically adjust the Threshold")

        self.auto_thresh_slider = QSlider(Qt.Horizontal)
        self.auto_thresh_slider.setRange(10, 30)
        self.auto_thresh_slider.setValue(20)
        self.auto_thresh_slider.valueChanged.connect(self.update_auto_thresh_value)
        self.auto_thresh_slider.setToolTip("tmp")

        self.auto_thresh_value = QDoubleSpinBox()
        self.auto_thresh_value.setValue(2.0)
        self.auto_thresh_value.setAlignment(Qt.AlignCenter)
        self.auto_thresh_value.setRange(1, 3)
        self.auto_thresh_value.setSingleStep(0.1)
        self.auto_thresh_value.valueChanged.connect(self.update_auto_thresh_slider)
        self.auto_thresh_value.setToolTip("tmp")

        self.auto_thresh_box = QCheckBox(self)
        self.auto_thresh_box.setToolTip("tmp")
        self.auto_thresh_box.stateChanged.connect(self.switch_auto_thresh)
        self.auto_thresh_box.setChecked(1)
        self.auto_thresh_box.setChecked(0)

        self.top_label = QLabel(self)
        self.top_label.setText("Compare Top:")
        self.top_label.setToolTip("Compare this many plays from the leaderboard")

        self.top_slider = QSlider(Qt.Horizontal)
        self.top_slider.setMinimum(2)
        self.top_slider.setMaximum(100)
        self.top_slider.setValue(50)
        self.top_slider.valueChanged.connect(self.update_top_value)

        self.top_value = QSpinBox()
        self.top_value.setValue(50)
        self.top_value.setAlignment(Qt.AlignCenter)
        self.top_value.setRange(2, 100)
        self.top_value.setSingleStep(1)
        self.top_value.valueChanged.connect(self.update_top_slider)

        self.grid = QGridLayout()
        self.grid.addWidget(self.info, 1, 0, 1, 1)

        self.grid.addWidget(self.map_id_label, 2, 0, 1, 1)
        self.grid.addWidget(self.map_id_field, 2, 1, 1, 3)

        self.grid.addWidget(self.top_label, 3, 0, 1, 1)
        self.grid.addWidget(self.top_slider, 3, 1, 1, 2)
        self.grid.addWidget(self.top_value, 3, 3, 1, 1)

        self.grid.addWidget(self.thresh_label, 4, 0, 1, 1)
        self.grid.addWidget(self.thresh_slider, 4, 1, 1, 2)
        self.grid.addWidget(self.thresh_value, 4, 3, 1, 1)

        self.grid.addWidget(self.auto_thresh_label, 5, 0, 1, 1)
        self.grid.addWidget(self.auto_thresh_box, 5, 1, 1, 1)
        self.grid.addWidget(self.auto_thresh_slider, 5, 2, 1, 1)
        self.grid.addWidget(self.auto_thresh_value, 5, 3, 1, 1)

        self.setLayout(self.grid)

    # If somebody has a nicer way to solve this mess, sign me up!

    def update_thresh_value(self):
        self.thresh_value.setValue(self.thresh_slider.value())

    def update_thresh_slider(self):
        self.thresh_slider.setValue(self.thresh_value.value())

    def update_auto_thresh_value(self):
        self.auto_thresh_value.setValue(self.auto_thresh_slider.value() / 10)

    def update_auto_thresh_slider(self):
        self.auto_thresh_slider.setValue(self.auto_thresh_value.value() * 10)

    def update_top_value(self):
        self.top_value.setValue(self.top_slider.value())

    def update_top_slider(self):
        self.top_slider.setValue(self.top_value.value())

    def switch_auto_thresh(self, i):
        self.auto_thresh_slider.setEnabled(i)
        self.auto_thresh_value.setEnabled(i)
        self.thresh_label.setEnabled(not i)
        self.thresh_slider.setEnabled(not i)
        self.thresh_value.setEnabled(not i)


class UserTab(QWidget):
    def __init__(self):
        super(UserTab, self).__init__()
        self.info = QLabel(self)
        self.info.setText("This will compare a user's n top plays with the n Top plays of the corresponding Map")
        self.grid = QGridLayout()
        self.grid.addWidget(self.info, 0, 0, 1, 1)
        self.setLayout(self.grid)


class UserOnMapTab(QWidget):
    def __init__(self):
        super(UserOnMapTab, self).__init__()
        self.info = QLabel(self)
        self.info.setText("This will compare a user's score with the n Top plays of a Map")
        self.grid = QGridLayout()
        self.grid.addWidget(self.info, 0, 0, 1, 1)
        self.setLayout(self.grid)


class LocalTab(QWidget):
    def __init__(self):
        super(LocalTab, self).__init__()
        self.info = QLabel(self)
        self.info.setText("This will verify replays")
        self.grid = QGridLayout()
        self.grid.addWidget(self.info, 0, 0, 1, 1)
        self.setLayout(self.grid)


class VerifyTab(QWidget):
    def __init__(self):
        super(VerifyTab, self).__init__()
        self.info = QLabel(self)
        self.info.setText("This will compare a user's score with the n Top plays of a Map")
        self.grid = QGridLayout()
        self.grid.addWidget(self.info, 0, 0, 1, 1)
        self.setLayout(self.grid)


class SettingsWindow(QWidget):
    def __init__(self):
        super(SettingsWindow, self).__init__()
        self.darkmode_label = QLabel(self)
        self.darkmode_label.setText("Dark mode:")
        self.darkmode_label.setToolTip("tmp")

        self.darkmode_box = QCheckBox(self)
        self.darkmode_box.setToolTip("tmp")
        self.darkmode_box.stateChanged.connect(switch_theme)
        self.darkmode_box.setChecked(DARK_THEME)

        self.thresh_label = QLabel(self)
        self.thresh_label.setText("Default Threshold:")
        self.thresh_label.setToolTip("tmp")

        self.thresh_value = QSpinBox()
        self.thresh_value.setValue(THRESHOLD)
        self.thresh_value.setAlignment(Qt.AlignCenter)
        self.thresh_value.setRange(2, 100)
        self.thresh_value.setSingleStep(1)
        self.thresh_value.valueChanged.connect(partial(update_default, "threshold"))
        self.thresh_value.setToolTip("tmp")

        self.apikey_label = QLabel(self)
        self.apikey_label.setText("API Key:")

        self.apikey_field = QLineEdit(self)
        self.apikey_field.setText(API_KEY)
        self.apikey_field.textChanged.connect(partial(update_default, "api_key"))

        self.cache_label = QLabel(self)
        self.cache_label.setText("Caching:")
        self.cache_label.setToolTip("Downloaded replays will be cached locally")

        self.cache_box = QCheckBox(self)
        self.cache_box.stateChanged.connect(partial(update_default, "caching"))
        self.cache_box.setChecked(CACHING)

        self.grid = QGridLayout()
        self.grid.addWidget(self.apikey_label, 0, 0, 1, 1)
        self.grid.addWidget(self.apikey_field, 0, 1, 1, 1)
        self.grid.addWidget(self.thresh_label, 1, 0, 1, 1)
        self.grid.addWidget(self.thresh_value, 1, 1, 1, 1)
        self.grid.addWidget(self.darkmode_label, 2, 0, 1, 1)
        self.grid.addWidget(self.darkmode_box, 2, 1, 1, 1)
        self.grid.addWidget(self.cache_label, 3, 0, 1, 1)
        self.grid.addWidget(self.cache_box, 3, 1, 1, 1)
        self.setLayout(self.grid)


def update_default(name, value):
    settings.setValue(name, value)


def switch_theme(dark):
    update_default("dark_theme", 1 if dark else 0)
    if dark:
        dark_palette = QPalette()

        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(218, 130, 42))
        dark_palette.setColor(QPalette.Inactive, QPalette.Highlight, Qt.lightGray)
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        dark_palette.setColor(QPalette.Disabled, QPalette.Highlight, Qt.darkGray)

        app.setPalette(dark_palette)
        app.setStyleSheet("QToolTip { color: #ffffff; "
                          "background-color: #2a2a2a; "
                          "border: 1px solid white; }")
    else:
        app.setPalette(app.style().standardPalette())
        updated_palette = QPalette()
        # fixes inactive items not being greyed out
        updated_palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        updated_palette.setColor(QPalette.Disabled, QPalette.Highlight, Qt.darkGray)
        updated_palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor(240, 240, 240))
        app.setPalette(updated_palette)
        app.setStyleSheet("QToolTip { color: #000000; "
                          "background-color: #D5D5D5; "
                          "border: 1px solid white; }")


if __name__ == "__main__":
    # create and open window
    app = QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.resize(600, 500)
    window.show()
    app.exec_()
