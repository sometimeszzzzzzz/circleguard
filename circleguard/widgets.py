# pylint: disable=no-name-in-module
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit, QSpacerItem, QSizePolicy, QSlider, QSpinBox, QDoubleSpinBox
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp, Qt, QSettings
# pylint: enable=no-name-in-module

spacer = QSpacerItem(100, 0, QSizePolicy.Maximum, QSizePolicy.Minimum)


settings = QSettings("Circleguard", "Circleguard")

THRESHOLD = settings.value("threshold")
API_KEY = settings.value("api_key")
DARK_THEME = settings.value("dark_theme")
CACHING = settings.value("caching")


class IDLineEdit(QLineEdit):
    def __init__(self, parent):
        super(IDLineEdit, self).__init__(parent)
        # r prefix isn't necessary but pylint was annoying
        validator = QRegExpValidator(QRegExp(r"\d*"))
        self.setValidator(validator)


class MapId(QWidget):
    def __init__(self):
        super(MapId, self).__init__()

        label = QLabel(self)
        label.setText("Map Id:")
        label.setToolTip("Beatmap id, not the mapset id!")
        self.field = IDLineEdit(self)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 0, 0, 1, 1)
        layout.addItem(spacer, 0, 1, 1, 1)
        layout.addWidget(self.field, 0, 2, 1, 3)
        self.setLayout(layout)


class CompareTop(QWidget):
    def __init__(self):
        super(CompareTop, self).__init__()
        label = QLabel(self)
        label.setText("Compare Top:")
        label.setToolTip("Compare this many plays from the leaderboard")

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(2)
        slider.setMaximum(100)
        slider.setValue(50)
        slider.valueChanged.connect(self.update_spinbox)
        self.slider = slider

        spinbox = QSpinBox()
        spinbox.setValue(50)
        spinbox.setAlignment(Qt.AlignCenter)
        spinbox.setRange(2, 100)
        spinbox.setSingleStep(1)
        spinbox.valueChanged.connect(self.update_slider)
        self.spinbox = spinbox

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 0, 0, 1, 1)
        layout.addItem(spacer, 0, 1, 1, 1)
        layout.addWidget(slider, 0, 2, 1, 2)
        layout.addWidget(spinbox, 0, 4, 1, 1)
        self.setLayout(layout)

    # keep spinbox and slider in sync
    def update_spinbox(self, value):
        self.spinbox.setValue(value)

    def update_slider(self, value):
        self.slider.setValue(value)


class Threshold(QWidget):
    def __init__(self):
        super(Threshold, self).__init__()
        threshold = settings.value("threshold")

        label = QLabel(self)
        label.setText("Threshold:")
        label.setToolTip("Cutoff for how similar two replays must be to be printed")
        self.label = label

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 30)
        slider.setValue(threshold)
        slider.valueChanged.connect(self.update_spinbox)
        self.slider = slider

        spinbox = QSpinBox()
        spinbox.setValue(threshold)
        spinbox.setAlignment(Qt.AlignCenter)
        spinbox.setRange(0, 30)
        spinbox.setSingleStep(1)
        spinbox.valueChanged.connect(self.update_slider)
        self.spinbox = spinbox

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 0, 0, 1, 1)
        layout.addItem(spacer, 0, 1, 1, 1)
        layout.addWidget(slider, 0, 2, 1, 2)
        layout.addWidget(spinbox, 0, 4, 1, 1)
        self.setLayout(layout)

    # keep spinbox and slider in sync
    def update_spinbox(self, value):
        self.spinbox.setValue(value)

    def update_slider(self, value):
        self.slider.setValue(value)


class AutoThreshold(QWidget):
    def __init__(self):
        super(AutoThreshold, self).__init__()

        label = QLabel(self)
        label.setText("Auto Threshold:")
        label.setToolTip("Stddevs below average threshold to print for"+
                         "\n(typically between TLS and 2.5. The higher, the less results you will get)")
        self.label = label

        slider = QSlider(Qt.Horizontal)
        slider.setRange(10, 30)
        slider.setValue(THRESHOLD)
        slider.valueChanged.connect(self.update_spinbox)
        self.slider = slider

        spinbox = QDoubleSpinBox()
        spinbox.setValue(THRESHOLD)
        spinbox.setAlignment(Qt.AlignCenter)
        spinbox.setRange(1.0, 3.0)
        spinbox.setSingleStep(0.1)
        spinbox.valueChanged.connect(self.update_slider)
        self.spinbox = spinbox

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 0, 0, 1, 1)
        layout.addItem(spacer, 0, 1, 1, 1)
        layout.addWidget(slider, 0, 2, 1, 2)
        layout.addWidget(spinbox, 0, 4, 1, 1)
        self.setLayout(layout)

    # keep spinbox and slider in sync
    def update_spinbox(self, value):
        self.spinbox.setValue(value/10)

    def update_slider(self, value):
        self.slider.setValue(value*10)
