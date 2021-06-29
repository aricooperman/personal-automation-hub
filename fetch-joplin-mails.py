#!/usr/bin/env python

import datetime
import traceback

import mail_functions
import joplin_api_functions
from configuration import joplin_configs, mail_configs, evernote_configs

print("===============================")
print("Start: ", str(datetime.datetime.now()))

try:
    messages = mail_functions.fetch_mail(joplin_configs['mailbox'])
    if len(messages) < 1:
        print(f"Did not find any messages")

    for uid, msg in messages.items():
        print("-------------------")
        subject = mail_functions.get_subject(msg)
        print(f"Processing '{subject}'")

        try:
            joplin_api_functions.add_new_note_from_message(msg)
            if evernote_configs['enabled']:
                mail_functions.send_mail(msg, evernote_configs['email'])
            if mail_configs['archive']:
                print("Archiving message")
                mail_functions.archive_mail(joplin_configs['mailbox'], uid)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: Mail '{subject}' could not be added: {str(e)}")

except Exception as e:
    traceback.print_exc()
    print(f"Error: Problem processing Joplin email forwarding: {str(e)}")

print("-------------------")

if joplin_configs['auto-sync']:
    print("Starting Joplin Sync")
    if joplinfuncs.sync() != 0:
        print("Failure running joplin sync")

print("===============================")
print("End: ", str(datetime.datetime.now()))
