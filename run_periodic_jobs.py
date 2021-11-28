#!/usr/bin/env python

import datetime
import os
import re
import traceback
from email.message import EmailMessage
from io import BytesIO, StringIO

import dateutil.parser
import pytz
from todoist.models import Note

from configuration import joplin_configs, evernote_configs, mail_configs, file_configs, kindle_configs, \
    todoist_configs, trello_configs
from constants import LOCAL_TZ, DEFAULT_TZ
from file.functions import move_file
from joplin.functions import sync, get_note_resources, get_resource_file, handle_processed_note, \
    add_new_note_from_file, get_tag, get_notes_with_tag, get_note_tags, is_processed, \
    get_notebook, create_new_note, add_note_tags, add_attachment, get_tags, create_tag, add_note_tag, append_to_note
from mail.functions import fetch_mail, send_mail, archive_mail, get_subject, get_title_from_subject, \
    get_tags_from_subject, get_notebook_from_subject, determine_mime_type, get_email_body
from my_todoist.functions import get_all_projects, create_project, add_item, add_file_comment, get_label, \
    get_items_with_label, get_item_notes, get_project, archive_item, get_item_detail, get_project_details

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


def process_joplin_email_mailbox() -> None:
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
                    subject = get_subject(msg)
                    title = get_title_from_subject(subject)
                    tags = get_tags_from_subject(subject)
                    notebook_name = get_notebook_from_subject(subject)
                    body, content_type = get_email_body(msg)
                    notebook = get_notebook(notebook_name)

                    note = create_new_note(title, body, notebook_id=notebook['id'],
                                           is_html=(content_type == 'text/html'))

                    add_note_tags(note, tags)

                    for part in msg.iter_attachments():
                        file_name = part.get_filename(failobj="unknown_file_name")
                        content_type = part.get_content_type()
                        part_type = determine_mime_type(file_name, content_type)
                        content = part.get_content()
                        if isinstance(content, bytes):
                            with BytesIO(content) as f:
                                add_attachment(note, file_name, f, part_type)
                        else:
                            with StringIO(content) as f:
                                add_attachment(note, file_name, f, part_type)

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

        labels.append("From-Joplin")
        task = add_item(content, comment=comment, due=due, labels=labels, project=project)

        resources = get_note_resources(note)
        for resource in resources:
            file_bytes = get_resource_file(resource['id'])
            add_file_comment(task['id'], file_bytes, resource['title'], resource['mime'])

        handle_processed_note(note)


def process_joplin_trello_tag():
    print("Processing Trello tag in Joplin")
    tag = get_tag(trello_configs['joplin-tag'], auto_create=True)
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
            # TODO use Trello API
            send_mail(msg, trello_configs['email'])
            handle_processed_note(note)
        except Exception as e:
            traceback.print_exc()
            print(f"Error: Note '{note['title']}' could not sent to Kindle: {str(e)}")


def get_todoist_note_text(note):
    if note['file_attachment'] is None:
        return note['content']
    else:
        link = f"[{note['file_attachment']['file_name']} - {note['file_attachment']['file_type']}]" \
               f"({note['file_attachment']['file_url']})"
        return link


def process_todoist_joplin_tag():
    print("Processing Todoist tag in Joplin")

    joplin_service_configs = todoist_configs['service']['joplin']
    mapping = joplin_service_configs['tag-mapping']

    todoist_label = get_label(mapping[0])
    items = get_items_with_label(todoist_label)

    items = [i for i in items if not i['checked'] and not i['is_deleted'] and not i['in_history']]

    if len(items) > 0:
        todoist_joplin_tag = get_tag(mapping[1], auto_create=True)
        processed_tag = joplin_service_configs['processed-tag']
        todoist_processed_label = get_label(processed_tag) if processed_tag is not None else None

        if todoist_processed_label is not None:
            items = [i for i in items if 'labels' not in i or todoist_processed_label['id'] not in i['labels']]

        for item in items:
            print(f" Copying task '{item['content']}' as note")
            item_detail = get_item_detail(item['id'])

            body = item['description'] if 'description' in item and len(item['description']) > 0 else None
            due = None
            if 'due' in item and item['due'] is not None and 'date' in item['due']:
                dt = dateutil.parser.isoparse(item['due']['date'])
                tz = item['due']['timezone'] if item['due']['timezone'] is not None else DEFAULT_TZ
                dt = dt.astimezone(pytz.timezone(tz))
                due = int(dt.strftime('%s')) * 1000

            joplin_note = create_new_note(item['content'], body, notebook_id=None, is_html=True, due_date=due)

            for comment in item_detail['notes']:
                append_to_note(joplin_note, get_todoist_note_text(comment))

            todoist_project = item_detail['project']
            todoist_project_details = get_project_details(todoist_project['id'])
            child_items = [i for i in todoist_project_details['items'] if i['parent_id'] == item['id']]
            if len(child_items) > 0:
                for child_item in child_items:
                    append_note = 'Task: ' + child_item['content'] + " " + child_item['description']
                    for child_note in get_item_detail(child_item['id'])['notes']:
                        append_note += '\n' + get_todoist_note_text(child_note)
                    append_to_note(joplin_note, append_note)
                    item_to_remove = next((i for i in items if i['id'] == child_item['id']), None)
                    if item_to_remove is not None:
                        items.remove(item_to_remove)

            add_note_tag(joplin_note, todoist_joplin_tag)

            joplin_tag = next((t for t in get_tags() if t['title'][1:].lower() == todoist_project['name'].lower()),
                              None)
            if joplin_tag is None and todoist_project['name'] != 'Inbox':
                joplin_tag = create_tag('#' + todoist_project['name'])

            if joplin_tag is not None:
                add_note_tag(joplin_note, joplin_tag)

            archive_item(item)


print("Start: ", str(datetime.datetime.now()))
print("===============================")

# Mail Handling
forward_mail()
process_joplin_email_mailbox()

# Joplin Handling
process_joplin_directory()
process_joplin_kindle_tag()
process_joplin_todoist_tag()
process_joplin_trello_tag()

# Todoist Handling
process_todoist_joplin_tag()

if joplin_configs['auto-sync']:
    print("Starting Joplin Sync")
    sync()

print("===============================")
print("End: ", str(datetime.datetime.now()))
