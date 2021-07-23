#!/usr/bin/env python

import datetime
import os
import traceback
from email.message import EmailMessage

from configuration import joplin_configs, evernote_configs, mail_configs, file_configs, kindle_configs, todoist_configs, \
    trello_configs
from file.functions import move_file
from joplin.functions import sync, get_resources, get_resource_file, handle_processed_note, get_notes, get_notebook, \
    add_new_note_from_file, add_new_note_from_message
from mail.functions import send_mail, archive_mail, get_subject, fetch_mail
from my_todoist.functions import add_joplin_note_as_task


def process_joplin_email_mailbox():
    print("Processing Joplin emails")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")
        try:
            messages = fetch_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                  account['password'], joplin_configs['mailbox'])
            for uid, msg in messages.items():
                subject = get_subject(msg)
                print(f"  Moving '{subject}' to Joplin")

                try:
                    add_new_note_from_message(msg)
                    if evernote_configs['enabled']:
                        send_mail(msg, evernote_configs['email'])
                    if mail_configs['archive']:
                        print("  Archiving message")
                        archive_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                     account['password'], joplin_configs['mailbox'], uid,
                                     account['archive-folder'] if 'archive-folder' in account else None)
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error: Mail '{subject}' could not be added: {str(e)}")

        except Exception as e:
            traceback.print_exc()
            print(f"Error: Problem processing Joplin email forwarding: {str(e)}")


def process_joplin_directory():
    print("Processing Joplin files")
    directory = joplin_configs['directory']
    if not os.path.exists(directory) or not os.path.isdir(directory):
        print("No directory configured for Joplin file processing. Set configuration value joplin.directory")
        return

    try:
        for dir_path, _, filenames in os.walk(directory):
            for f in filenames:
                file = os.path.abspath(os.path.join(dir_path, f))
                try:
                    print(f" Adding file {file} to Joplin")
                    add_new_note_from_file(file)
                    if file_configs['archive']:
                        print(" Archiving file")
                        move_file(file, file_configs['archive'])
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error: File '{file}' could not be added: {str(e)}")

    except Exception as e:
        traceback.print_exc()
        print(f"Error: Problem processing Joplin file: {str(e)}")


def process_joplin_kindle_notebook():
    print("Processing Kindle notebook in Joplin")
    notebook = get_notebook(kindle_configs['joplin-notebook'], default_on_missing=False,
                                      auto_create=False)
    if not notebook:
        print(f" Unable to find the Joplin notebook {kindle_configs['joplin-notebook']}")
        return

    notes = get_notes(notebook)
    for note in notes:
        try:
            print(f" Moving note '{note['title']}'")

            msg = EmailMessage()
            msg['Subject'] = note['title']

            resources = get_resources(note['id'])
            for resource in resources:
                # TODO check supported format
                file_bytes = get_resource_file(resource['id'])
                maintype, subtype = resource['mime'].split('/', 1)
                msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=resource['title'])

            print(f"Sending note attachments to Kindle ")
            send_mail(msg, kindle_configs['email'])
            handle_processed_note(note)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: Note '{note['title']}' could not sent to Kindle: {str(e)}")


def process_joplin_todoist_notebook():
    print("Processing Todoist notebook in Joplin")
    notebook = get_notebook(todoist_configs['joplin-notebook'], default_on_missing=False, auto_create=False)
    if not notebook:
        print(f" Unable to find the Joplin notebook {todoist_configs['joplin-notebook']}")
        return

    notes = get_notes(notebook)
    for note in notes:
        print(f" Moving note '{note['title']}'")
        add_joplin_note_as_task(note)
        handle_processed_note(note)


def process_joplin_trello_notebook():
    print("Processing Trello notebook in Joplin")
    notebook = get_notebook(trello_configs['joplin-notebook'], default_on_missing=False, auto_create=False)
    if not notebook:
        print(f" Unable to find the Joplin notebook {kindle_configs['joplin-notebook']}")
        return

    notes = get_notes(notebook)
    for note in notes:
        try:
            print("")
            print(f" Moving note '{note['title']}'")

            msg = EmailMessage()
            msg['Subject'] = note['title']

            resources = get_resources(note['id'])
            for resource in resources:
                file_bytes = get_resource_file(resource['id'])
                maintype, subtype = resource['mime'].split('/', 1)
                msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=resource['title'])

            print(f" Sending note to Trello ")
            send_mail(msg, trello_configs['email'])
            handle_processed_note(note)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: Note '{note['title']}' could not sent to Kindle: {str(e)}")


if __name__ == "__main__":
    print("Start: ", str(datetime.datetime.now()))
    print("===============================")

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
