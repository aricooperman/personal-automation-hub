from io import BytesIO
from typing import List

import todoist
from todoist.models import Project

from configuration import todoist_configs

api = todoist.TodoistAPI(todoist_configs['api-key'])
api.sync()


def get_all_projects() -> List[Project]:
    return api.state['projects']


def get_active_projects() -> List[Project]:
    return [proj for proj in get_all_projects()
            if proj['name'][0] != '.' and not proj['is_archived'] and not proj['is_deleted']]


def create_project(proj_name: str) -> Project:
    project = api.projects.add(proj_name)
    api.commit()
    return project


def get_project_details(project: Project) -> any:
    return api.projects.get_data(project['id'])


def get_labels():
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
        api.notes.add(item.data['id'], comment if len(comment) <= 15000 else comment[0:14997] + '...')

    api.commit()

    return item.data


def add_file_comment(task_id, file_bytes, file_name, file_type):
    # with tempfile.TemporaryDirectory() as tmpdir:
    #     with open(f"{tmpdir}/{file_name}", mode="wb") as temp_file:
    #         temp_file.write(file_bytes)
    #         file_upload = api.uploads.add(temp_file.name)
    #         api.notes.add(task_id, '', file_attachment=file_upload)
    #         api.commit()

    # call directly so we don't have to write file to disk
    data = {"token": api.token, 'file_name': file_name, 'file_type': file_type}
    url = api.get_api_url() + "uploads/add"
    with BytesIO(file_bytes) as file_data:
        files = {"file": file_data}
        response = api.session.post(url, data=data, files=files)
        file_upload = response.json()
        api.notes.add(task_id, '', file_attachment=file_upload)
        api.commit()

# def add_new_task_from_message(msg):
#     # TODO
#     pass
#
#
# def add_new_task_from_file(file):
#     # TODO
#     pass
