from email.message import EmailMessage
from io import StringIO
from itertools import groupby
from typing import Dict, List, Optional

from todoist.models import Project

from joplin.functions import get_active_projects as get_joplin_projects, get_notes_with_tag, Tag
from mail.functions import send_mail
from my_todoist.functions import get_active_projects as get_todoist_projects, get_project_details, get_labels
from configuration import mail_configs

file_str = StringIO()


def print_line(level: int, line: str):
    # print("\t" * level, line)
    file_str.write("\t" * level)
    file_str.write(line)
    file_str.write('\n')


def print_items(items: List[dict], section_name: Optional[str], level: int, labels: Dict[int, str]):
    item_ids = [i['id'] for i in items]
    top_level_items = [i for i in items if i['parent_id'] not in item_ids]
    child_items = {pi_id: list(grouper) for pi_id, grouper in
                   groupby(sorted([i for i in items if i['parent_id'] in item_ids],
                                  key=lambda i: i['parent_id']), key=lambda i: i['parent_id'])}

    if section_name is not None:
        print_line(level, f"# {section_name} #")

    n = 0
    for item in sorted(top_level_items, key=lambda i: (-i['priority'], -i['child_order'])):
        n += 1
        priority = "  " if item['priority'] == 1 else f"p{5 - item['priority']}"
        label = "" if len(item['labels']) == 0 else (" - " + ", ".join([labels[label_id] for label_id in item['labels']]))
        print_line(level, f" {n if n > 9 else ' ' + str(n)} {priority} {item['content']}{label}")
        if item['id'] in child_items:
            print_items(child_items[item['id']], None, level + 2, labels)


def print_joplin_project_tasks(project: Tag, project_name: Optional[str], level: int):
    notes = [note for note in get_notes_with_tag(project) if not note['is_todo']]
    if len(notes) > 0:
        print_line(level, f"~~~ {project_name} ~~~")
        for note in notes:
            print_line(level, f" * {note['title']}")
    else:
        print_line(level, f"!!! Empty Joplin Tag: {project}")


def print_todoist_project_tasks(projects: List[Project], level: int, todoist_child_projects: Dict[int, List[Project]],
                                joplin_projects: List[Tag], labels: Dict[int, str]):
    for proj in sorted(projects, key=lambda p: p['child_order']):
        child_projects = todoist_child_projects[proj['id']] if proj['id'] in todoist_child_projects else None
        joplin_project = next((p for p in joplin_projects if p['title'][1:].lower() == proj['name'].lower()), None)

        proj_details = get_project_details(proj)
        items = [i for i in proj_details['items'] if not i['checked'] and i['due'] is None]

        if len(items) == 0 and child_projects is None and joplin_project is None:
            continue

        print_line(level, f"~~~ {proj['name']} ~~~")

        section_items = {s_id: list(grouper) for s_id, grouper in
                         groupby(sorted(items, key=lambda i: i['section_id'] if i['section_id'] is not None else -1),
                                 key=lambda i: i['section_id'] if i['section_id'] is not None else -1)}

        relevant_sections = [s for s in proj_details['sections'] if
                             s['name'] != 'Scheduled' and not s['is_archived'] and not s['is_deleted']]

        if -1 in section_items:
            print_items(section_items[-1], None, level, labels)

        for section in sorted(relevant_sections, key=lambda s: s['section_order']):
            if section['id'] in section_items:
                print_items(section_items[section['id']], section['name'], level + 2, labels)

        if child_projects:
            print_todoist_project_tasks(child_projects, level + 2, todoist_child_projects, joplin_projects, labels)

        if joplin_project is not None:
            joplin_projects.remove(joplin_project)
            print_joplin_project_tasks(joplin_project, "[Joplin]", level + 2)

        file_str.write('\n')


def generate_task_list():
    todoist_projects = get_todoist_projects()
    todoist_top_level_projects = [p for p in todoist_projects if p['parent_id'] is None]
    todoist_child_projects = {p_id: list(grouper) for p_id, grouper in
                              groupby(sorted([p for p in todoist_projects if p['parent_id'] is not None],
                                             key=lambda p: p['parent_id']), key=lambda p: p['parent_id'])}
    joplin_projects = get_joplin_projects()

    labels = {label['id']: label['name'] for label in get_labels()}

    print_todoist_project_tasks(todoist_top_level_projects, 0, todoist_child_projects, joplin_projects, labels)

    for joplin_project in joplin_projects:
        print_joplin_project_tasks(joplin_project, joplin_project['title'], 0)
        file_str.write('\n')


if __name__ == '__main__':
    generate_task_list()
    # print(file_str.getvalue())
    msg = EmailMessage()
    msg.set_content(file_str.getvalue())
    msg['Subject'] = 'Task List'
    send_mail(msg, mail_configs['smtp']['username'])
