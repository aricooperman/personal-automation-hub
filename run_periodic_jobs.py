#!/usr/bin/env python

import datetime

from configuration import joplin_configs
from joplin.actions import process_joplin_email_mailbox, process_joplin_directory, process_joplin_kindle_notebook, \
    process_joplin_todoist_notebook, process_joplin_trello_notebook
from joplin.functions import sync
from mail.actions import forward_mail

print("Start: ", str(datetime.datetime.now()))
print("===============================")

forward_mail()

process_joplin_email_mailbox()
process_joplin_directory()
process_joplin_kindle_notebook()
process_joplin_todoist_notebook()
process_joplin_trello_notebook()

if joplin_configs['auto-sync']:
    print("Starting Joplin Sync")
    sync()

print("===============================")
print("End: ", str(datetime.datetime.now()))
