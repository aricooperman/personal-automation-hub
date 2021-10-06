import datetime
import re
from io import BytesIO
import todoist

from configuration import todoist_configs, joplin_configs
from constants import LOCAL_TZ, DEFAULT_TZ
from joplin.functions import get_note_tags, get_note_resources, get_resource_file

FILTERED_TAGS = [joplin_configs['processed-tag'], todoist_configs['joplin-tag']]

api = todoist.TodoistAPI(todoist_configs['api-key'])


def get_projects():
    api.sync()
    return api.state['projects']


def get_labels():
    api.sync()
    return api.state['labels']


def get_label(label_name):
    if not label_name or len(label_name.strip()) == 0:
        return None
    label_name_lower = label_name.lower()
    labels = get_labels()
    label = next((l for l in labels if l['name'].lower() == label_name_lower), None)
    return label


def add_task(content, comment=None, due=None, labels=None, project=None):
    if labels is None:
        labels = []

    label_ids = []
    for label in labels:
        label = get_label(label)
        if not label:
            label = api.labels.add(label.title().replace(' ', ''), color=41)
        label_ids.append(label['id'])

    project_id = project['id'] if project else None

    item = api.items.add(content, auto_parse_labels=True, due=due, labels=label_ids, project_id=project_id)

    if comment:
        api.notes.add(item.data['id'], comment)
    api.commit()

    return item.data


def add_file_comment(task_id, file_bytes, file_name, file_type):
    # api.uploads.add('example.jpg')
    # call directly so we don't have to write file to disk
    data = {"token": api.token, 'file_name': file_name, 'file_type': file_type}
    url = api.get_api_url() + "uploads/add"
    with BytesIO(file_bytes) as file_data:
        files = {"file": file_data}
        response = api.session.post(url, data=data, files=files)
        file_upload = response.json()
        api.notes.add(task_id, '', file_attachment=file_upload)
        api.commit()


def add_joplin_note_as_task(note):
    print(f" Adding task {note['title']}")

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
    labels = [tag['title'] for tag in tags if tag['title'] not in FILTERED_TAGS]
    projects = [label for label in labels if label.startswith('#')]
    labels = list(set(labels) - set(projects))
    project = None
    if len(projects) > 0:
        if len(projects) > 1:
            print(f"  Warning: task {note['title']} has more than one project tag {projects}, using first")
        proj_name = projects[0][1:]
        project = next((proj for proj in get_projects() if proj['name'] == proj_name), None)
        if project is None:
            print(f"  Creating Todoist project '{proj_name}'")
            project = api.projects.add(proj_name)
            api.commit()

    labels.append("Joplin")
    task = add_task(content, comment=comment, due=due, labels=labels, project=project)

    resources = get_note_resources(note)
    for resource in resources:
        file_bytes = get_resource_file(resource['id'])
        add_file_comment(task['id'], file_bytes, resource['title'], resource['mime'])


def add_new_task_from_message(msg):
    # TODO
    pass


def add_new_task_from_file(file):
    # TODO
    pass
