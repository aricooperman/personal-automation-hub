import re
import datetime
import os.path
import shutil

from configuration import joplin_configs


def get_last_modified_time_from_filename(file_path):
    modified_time = os.path.getmtime(file_path)
    return int(modified_time * 1000)


def get_title_from_filename(file_name):
    match = re.search(r"^(?:\d\d\d\d-\d\d-\d\d(?:\s\d\d.\d\d.\d\d)?\s?-?\s?)?(.+?)(?:\[\s*\w+(?:\s+\w+)*\s*\])?("
                      r"?:\.\w+)*?$", file_name)
    return match.group(1) if match else joplin_configs['default-title-prefix'] + '-' + datetime.datetime.now()


def get_tags_from_filename(file_name):
    match = re.search(r"^.*\[\s*(\w+(?:\s+\w+)*)\s*\](?:\.\w+)*?$", file_name)
    return match.group(1).split() if match else []


def move_file(file, directory):
    file_name = os.path.basename(file)
    shutil.move(file, os.path.abspath(os.path.join(directory, file_name)))
