import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
from itertools import groupby
from typing import Dict, List, Optional, Union

import markdown
import pdfkit
from todoist.models import Project

from service.joplin_api import get_notes_with_tag, Tag, get_active_projects, get_default_notebook, get_notes_in_notebook
from utils.mail import send_mail
from service.todoist_api import get_active_projects as get_todoist_projects, get_labels, get_project_tasks, \
    get_project_sections
from configuration import mail_configs

file_str = StringIO()


def print_project(level: int, project_name: str) -> None:
    indicator = "*" if level > 0 else "**"
    print_table_row(indicator + project_name + indicator, '', '', None, '', None)


def print_section(section_name):
    print_table_row('', section_name, '', None, '', None)


def print_table_header() -> None:
    file_str.write("\n| Project | Section | Order | Priority | Description | Label |")
    file_str.write("\n| ----------- | ----------- | ----------- | ----------- | ----------- | ----------- |\n")


def print_table_row(project: str, section: str, order: str, priority: Optional[int], desc: str, label: Optional[str]) \
        -> None:
    file_str.write(f"| {project} | {section} | {order} | {priority if priority is not None else ''} | {desc} | "
                   f"{label if label is not None else ''} |\n")


def print_items(items: List[dict], section_name: Optional[str], level: int, labels: Dict[int, str]):
    item_ids = [i['id'] for i in items]
    top_level_items = [i for i in items if i['parent_id'] not in item_ids]
    child_items = {pi_id: list(grouper) for pi_id, grouper in
                   groupby(sorted([i for i in items if i['parent_id'] in item_ids],
                                  key=lambda i: i['parent_id']), key=lambda i: i['parent_id'])}

    if section_name is not None:
        print_section(section_name)

    # if level == 0:
    #     print_table_header()

    n = 0
    for item in sorted(top_level_items, key=lambda i: (-i['priority'], -i['child_order'])):
        n += 1
        priority = None if item['priority'] == 1 else 5 - item['priority']
        label = "" if len(item['labels']) == 0 \
            else (" - " + ", ".join([labels[label_id] for label_id in item['labels']]))

        indent = ("&nbsp;&nbsp;&nbsp;&nbsp;" * level)
        order = str(n) if level % 2 == 0 else chr(ord('`') + n)  # '@'
        print_table_row('', '', indent + order, priority, indent + item['content'].replace("|", "&vert;"), label)

        if item['id'] in child_items:
            print_items(child_items[item['id']], None, level + 1, labels)


def print_joplin_project_tasks(project: Union[Tag, Project], project_name: Optional[str], level: int):
    if project['title'] != 'Inbox':
        notes = get_notes_with_tag(project)
    else:
        notes = get_notes_in_notebook(project)

    notes = [note for note in notes if not note['is_todo']]

    if len(notes) > 0:
        if level > 0:
            print_section(f"{project_name} (Joplin)")
        else:
            print_project(0, f"{project_name[1:]} (Joplin)")

        for note in notes:
            print_table_row('', '', '--', None, note['title'], '')


def print_todoist_project_tasks(projects: List[Project], level: int, todoist_child_projects: Dict[int, List[Project]],
                                joplin_projects: List[Tag], labels: Dict[int, str]):
    for project in sorted(projects, key=lambda p: p['child_order']):
        child_projects = todoist_child_projects[project['id']] if project['id'] in todoist_child_projects else None
        joplin_project = next((p for p in joplin_projects if p['title'].lower() == project['name'].lower() or
                               p['title'][1:].lower() == project['name'].lower()), None)

        items = [i for i in get_project_tasks(project) if not i.is_completed and i.due is None]

        if len(items) == 0 and child_projects is None and joplin_project is None:
            continue

        print_project(level, project['name'])

        section_items = {s_id: list(grouper) for s_id, grouper in
                         groupby(sorted(items, key=lambda i: i['section_id'] if i['section_id'] is not None else -1),
                                 key=lambda i: i['section_id'] if i['section_id'] is not None else -1)}

        relevant_sections = [s for s in get_project_sections(project) if s.name != 'Scheduled']

        if -1 in section_items:
            print_items(section_items[-1], None, 0, labels)

        for section in sorted(relevant_sections, key=lambda s: s['section_order']):
            if section['id'] in section_items:
                print_items(section_items[section['id']], section['name'], 0, labels)

        if child_projects:
            print_todoist_project_tasks(child_projects, level + 1, todoist_child_projects, joplin_projects, labels)

        if joplin_project is not None:
            joplin_projects.remove(joplin_project)
            print_joplin_project_tasks(joplin_project, project['name'], level + 1)

        # file_str.write('\n')


def generate_task_list():
    todoist_projects = get_todoist_projects()
    todoist_top_level_projects = [p for p in todoist_projects if p.parent_id is None]
    todoist_child_projects = {p_id: list(grouper) for p_id, grouper in
                              groupby(sorted([p for p in todoist_projects if p.parent_id is not None],
                                             key=lambda p: p['parent_id']), key=lambda p: p['parent_id'])}
    joplin_projects = get_active_projects()
    joplin_projects.append(get_default_notebook())

    labels = {label.id: label.name for label in get_labels()}

    print_table_header()

    print_todoist_project_tasks(todoist_top_level_projects, 0, todoist_child_projects, joplin_projects, labels)

    for joplin_project in joplin_projects:
        print_joplin_project_tasks(joplin_project, joplin_project['title'], 0)
        # file_str.write('\n')


if __name__ == '__main__':
    generate_task_list()

    # with open("task_list.md", mode="w") as md_file:
    #     md_file.write(file_str.getvalue())

    html = markdown.markdown(file_str.getvalue(), extensions=['tables'])
    html = f"""\
        <html>
          <head></head>
          <body>
            {html}
          </body>
        </html>
        """

    # with open("task_list.html", mode="w") as html_file:
    #     html_file.write(html)

    pdfkit.from_string(html, 'task_list.pdf')

    msg = MIMEMultipart('alternative')
    part = MIMEText(html, 'html')
    msg.attach(part)

    part = MIMEBase('application', 'octet-stream')
    part.set_payload((open('task_list.pdf', "rb")).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', "attachment; filename= %s" % 'task_list.pdf')
    msg.attach(part)

    msg['Subject'] = 'Task List'
    send_mail(msg, mail_configs['smtp']['username'])

    os.remove('task_list.pdf')
