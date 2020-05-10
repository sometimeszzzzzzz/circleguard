from pathlib import Path
import sys
import os
import bz2
import logging
import time
import sqlite3
from datetime import datetime, timedelta
from threading import Thread

from circleguard import Mod
from ossapi import ossapi
from packaging import version
import requests
from requests import RequestException
from PyQt5.QtWidgets import QLayout

# placeholder imports to have all imports at the top of the file. Imported for
# real farther below
#from settings import get_setting, set_setting
#from version import __version__

# placed above local imports to avoid circular import errors
ROOT_PATH = Path(__file__).parent.absolute()
def resource_path(str_path):
    """
    Returns a Path representing where to look for resource files for the program,
    such as databases or images.

    This location changes if the program is run from an application built with pyinstaller.
    """

    if hasattr(sys, '_MEIPASS'): # being run from a pyinstall'd app
        return Path(sys._MEIPASS) / Path(str_path) # pylint: disable=no-member
    return ROOT_PATH / Path(str_path)


from settings import get_setting, set_setting
from version import __version__


def run_update_check():
    last_check = datetime.strptime(get_setting("last_update_check"), get_setting("timestamp_format"))
    next_check = last_check + timedelta(hours=1)
    if next_check > datetime.now():
        return get_idle_setting_str()
    try:
        # check for new version
        git_request = requests.get("https://api.github.com/repos/circleguard/circleguard/releases/latest").json()
        git_version = version.parse(git_request["name"])
        set_setting("latest_version", git_version)
        set_setting("last_update_check", datetime.now().strftime(get_setting("timestamp_format")))
    except RequestException:
        # user is probably offline
        pass
    return get_idle_setting_str()


def get_idle_setting_str():
    current_version = version.parse(__version__)
    if current_version < version.parse(get_setting("latest_version")):
        return "<a href=\'https://circleguard.dev/download'>Update available!</a>"
    else:
        return "Idle"

class InvalidModException(Exception):
    """
    We were asked to parse an invalid mod string.
    """

def parse_mod_string(mod_string):
    """
    Takes a string made up of two letter mod names and converts them
    to a circlecore ModCombination.

    Returns None if the string is empty (mod_string == "")
    """
    if mod_string == "":
        return None
    if len(mod_string) % 2 != 0:
        raise InvalidModException(f"Invalid mod string {mod_string} (not of even length)")
    # slightly hacky, using ``Mod.NM`` our "no mod present" mod
    mod = Mod.NM
    for i in range(2, len(mod_string) + 1, 2):
        single_mod_string = mod_string[i - 2: i]
        # there better only be one Mod that has an acronym matching ours, but a comp + 0 index works too
        matching_mods = [mod for mod in Mod.ORDER if mod.short_name() == single_mod_string]
        if not matching_mods:
            raise InvalidModException(f"Invalid mod string (no matching mod found for {single_mod_string})")
        mod += matching_mods[0]
    return mod


def delete_widget(widget):
    if isinstance(widget.layout, QLayout):
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


class Run():
    """
    Represents a click of the Run button on the Main tab, which can contain
    multiple Checks, each of which contains a set of Loadables.
    """

    def __init__(self, checks, run_id, event):
        self.checks = checks
        self.run_id = run_id
        self.event = event


class Player:
    def __init__(self, replay, cursor_color):
        self.cursor_color = cursor_color
        self.username = replay.username
        self.t = replay.t
        self.xy = replay.xy
        self.k = replay.k
        self.end_pos = 0
        self.start_pos = 0
        self.mods = replay.mods


def score_to_acc(score_dict):
    judgements = (int(score_dict["countmiss"]) +
                  int(score_dict["count50"]) +
                  int(score_dict["count100"]) +
                  int(score_dict["count300"]))
    max_judgment_score = 300 * judgements
    achieved_judgment_score = (
            50 * int(score_dict["count50"]) +
            100 * int(score_dict["count100"]) +
            300 * int(score_dict["count300"]))
    accuracy = (achieved_judgment_score/max_judgment_score)*100
    return round(accuracy, 2)


def retrying_request(func, *args, max_retries=5, cooldown=5):
    for i in range(max_retries):
        try:
            response = func(*args)
            logging.error("Request %s succeeded (Attempt #%s)", func.__name__, i+1)
            return response
        except requests.exceptions.ConnectionError:
            logging.error("Request %s with params %s failed, sleeping for %s seconds and trying again (Attempt #%s)", func.__name__, params, cooldown, i+1)
            time.sleep(cooldown)
    return {"error": "Api not available"}


def _download_beatmap_cache():
    cache_file = os.path.join(get_setting("cache_dir"), "online.db")
    if os.path.exists(cache_file):
        return
    logging.info("Beatmap cache not found, downloading it")
    url = 'https://assets.ppy.sh/client-resources/online.db.bz2'
    r = requests.get(url).content
    decompressed = bz2.decompress(r)
    with open(cache_file + ".tmp", 'wb') as f:
        f.write(decompressed)
    # atomic file saving to be safe
    os.rename(cache_file + ".tmp", cache_file)
    logging.info("Beatmap cache downloaded")


def _convert_api_to_db_dict(api_dict, columns):
    merge_dict = {"user_id": api_dict["creator_id"],
                  "checksum": api_dict["file_md5"],
                  "countTotal":
                      int(api_dict["count_normal"])
                      + 2 * int(api_dict["count_slider"])
                      + 3 * int(api_dict["count_spinner"]),
                  "countNormal": api_dict["count_normal"],
                  "countSlider": api_dict["count_slider"],
                  "countSpinner": api_dict["count_spinner"],
                  "playmode": api_dict["mode"],
                  "filename":
                      api_dict["artist"]
                      + " - "
                      + api_dict["title"]
                      + " ("
                      + api_dict["creator"]
                      + ") ["
                      + api_dict["version"]
                      + "].osu"
                  }
    merge_dict.update(api_dict)
    return merge_dict


def cached_beatmap_lookup(beatmap_id):
    api = ossapi(get_setting("api_key"))
    cache_file = os.path.join(get_setting("cache_dir"), "online.db")

    if not os.path.exists(cache_file):
        logging.info("No Beatmap cache found, doing request")
        bm = retrying_request(api.get_beatmaps,
                              {"b": beatmap_id, "limit": 1})
        if "error" in bm or len(bm) == 0:
            return bm
        return bm[0]

    db = sqlite3.connect(cache_file)

    # get columns from db
    column_query = db.execute("SELECT c.name "
                              "FROM pragma_table_info('osu_beatmaps') c;")
    columns = column_query.fetchall()
    columns = [c[0] for c in columns]

    bm_query = db.execute("SELECT * FROM osu_beatmaps WHERE beatmap_id == ?",
                          (beatmap_id,))
    bm = bm_query.fetchone()

    if bm is None:
        logging.info("Beatmap isn't cached, doing request")
        bm = retrying_request(api.get_beatmaps,
                              {"b": beatmap_id, "limit": 1})
        if "error" in bm or len(bm) == 0:
            return bm
        bm = _convert_api_to_db_dict(bm[0], columns)

        # filter unused keys
        data = {key: bm[key] for key in columns if key in bm.keys()}

        keys = ','.join(data.keys())
        question_marks = ','.join(list('?'*len(data)))
        values = tuple(data.values())

        db.execute("INSERT INTO osu_beatmaps ("+keys+")  VALUES ("
                   + question_marks + ")", values)
        db.commit()
        return data

    return {d[0]: d[1] for d in zip(columns, bm)}


# download db asap
Thread(target=_download_beatmap_cache).start()
print(cached_beatmap_lookup(221777))
