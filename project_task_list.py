import os
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
from itertools import groupby
from typing import Dict, List, Optional, Union

import markdown
import pdfkit
from todoist_api_python.models import Project, Task

from constants import LOCAL_TZ, PDF_MIME_TYPE
from service.joplin_api import get_notes_with_tag, Tag, get_active_projects, get_default_notebook, \
    get_notes_in_notebook, Notebook
from utils.mail import send_mail
from service.todoist_api import get_active_projects as get_todoist_projects, get_labels, get_project_tasks, \
    get_project_sections, add_task, add_file_comment
from configuration import mail_configs

file_str = StringIO()


def print_project(level: int, project_name: str) -> None:
    indicator = "*" if level > 0 else "**"
    print_table_row(indicator + project_name + indicator, '', '', None, '', None)


def print_section(section_name):
    print_table_row('', section_name, '', None, '', None)


def print_table_header() -> None:
    file_str.write("\n| Project | Section | Order | Priority | Description | Label |")
    file_str.write("\n|:----------- |:----------- |:----------- |:----------- |:----------- |:----------- |\n")


def print_table_row(project: str, section: str, order: str, priority: Optional[int], desc: str, label: Optional[str]) \
        -> None:
    file_str.write(f"| {project} | {section} | {order} | {priority if priority is not None else ''} | {desc} | "
                   f"{label if label is not None else ''} |\n")


def print_todoist_tasks(tasks: List[Task], section_name: Optional[str], level: int):
    task_ids = [task.id for task in tasks]
    top_level_items = [task for task in tasks if task.parent_id not in task_ids]
    child_items = {pt_id: list(grouper) for pt_id, grouper in
                   groupby(sorted([task for task in tasks if task.parent_id in task_ids],
                                  key=lambda task: task.parent_id), key=lambda task: task.parent_id)}
    remaining_tasks = tasks[:]

    if section_name is not None:
        print_section(section_name)

    n = 0
    for task in sorted(top_level_items, key=lambda task: (-task.priority, -task.order)):
        n += 1
        priority = None if task.priority == 1 else 5 - task.priority
        label = "" if len(task.labels) == 0 else (" - " + ", ".join(task.labels))

        indent = ("&nbsp;&nbsp;&nbsp;&nbsp;" * level)
        if level % 2 == 0:
            order = str(n)
        else:
            i = (n - 1) // 26
            prefix = "" if i == 0 else chr(ord('`') + i)
            order = prefix + chr(ord('`') + (n % 26))  # '@'
        print_table_row('', '', indent + order, priority, indent + task.content.replace("|", "&vert;"), label)
        remaining_tasks.remove(task)

        if task.id in child_items:
            child_items_tasks = child_items[task.id]
            print_todoist_tasks(child_items_tasks, None, level + 1)
            for t in child_items_tasks:
                remaining_tasks.remove(t)

    # if len(remaining_tasks) > 0:
    #     print(remaining_tasks)


def print_joplin_project_tasks(project: Union[Tag, Notebook], project_name: Optional[str], level: int):
    notes = get_notes_in_notebook(project)
    notes = [note for note in notes if not note['is_todo']]

    if len(notes) > 0:
        if level > 0:
            print_section(f"{project_name} (Joplin)")
        else:
            print_project(0, f"{project_name[1:]} (Joplin)")

        for note in notes:
            print_table_row('', '', '--', None, note['title'], '')


def print_todoist_project_tasks(projects: List[Project], level: int, todoist_child_projects: Dict[str, List[Project]],
                                joplin_projects: List[Tag]):
    for project in sorted(projects, key=lambda p: p.order if p.order is not None else 0):
        child_projects = todoist_child_projects[project.id] if project.id in todoist_child_projects else None
        joplin_project = next((p for p in joplin_projects if p['title'].lower() == project.name.lower() or
                               p['title'][1:].lower() == project.name.lower()), None)

        project_tasks = get_project_tasks(project)
        parent_ids = list(map(lambda task: task.parent_id, project_tasks))
        child_counts = dict((x, parent_ids.count(x)) for x in set(parent_ids) if x is not None)
        tasks = [task for task in project_tasks if not task.is_completed and
                 (task.due is None or task.id in child_counts)]

        if len(tasks) == 0 and child_projects is None and joplin_project is None:
            continue

        print_project(level, project.name)

        section_tasks = {s_id: list(grouper) for s_id, grouper in
                         groupby(sorted(tasks, key=lambda task: task.section_id if task.section_id is not None else ""),
                                 key=lambda task: task.section_id if task.section_id is not None else "")}

        relevant_sections = [s for s in get_project_sections(project) if s.name != 'Scheduled']

        if "" in section_tasks:
            print_todoist_tasks(section_tasks[""], None, 0)

        for section in sorted(relevant_sections, key=lambda sec: sec.order):
            if section.id in section_tasks:
                print_todoist_tasks(section_tasks[section.id], section.name, 0)

        if child_projects:
            print_todoist_project_tasks(child_projects, level + 1, todoist_child_projects, joplin_projects)

        if joplin_project is not None:
            joplin_projects.remove(joplin_project)
            print_joplin_project_tasks(joplin_project, project.name, level + 1)

        # file_str.write('\n')


def generate_task_list():
    todoist_projects = get_todoist_projects()
    todoist_top_level_projects = [p for p in todoist_projects if p.parent_id is None]
    todoist_child_projects = {p_id: list(grouper) for p_id, grouper in
                              groupby(sorted([p for p in todoist_projects if p.parent_id is not None],
                                             key=lambda p: p.parent_id), key=lambda p: p.parent_id)}
    joplin_projects = get_active_projects()
    joplin_projects.append(get_default_notebook())

    print_table_header()

    print_todoist_project_tasks(todoist_top_level_projects, 0, todoist_child_projects, joplin_projects)

    for joplin_project in joplin_projects:
        print_joplin_project_tasks(joplin_project, joplin_project['title'], 0)
        # file_str.write('\n')


def send_email(html_str: str):
    msg = MIMEMultipart('alternative')
    part = MIMEText(html_str, 'html')
    msg.attach(part)
    part = MIMEBase('application', 'octet-stream')
    part.set_payload((open('task_list.pdf', "rb")).read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', "attachment; filename= %s" % 'task_list.pdf')
    msg.attach(part)
    msg['Subject'] = 'Task List'
    send_mail(msg, mail_configs['smtp']['username'])


def add_todoist_task():
    dt = datetime.now()
    due = dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')
    task = add_task("Project List", due=due)
    with open('task_list.pdf', mode="rb") as pdf_file:
        contents = pdf_file.read()
        add_file_comment(task, contents, 'task_list.pdf', PDF_MIME_TYPE)


def print_tasks():
    os.system("lp task_list.pdf")


if __name__ == '__main__':
    generate_task_list()

    # with open("task_list.md", mode="w") as md_file:
    #     md_file.write(file_str.getvalue())

    html = markdown.markdown(file_str.getvalue(), extensions=['tables'])
    html = f"""\
        <html>
          <head>
            <style>
                td, th {{
                   border: 1px solid #000;
                }}
                
                table {{
                    border-collapse: collapse;
                }}
            </style>
          </head>
          <body>
            {html}
          </body>
        </html>
        """

    # with open("task_list.html", mode="w") as html_file:
    #     html_file.write(html)

    pdfkit.from_string(html, 'task_list.pdf')

    # send_email(html)
    # add_todoist_task()
    # print_tasks()

    # os.remove('task_list.pdf')
