import os
import sys
from pathlib import Path
from queue import Queue, Empty
from functools import partial
import logging
from logging.handlers import RotatingFileHandler
import threading
from datetime import datetime
import math
import time

# TODO this might cause a performance hit (we only import * for convenience),
# investigate
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from circleguard import (Circleguard, set_options, Loader, NoInfoAvailableException,
                        ReplayMap, ReplayPath, User, Map, Check, MapUser,
                        StealResult, RelaxResult, CorrectionResult, Detect, Mod)
from circleguard import __version__ as cg_version
from circleguard.loadable import Loadable
from circlevis import BeatmapInfo
from slider import Library

from utils import resource_path, delete_widget
from widgets import (ResetSettings, WidgetCombiner, FolderChooser, Separator,
                     LoglevelWidget, ButtonWidget, OptionWidget, SliderBoxSetting,
                     BeatmapTest, LineEditSetting, EntryWidget, RunWidget)

from settings import get_setting, set_setting, overwrite_config, overwrite_with_config_settings, LinkableSetting, SingleLinkableSetting
from .visualizer import CGVisualizer
from .main_tab import MainTab
from wizard import CircleguardWizard
from version import __version__


log = logging.getLogger(__name__)


class DebugWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debug Output")
        self.setWindowIcon(QIcon(resource_path("logo/logo.ico")))
        terminal = QTextEdit(self)
        terminal.setReadOnly(True)
        terminal.ensureCursorVisible()
        self.terminal = terminal
        self.setCentralWidget(self.terminal)
        self.resize(800, 350)

    def write(self, message):
        self.terminal.append(message)

class MainWindow(QFrame):
    def __init__(self, parent):
        super().__init__(parent)

        self.tabs = QTabWidget()
        self.main_tab = MainTab()
        self.results_tab = ResultsTab()
        self.queue_tab = QueueTab()
        self.thresholds_tab = ThresholdsTab(self)
        self.settings_tab = SettingsTab()
        self.tabs.addTab(self.main_tab, "Main")
        self.tabs.addTab(self.results_tab, "Results")
        self.tabs.addTab(self.queue_tab, "Queue")
        self.tabs.addTab(self.thresholds_tab, "Thresholds")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tabs)
        self.layout.setContentsMargins(10, 10, 10, 0)
        self.setLayout(self.layout)


# TODO needs to be updated to work with ReplayChooser instead of FolderChooser
class VisualizeTab(QFrame):
    def __init__(self):
        super().__init__()
        self.result_frame = ResultsTab()
        self.result_frame.results.info_label.hide()
        self.map_id = None
        self.q = Queue()
        self.replays = []
        cache_path = get_setting("cache_dir") + "circleguard.db"
        self.cg = Circleguard(get_setting("api_key"), cache_path)
        self.info = QLabel(self)
        self.info.setText("Visualizes Replays. Has theoretically support for an arbitrary amount of replays.")
        self.label_map_id = QLabel(self)
        self.update_map_id_label()
        self.file_chooser = FolderChooser("Add Replays", folder_mode=False, multiple_files=True,
                                            file_ending="osu! Replayfile (*osr)", display_path=False)
        self.file_chooser.path_signal.connect(self.add_files)
        self.folder_chooser = FolderChooser("Add Folder", display_path=False)
        self.folder_chooser.path_signal.connect(self.add_folder)
        layout = QGridLayout()
        layout.addWidget(self.info)
        layout.addWidget(self.file_chooser)
        layout.addWidget(self.folder_chooser)
        layout.addWidget(self.label_map_id)
        layout.addWidget(self.result_frame)

        self.setLayout(layout)

    def start_timer(self):
        timer = QTimer(self)
        timer.timeout.connect(self.run_timer)
        timer.start(250)

    def run_timer(self):
        self.add_widget()

    def update_map_id_label(self):
        self.label_map_id.setText(f"Current beatmap_id: {self.map_id}")

    def add_files(self, paths):
        thread = threading.Thread(target=self._parse_replays, args=[paths])
        thread.start()
        self.start_timer()

    def add_folder(self, path):
        thread = threading.Thread(target=self._parse_folder, args=[path])
        thread.start()
        self.start_timer()

    def _parse_replays(self, paths):
        for path in paths:
            # guaranteed to end in .osr by our filter
            self._parse_replay(path)

    def _parse_folder(self, path):
        for f in os.listdir(path): # os.walk seems unnecessary
            if f.endswith(".osr"):
                self._parse_replay(os.path.join(path, f))

    def _parse_replay(self, path):
        replay = ReplayPath(path)
        self.cg.load(replay)
        if self.map_id is None or len(self.replays) == 0: # store map_id if nothing stored
            log.info(f"Changing map_id from {self.map_id} to {replay.map_id}")
            self.map_id = replay.map_id
            self.update_map_id_label()
        elif replay.map_id != self.map_id: # ignore replay with diffrent map_ids
            log.error(f"replay {replay} doesn't match with current map_id ({replay.map_id} != {self.map_id})")
            return
        if not any(replay.replay_id == r.data.replay_id for r in self.replays): # check if already stored
            log.info(f"adding new replay {replay} with replay id {replay.replay_id} on map {replay.map_id}")
            self.q.put(replay)
        else:
            log.info(f"skipping replay {replay} with replay id {replay.replay_id} on map {replay.map_id} since it's already saved")

    def add_widget(self):
        try:
            while True:
                replay = self.q.get(block=False)
                widget = EntryWidget(f"{replay.username}'s play with the id {replay.replay_id}", "Delete", replay)
                widget.clicked_signal.connect(self.remove_replay)
                self.replays.append(widget)
                self.result_frame.results.layout.insertWidget(0,widget)
        except Empty:
            pass

    def remove_replay(self, data):
        replay_ids = [replay.data.replay_id for replay in self.replays]
        index = replay_ids.index(data.replay_id)
        self.result_frame.results.layout.removeWidget(self.replays[index])
        self.replays[index].deleteLater()
        self.replays[index] = None
        self.replays.pop(index)


class SettingsTab(QFrame):
    def __init__(self):
        super().__init__()
        self.qscrollarea = QScrollArea(self)
        self.qscrollarea.setWidget(ScrollableSettingsWidget())
        self.qscrollarea.setAlignment(Qt.AlignCenter)
        self.qscrollarea.setWidgetResizable(True)

        self.open_settings = QPushButton("Open Advanced Settings")
        self.open_settings.clicked.connect(self._open_settings)
        self.sync_settings = QPushButton("Sync Settings")
        self.sync_settings.clicked.connect(self._sync_settings)


        self.info = QLabel(self)
        # multiple spaces get shrinked to one space in rich text mode
        # https://groups.google.com/forum/#!topic/qtcontribs/VDOQFUj-eIA
        self.info.setText(f"circleguard v{__version__}&nbsp;&nbsp;|&nbsp;&nbsp;"
                          f"circlecore v{cg_version}&nbsp;&nbsp;|&nbsp;&nbsp;"
                          f"<a href=\"https://github.com/circleguard/circleguard/issues\">Bug Report</a>")
        self.info.setTextFormat(Qt.RichText)
        self.info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.info.setOpenExternalLinks(True)
        self.info.setAlignment(Qt.AlignCenter)
        self.setting_buttons = WidgetCombiner(self.open_settings, self.sync_settings, self)

        layout = QGridLayout()
        layout.addWidget(self.info, 0,0,1,1, alignment=Qt.AlignLeft)
        layout.addWidget(self.setting_buttons, 0,1,1,1, alignment=Qt.AlignRight)
        layout.addWidget(self.qscrollarea, 1,0,1,2)

        self.setLayout(layout)

    def _open_settings(self):
        overwrite_config() # generate file with latest changes
        QDesktopServices.openUrl(QUrl.fromLocalFile(get_setting("config_location") + "/circleguard.cfg"))

    def _sync_settings(self):
        overwrite_with_config_settings()


class ScrollableSettingsWidget(QFrame):
    """
    This class contains all of the actual settings content - SettingsTab just
    has a QScrollArea wrapped around this widget so that it can be scrolled
    down.

    """
    def __init__(self):
        super().__init__()
        self.visualizer = None
        self.wizard = CircleguardWizard()

        self.apikey_widget = LineEditSetting("Api Key", "", "password", "api_key")
        self.darkmode = OptionWidget("Dark mode", "Come join the dark side", "dark_theme")
        self.visualizer_info = OptionWidget("Show Visualizer info", "", "visualizer_info")
        self.visualizer_beatmap = OptionWidget("Render Hitobjects", "Reopen Visualizer for it to apply", "render_beatmap")
        self.cache = OptionWidget("Caching", "Downloaded replays will be cached locally", "caching")

        self.loglevel = LoglevelWidget("")

        self.run_wizard = ButtonWidget("Run Wizard", "Run", "")
        self.run_wizard.button.clicked.connect(self.show_wizard)

        vert_spacer = QSpacerItem(0, 10, QSizePolicy.Maximum, QSizePolicy.Minimum)
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.addItem(vert_spacer)
        self.layout.addWidget(Separator("General"))
        self.layout.addWidget(self.apikey_widget)
        self.layout.addWidget(self.cache)
        self.layout.addItem(vert_spacer)
        self.layout.addWidget(Separator("Appearance"))
        self.layout.addWidget(self.darkmode)
        self.layout.addWidget(self.visualizer_info)
        self.layout.addWidget(self.visualizer_beatmap)
        self.layout.addItem(vert_spacer)
        self.layout.addWidget(Separator("Debug"))
        self.layout.addWidget(self.loglevel)
        self.layout.addWidget(ResetSettings())
        self.layout.addItem(vert_spacer)
        self.layout.addWidget(Separator("Dev"))
        self.layout.addWidget(self.run_wizard)
        self.beatmaptest = BeatmapTest()
        self.beatmaptest.visualize_button.clicked.connect(self.visualize)
        self.layout.addWidget(self.beatmaptest)
        self.setLayout(self.layout)

    def show_wizard(self):
        self.wizard.show()

    def visualize(self):
        if self.visualizer is not None:
            self.visualizer.close()
        beatmap_info = BeatmapInfo(path=self.beatmaptest.file_chooser.path)
        # TODO pass the library we define in MainTab to CGVIsualizer,
        # probably will have to rework some things entirely
        self.visualizer = CGVisualizer(beatmap_info)
        self.visualizer.show()


class ResultsTab(QFrame):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.qscrollarea = QScrollArea(self)
        self.results = ResultsFrame()
        self.qscrollarea.setWidget(self.results)
        self.qscrollarea.setWidgetResizable(True)
        layout.addWidget(self.qscrollarea)
        self.setLayout(layout)


class ResultsFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        # we want widgets to fill from top down,
        # being vertically centered looks weird
        self.layout.setAlignment(Qt.AlignTop)
        self.info_label = QLabel("After running checks, this tab will fill up "
                                 "with replays that can be played back. Newest "
                                 "results appear at the top.")
        self.layout.addWidget(self.info_label)
        self.setLayout(self.layout)


class QueueTab(QFrame):
    cancel_run_signal = pyqtSignal(int) # run_id

    def __init__(self):
        super().__init__()

        self.run_widgets = []
        layout = QVBoxLayout()
        self.qscrollarea = QScrollArea(self)
        self.queue = QueueFrame()
        self.qscrollarea.setWidget(self.queue)
        self.qscrollarea.setWidgetResizable(True)
        layout.addWidget(self.qscrollarea)
        self.setLayout(layout)

    def add_run(self, run):
        run_w = RunWidget(run)
        run_w.button.clicked.connect(partial(self.cancel_run, run.run_id))
        self.run_widgets.append(run_w)
        self.queue.layout.addWidget(run_w)

    def update_status(self, run_id, status):
        self.run_widgets[run_id].update_status(status)

    def cancel_run(self, run_id):
        self.cancel_run_signal.emit(run_id)
        self.run_widgets[run_id].cancel()

class QueueFrame(QFrame):

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.layout)

class ThresholdsTab(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.qscrollarea = QScrollArea(self)
        self.qscrollarea.setWidget(ScrollableThresholdsWidget(self))
        self.qscrollarea.setWidgetResizable(True)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.qscrollarea)
        self.setLayout(self.layout)

class ScrollableThresholdsWidget(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        steal_max_sim = SliderBoxSetting(self, "Max similarity", "ReplaySteal comparisons that score below this "
                "will be stored so you can view them, and printed to the console", "steal_max_sim", 100)
        steal_max_sim_display = SliderBoxSetting(self, "Max similarity display", "ReplaySteal comparisons that "
                "score below this will be printed to the console", "steal_max_sim_display", 100)
        relax_max_ur = SliderBoxSetting(self, "Max ur", "Replays that have a ur lower than this will be stored "
                "so you can view them, and printed to the console", "relax_max_ur", 300)
        relax_max_ur_display = SliderBoxSetting(self, "Max ur display", "Replays with a ur lower than this "
                "will be printed to the console", "relax_max_ur_display", 300)
        # display options for correction are more confusing than they're worth,
        # especially when we don't have a good mechanism for storing Snaps in
        # the Result tab or visualizer support for the Snap timestamps. TODO
        # potentially add back if we can provide good support for them.
        correction_max_angle = SliderBoxSetting(self, "Max angle", "Replays with a set of three points "
                "making an angle less than this (*and* also satisfying correction_min_distance) will be stored so "
                "you can view them, and printed to the console.", "correction_max_angle", 360)
        correction_min_distance = SliderBoxSetting(self, "Min distance", "Replays with a set of three points "
                "where either the distance from AB or BC is greater than this (*and* also satisfying correction_max_angle) "
                "will be stored so you can view them, and printed to the console.", "correction_min_distance", 100)

        timewarp_max_frametime = SliderBoxSetting(self, "Max frametime", "Replays with an average frametime "
                "lower than this will be stored so you can view them, and printed to the console", "timewarp_max_frametime", 50)
        timewarp_max_frametime_display = SliderBoxSetting(self, "Max frametime display", "Replays with an average frametime "
                "lower than this will be printed to the console", "timewarp_max_frametime_display", 50)


        layout = QVBoxLayout()
        layout.addWidget(Separator("Replay Stealing"))
        layout.addWidget(steal_max_sim)
        layout.addWidget(steal_max_sim_display)
        layout.addWidget(Separator("Relax"))
        layout.addWidget(relax_max_ur)
        layout.addWidget(relax_max_ur_display)
        layout.addWidget(Separator("Aim Correction"))
        layout.addWidget(correction_max_angle)
        layout.addWidget(correction_min_distance)
        layout.addWidget(Separator("Timewarp"))
        layout.addWidget(timewarp_max_frametime)
        layout.addWidget(timewarp_max_frametime_display)

        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)
