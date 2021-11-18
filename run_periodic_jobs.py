#!/usr/bin/env python

import datetime
import os
import re
import traceback
from email.message import EmailMessage

from configuration import joplin_configs, evernote_configs, mail_configs, file_configs, kindle_configs, \
    todoist_configs, trello_configs
from constants import LOCAL_TZ, DEFAULT_TZ
from file.functions import move_file
from joplin.functions import sync, get_note_resources, get_resource_file, handle_processed_note, \
    add_new_note_from_file, add_new_note_from_message, get_tag, get_notes_with_tag, get_note_tags
from my_todoist.functions import get_all_projects, create_project, add_task, add_file_comment
from mail.functions import fetch_mail, send_mail, archive_mail, get_subject

FILTERED_JOPLIN_TAGS = [joplin_configs['processed-tag'], todoist_configs['joplin-tag']]

# def process_todoist_directory():
#     #TODO
#     print("Processing Todoist files")
#     directory = todoist_configs['directory']
#     if not os.path.exists(directory) or not os.path.isdir(directory):
#         print("No directory configured for Joplin file processing. Set configuration value joplin.directory")
#         return
#
#     try:
#         for dir_path, _, filenames in os.walk(directory):
#             for f in filenames:
#                 file = os.path.abspath(os.path.join(dir_path, f))
#                 try:
#                     print(f" Adding {file} to Todoist")
#                     add_new_task_from_file(file)
#                     if file_configs['archive']:
#                         print(" Archiving file")
#                         move_file(file, file_configs['archive'])
#                 except Exception as e:
#                     traceback.print_exc()
#                     print(f"Error: File '{file}' could not be added: {str(e)}")
#
#     except Exception as e:
#         traceback.print_exc()
#         print(f"Error: Problem processing Joplin file: {str(e)}")


# def process_todoist_joplin_project():
#     #TODO
#     pass


def forward_mail():
    print("Processing Mail Forwarding")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")

        forwarding_map = account['mail-forward']
        for mailbox, email in forwarding_map.items():
            try:
                messages = fetch_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                      account['password'], mailbox)
                for uid, msg in messages.items():
                    try:
                        print(f"  Forwarding '{get_subject(msg)}' in {mailbox} mailbox")
                        send_mail(msg, email)
                        if mail_configs['archive']:
                            print("  Archiving message")
                            archive_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                         account['password'], mailbox, uid,
                                         account['archive-folder'] if 'archive-folder' in account else None)
                    except Exception as e:
                        traceback.print_exc()
                        print(f"Error: Mail '{get_subject(msg)}' could not be forwarded: {str(e)}")

            except Exception as e:
                traceback.print_exc()
                print(f"Error: Problem forwarding emails in {mailbox} mailbox: {str(e)}")


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


def process_joplin_kindle_tag():
    print("Processing Kindle tag in Joplin")
    tag = get_tag(kindle_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" Unable to find the Joplin tag {kindle_configs['joplin-tag']}")
        return

    notes = get_notes_with_tag(tag)
    for note in notes:
        if is_processed(note):
            continue

        try:
            msg = EmailMessage()
            msg['Subject'] = note['title']

            resources = get_note_resources(note)
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


def is_processed(note):
    processed_tag_name = joplin_configs['processed-tag'].lower()
    processed_tag = next((tag for tag in get_note_tags(note) if tag['title'].lower() == processed_tag_name), None)
    return True if processed_tag else False


def process_joplin_todoist_tag():
    print("Processing Todoist tag in Joplin")
    tag = get_tag(todoist_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" Unable to find the Joplin notebook {todoist_configs['joplin-tag']}")
        return

    notes = get_notes_with_tag(tag)
    for note in notes:
        if is_processed(note):
            continue

        print(f" Copying note '{note['title']}' as task")

        due = None
        if 'todo_due' in note and note['todo_due'] > 0:
            dt = datetime.datetime.fromtimestamp(note['todo_due'] / 1000.0, tz=datetime.timezone.utc)
            dt_str = dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%dT%H:%M:%S')
            due = {'date': dt_str, 'timezone': DEFAULT_TZ, 'is_recurring': False, 'lang': 'en'}

        content = note['title']
        if len(note['source_url']) > 0:
            content = f"[{content}]({note['source_url']})"

        comment = None
        if note['body'] and len(note['body']) > 0:
            comment = note['body']
            comment = re.sub(r'!?\[.*\]\(:/[a-f0-9]+\)', '', comment).strip()

        tags = get_note_tags(note)
        labels = [tag['title'] for tag in tags if tag['title'] not in FILTERED_JOPLIN_TAGS]
        projects = [label for label in labels if label.startswith('#')]
        labels = list(set(labels) - set(projects))
        project = None
        if len(projects) > 0:
            if len(projects) > 1:
                print(f"  Warning: task {note['title']} has more than one project tag {projects}, using first")
            proj_name = projects[0][1:]
            project = next((proj for proj in get_all_projects() if proj['name'] == proj_name), None)
            if project is None:
                print(f"  Creating Todoist project '{proj_name}'")
                project = create_project(proj_name)

        labels.append("Joplin")
        task = add_task(content, comment=comment, due=due, labels=labels, project=project)

        resources = get_note_resources(note)
        for resource in resources:
            file_bytes = get_resource_file(resource['id'])
            add_file_comment(task['id'], file_bytes, resource['title'], resource['mime'])

        handle_processed_note(note)


def process_joplin_trello_tag():
    print("Processing Trello tag in Joplin")
    tag = get_tag(trello_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" Unable to find the Joplin tag {trello_configs['joplin-tag']}")
        return

    notes = get_notes_with_tag(tag)
    for note in notes:
        if is_processed(note):
            continue

        try:
            msg = EmailMessage()
            msg['Subject'] = note['title']

            resources = get_note_resources(note)
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


print("Start: ", str(datetime.datetime.now()))
print("===============================")

forward_mail()

process_joplin_email_mailbox()
process_joplin_directory()
process_joplin_kindle_tag()
process_joplin_todoist_tag()
process_joplin_trello_tag()

if joplin_configs['auto-sync']:
    print("Starting Joplin Sync")
    sync()

print("===============================")
print("End: ", str(datetime.datetime.now()))
