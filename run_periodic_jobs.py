#!/usr/bin/env python

import datetime
import traceback
from email.message import EmailMessage
from io import BytesIO, StringIO
from typing import List

import dateutil.parser
import pytz
from todoist_api_python.models import Comment

import service
from configuration import joplin_configs, mail_configs, kindle_configs, todoist_configs, trello_configs, \
    obsidian_configs
from constants import LOCAL_TZ, DEFAULT_TZ
from enums import MimeType
from service import obsidian_api
from service.joplin_api import JoplinNote
from service.todoist_api import get_all_projects, create_project, add_task, add_file_comment, get_label, \
    get_tasks_with_label, complete_task, get_task_comments, get_project, get_project_tasks, add_comment
from utils.mail import fetch_mail, send_mail, archive_mail, get_subject, get_title_from_subject, \
    get_tags_from_subject, get_notebook_from_subject, determine_mime_type, get_email_body
from utils.ocr import get_image_full_text
from utils.pdf import get_pdf_full_text

FILTERED_JOPLIN_TAGS = [joplin_configs['processed-tag']]  # , todoist_configs['joplin-tag']]


def forward_mail():
    print("Processing Mail Forwarding")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")

        forwarding_map = account['mail-forward']
        for mailbox, email in forwarding_map.items():
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
                except Exception as exc:
                    raise RuntimeError(f"Error: Mail '{get_subject(msg)}' could not be forwarded: {str(exc)}") from exc


def process_joplin_email_mailbox() -> None:
    print("Processing Joplin emails")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")
        messages = fetch_mail(account['imap']['server'], account['imap']['port'], account['username'],
                              account['password'], joplin_configs['mailbox'])
        for uid, msg in messages.items():
            subject = get_subject(msg)
            print(f"  Moving '{subject}' to Joplin")

            try:
                title = get_title_from_subject(subject)
                tags = get_tags_from_subject(subject)
                notebook_name = get_notebook_from_subject(subject)
                body, content_type = get_email_body(msg)
                notebook = service.joplin_api.get_notebook(notebook_name)

                note = service.joplin_api.create_new_note(title, body, notebook_id=notebook['id'],
                                       is_html=(content_type == 'text/html'))

                service.joplin_api.add_note_tags(note, tags)

                add_email_attachments_to_joplin_note(msg, note)

                if mail_configs['archive']:
                    print("  Archiving message")
                    archive_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                 account['password'], joplin_configs['mailbox'], uid,
                                 account['archive-folder'] if 'archive-folder' in account else None)
            except Exception as exc:
                raise RuntimeError(f"Error: Mail '{subject}' could not be added: {str(exc)}") from exc


def process_obsidian_email_mailbox() -> None:
    print("Processing Obsidian emails")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")
        messages = fetch_mail(account['imap']['server'], account['imap']['port'], account['username'],
                              account['password'], obsidian_configs['mailbox'])
        for uid, msg in messages.items():
            subject = get_subject(msg)
            print(f"  Moving '{subject}' to Obsidian")

            try:
                title = get_title_from_subject(subject)
                tags = get_tags_from_subject(subject)
                notebook_name = get_notebook_from_subject(subject)
                body, content_type = get_email_body(msg)

                path, filename = obsidian_api.create_new_note(title, body, path=notebook_name,
                                                              is_html=(content_type == 'text/html'), tags=tags)

                add_email_attachments_to_obsidian_note(msg, path, filename)

                if mail_configs['archive']:
                    print("  Archiving message")
                    archive_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                 account['password'], obsidian_configs['mailbox'], uid,
                                 account['archive-folder'] if 'archive-folder' in account else None)
            except Exception as exc:
                raise RuntimeError(f"Error: Mail '{subject}' could not be added: {str(exc)}") from exc


def add_email_attachments_to_joplin_note(email_message, note: JoplinNote):
    for part in email_message.iter_attachments():
        content_type = part.get_content_type()
        if part.is_multipart():
            add_email_attachments_to_joplin_note(part, note)
        else:
            file_name = part.get_filename(failobj="unknown_file_name")
            part_type = determine_mime_type(file_name, content_type)
            content = part.get_content()
            if isinstance(content, bytes):
                with BytesIO(content) as f:
                    service.joplin_api.add_attachment(note, file_name, f, part_type)
            else:
                with StringIO(content) as f:
                    service.joplin_api.add_attachment(note, file_name, f, part_type)


def add_email_attachments_to_obsidian_note(email_message, path: str, filename: str):
    for part in email_message.iter_attachments():
        content_type = part.get_content_type()
        if part.is_multipart():
            add_email_attachments_to_obsidian_note(part, path)
        else:
            attachment_name = part.get_filename(failobj="unknown_file_name")
            part_type = determine_mime_type(attachment_name, content_type)
            content = part.get_content()
            if isinstance(content, bytes):
                with BytesIO(content) as f:
                    obsidian_api.add_attachment(path, filename, attachment_name, f, part_type)
            else:
                with StringIO(content) as f:
                    obsidian_api.add_attachment(path, filename, attachment_name, f, part_type)


def process_joplin_kindle_tag():
    if 'joplin-tag' not in kindle_configs:
        return

    print("Processing Kindle tag in Joplin")
    tag = service.joplin_api.get_tag(kindle_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" Unable to find the Joplin tag {kindle_configs['joplin-tag']}")
        return

    notes = service.joplin_api.get_notes_with_tag(tag)
    if len(notes) > 0:
        send_notes_to_kindle(notes)


def process_joplin_kindle_notebook():
    if 'joplin-notebook' not in kindle_configs:
        return

    print("Processing Kindle notebook in Joplin")
    notebook = service.joplin_api.get_notebook(kindle_configs['joplin-notebook'], default_on_missing=False, auto_create=False)
    if not notebook:
        print(f" Unable to find the Joplin notebook {kindle_configs['joplin-notebook']}")
        return

    notes = service.joplin_api.get_notes_in_notebook(notebook)
    if len(notes) > 0:
        send_notes_to_kindle(notes)


def send_notes_to_kindle(notes: List[service.joplin_api.JoplinNote]):
    for note in notes:
        if service.joplin_api.is_processed(note):
            continue

        try:
            msg = EmailMessage()
            msg['Subject'] = note['title']

            resources = service.joplin_api.get_note_resources(note)
            for resource in resources:
                # TODO check supported format
                file_bytes = service.joplin_api.get_resource_file(resource['id'])
                maintype, subtype = resource['mime'].split('/', 1)
                msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=resource['title'])

            print(f" Sending note attachments to Kindle ")
            send_mail(msg, kindle_configs['email'])
            service.joplin_api.handle_processed_note(note)
        except Exception as exc:
            raise RuntimeError(f"Error: Note '{note['title']}' could not sent to Kindle: {str(exc)}") from exc


def process_joplin_todoist_tag():
    if 'joplin-tag' not in todoist_configs:
        return

    print("Processing Todoist tag in Joplin")
    tag = service.joplin_api.get_tag(todoist_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" Unable to find the Joplin tag {todoist_configs['joplin-tag']}")
        return

    notes = service.joplin_api.get_notes_with_tag(tag)
    if len(notes) > 0:
        send_notes_to_todoist_from_joplin(notes)


def process_joplin_todoist_notebook():
    if 'joplin-notebook' not in todoist_configs:
        return

    print("Processing Todoist notebook in Joplin")
    notebook = service.joplin_api.get_notebook(todoist_configs['joplin-notebook'], default_on_missing=False, auto_create=False)
    if not notebook:
        print(f" Unable to find the Joplin notebook {todoist_configs['joplin-notebook']}")
        return

    notes = service.joplin_api.get_notes_in_notebook(notebook)
    if len(notes) > 0:
        send_notes_to_todoist_from_joplin(notes)


def send_notes_to_todoist_from_joplin(notes: List[service.joplin_api.JoplinNote]):
    for note in notes:
        if service.joplin_api.is_processed(note):
            continue

        print(f" Copying note '{note['title']}' as task")

        due = None
        if 'todo_due' in note and note['todo_due'] > 0:
            dt = datetime.datetime.fromtimestamp(note['todo_due'] / 1000.0, tz=datetime.timezone.utc)
            due = dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%dT%H:%M:%S')

        content = note['title']
        if len(note['source_url']) > 0:
            content = f"[{content}]({note['source_url']})"

        tags = service.joplin_api.get_note_tags(note)
        labels = [tag['title'] for tag in tags if tag['title'] not in FILTERED_JOPLIN_TAGS]
        projects = [label for label in labels if label.startswith('#')]
        labels = list(set(labels) - set(projects))
        project = None
        if len(projects) > 0:
            if len(projects) > 1:
                print(f"  Warning: task {note['title']} has more than one project tag {projects}, using first")
            proj_name = projects[0][1:]
            project = next((proj for proj in get_all_projects() if proj.name == proj_name), None)
            if project is None:
                print(f"  Creating Todoist project '{proj_name}'")
                project = create_project(proj_name)

        task = add_task(content, due=due, labels=labels, project=project)

        if note['body'] and len(note['body']) > 0:
            add_comment(task, note['body'])

        add_comment(task, f"joplin://x-callback-url/openNote?id={note['id']}")

        resources = service.joplin_api.get_note_resources(note)
        for resource in resources:
            file_bytes = service.joplin_api.get_resource_file(resource['id'])
            add_file_comment(task, file_bytes, resource['title'], resource['mime'])

        service.joplin_api.handle_processed_note(note)


def process_joplin_trello_tag():
    if 'joplin-tag' not in trello_configs:
        return

    print("Processing Trello tag in Joplin")
    tag = service.joplin_api.get_tag(trello_configs['joplin-tag'], auto_create=False)
    if not tag:
        print(f" No Joplin tag {trello_configs['joplin-tag']}")
        return

    notes = service.joplin_api.get_notes_with_tag(tag)
    if len(notes) > 0:
        send_notes_to_trello(notes)


def process_joplin_trello_notebook():
    if 'joplin-notebook' not in trello_configs:
        return

    print("Processing Trello notebook in Joplin")
    notebook = service.joplin_api.get_notebook(trello_configs['joplin-notebook'], default_on_missing=False, auto_create=False)
    if not notebook:
        print(f" No Joplin notebook {trello_configs['joplin-notebook']}")
        return

    notes = service.joplin_api.get_notes_in_notebook(notebook)
    if len(notes) > 0:
        send_notes_to_trello(notes)


def send_notes_to_trello(notes: List[service.joplin_api.JoplinNote]):
    for note in notes:
        if service.joplin_api.is_processed(note):
            continue

        try:
            trello_msg = EmailMessage()
            trello_msg['Subject'] = note['title']

            resources = service.joplin_api.get_note_resources(note)
            for resource in resources:
                file_bytes = service.joplin_api.get_resource_file(resource['id'])
                maintype, subtype = resource['mime'].split('/', 1)
                trello_msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=resource['title'])

            print(f" Sending note to Trello ")
            # TODO use Trello API
            send_mail(trello_msg, trello_configs['email'])
            service.joplin_api.handle_processed_note(note)
        except Exception as exc:
            raise RuntimeError(f"Error: Note '{note['title']}' could not sent to Kindle: {str(exc)}") from exc


def process_joplin_ocr_tag():
    print("Processing OCR tag in Joplin")
    tag = service.joplin_api.get_tag(joplin_configs['ocr-tag'], auto_create=False)
    if not tag:
        print(f" No Joplin tag {joplin_configs['ocr-tag']}")
        return

    notes = service.joplin_api.get_notes_with_tag(tag)
    for note in notes:
        for resource in service.joplin_api.get_note_resources(note):
            mime_type = determine_mime_type(resource['filename'], resource['mime'])
            if mime_type == MimeType.IMG:
                file = service.joplin_api.get_resource_file(resource['id'])
                img_text = get_image_full_text(BytesIO(file))
                if len(img_text.strip()) > 0:
                    service.joplin_api.append_to_note(note, img_text)
            elif mime_type == MimeType.PDF:
                file = service.joplin_api.get_resource_file(resource['id'])
                pdf_text = get_pdf_full_text(BytesIO(file))
                if len(pdf_text.strip()) > 0:
                    service.joplin_api.append_to_note(note, pdf_text)

        service.joplin_api.remove_note_tag(note, tag)


def get_todoist_comment_text(comment: Comment) -> str:
    if comment.attachment is None:
        return comment.content
    else:
        link = f"[{comment.attachment.file_name} - {comment.attachment.file_type}]" \
               f"({comment.attachment.file_url})"
        return link


def process_todoist_joplin_tag():
    print("Processing Todoist tag in Joplin")

    joplin_service_configs = todoist_configs['service']['joplin']
    mapping = joplin_service_configs['tag-mapping']

    todoist_label = get_label(mapping[0])
    tasks = get_tasks_with_label(todoist_label)

    if len(tasks) > 0:
        todoist_joplin_tag = service.joplin_api.get_tag(mapping[1], auto_create=True)
        processed_tag = joplin_service_configs['processed-tag']
        todoist_processed_label = get_label(processed_tag) if processed_tag is not None else None

        if todoist_processed_label is not None:
            tasks = [i for i in tasks if i.labels is None or todoist_processed_label.name not in i.labels]

        for task in tasks:
            print(f" Copying task '{task.content}' as note")

            body = task.description if task.description is not None and len(task.description) > 0 else None
            due = None
            if task.due is not None and (task.due.date is not None or task.due.datetime is not None):
                dt = dateutil.parser.isoparse(task.due.datetime if task.due.datetime is not None else task.due.date)
                tz = task.due.timezone if task.due.timezone is not None else DEFAULT_TZ
                dt = dt.astimezone(pytz.timezone(tz))
                due = int(dt.strftime('%s')) * 1000

            joplin_note = service.joplin_api.create_new_note(task.content, body, notebook_id=None, is_html=True, due_date=due)

            for comment in get_task_comments(task):
                service.joplin_api.append_to_note(joplin_note, get_todoist_comment_text(comment))

            todoist_project = get_project(task.project_id)
            child_items = [i for i in get_project_tasks(todoist_project) if i.project_id == task.id]
            if len(child_items) > 0:
                for child_item in child_items:
                    append_note = 'Task: ' + child_item.content + " " + child_item.description
                    for child_comment in get_task_comments(child_item):
                        append_note += '\n' + get_todoist_comment_text(child_comment)
                    service.joplin_api.append_to_note(joplin_note, append_note)
                    item_to_remove = next((i for i in tasks if i.id == child_item.id), None)
                    if item_to_remove is not None:
                        tasks.remove(item_to_remove)

            service.joplin_api.add_note_tag(joplin_note, todoist_joplin_tag)

            joplin_tag = next((t for t in service.joplin_api.get_tags() if t['title'][1:].lower() == todoist_project.name.lower()), None)
            if joplin_tag is None and todoist_project.name != 'Inbox':
                joplin_tag = service.joplin_api.create_tag('#' + todoist_project.name)

            if joplin_tag is not None:
                service.joplin_api.add_note_tag(joplin_note, joplin_tag)

            complete_task(task)


print("Start: ", str(datetime.datetime.now()))
print("===============================")

try:
    # Mail Handling
    forward_mail()
    process_joplin_email_mailbox()
    process_obsidian_email_mailbox()

    # Joplin Handling
    process_joplin_ocr_tag()
    process_joplin_kindle_tag()
    process_joplin_kindle_notebook()
    process_joplin_todoist_tag()
    process_joplin_todoist_notebook()
    process_joplin_trello_tag()
    process_joplin_trello_notebook()

    # Todoist Handling
    process_todoist_joplin_tag()

    if joplin_configs['auto-sync']:
        print("Starting Joplin Sync")
        service.joplin_api.sync()
except Exception as e:
    msg = EmailMessage()
    msg['Subject'] = "Automation Hub Error"
    msg.set_content(traceback.format_exc())
    send_mail(msg, mail_configs['smtp']['username'])
    raise e

print("===============================")
print("End: ", str(datetime.datetime.now()))
