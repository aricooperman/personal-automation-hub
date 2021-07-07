#!/usr/bin/env python

import datetime
import os
import traceback

from configuration import todoist_configs, file_configs, mail_configs
from file.functions import move_file
from functions import add_new_task_from_message, add_new_task_from_file


def process_todoist_directory():
    #TODO
    print("Handling Todoist files")
    directory = todoist_configs['directory']
    if not os.path.exists(directory) or not os.path.isdir(directory):
        print("No directory configured for Joplin file processing. Set configuration value joplin.directory")
        return

    try:
        for dir_path, _, filenames in os.walk(directory):
            for f in filenames:
                file = os.path.abspath(os.path.join(dir_path, f))
                print("-------------------")
                try:
                    add_new_task_from_file(file)
                    if file_configs['archive']:
                        print("Archiving file")
                        move_file(file, file_configs['archive'])
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error: File '{file}' could not be added: {str(e)}")

    except Exception as e:
        traceback.print_exc()
        print(f"Error: Problem processing Joplin file: {str(e)}")


def process_todoist_joplin_project():
    #TODO
    pass


if __name__ == "__main__":
    process_todoist_directory()
    process_todoist_joplin_project()
