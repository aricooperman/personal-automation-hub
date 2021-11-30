from io import BytesIO
from typing import List, Optional, TypedDict

import todoist
from todoist.models import Project, Label, Item, Note

from configuration import todoist_configs


class ItemDetail(TypedDict):
    item: dict
    notes: list[dict]
    project: dict


api = todoist.TodoistAPI(todoist_configs['api-key'])
api.sync()


def get_all_projects() -> List[Project]:
    return api.state['projects']


def get_active_projects() -> List[Project]:
    return [proj for proj in get_all_projects()
            if proj['name'][0] != '.' and not proj['is_archived'] and not proj['is_deleted']]


def get_project(project_id: int) -> Project:
    return api.projects.get(project_id)['project']


def create_project(proj_name: str) -> Project:
    project = api.projects.add(proj_name)
    api.commit()
    return project


def get_project_details(project_id: int) -> dict:
    return api.projects.get_data(project_id)


def get_labels():
    return api.state['labels']


def get_label(label_name: str) -> Optional[Label]:
    if not label_name or len(label_name.strip()) == 0:
        return None
    label_name_lower = label_name.lower()
    return next((label for label in api.state['labels'] if label['name'].lower() == label_name_lower), None)


def get_items_with_label(label: Label) -> List[Item]:
    return [item for item in api.state['items'] if 'labels' in item and label['id'] in item['labels']]


def add_item(content, comment=None, due=None, labels: List[str] = None, project=None):  # TODO handle string and Label
    if labels is None:
        labels = []

    label_ids = []
    for label in labels:
        todoist_label = get_label(label)
        if todoist_label is not None:
            todoist_label = api.labels.add(label.title().replace(' ', ''), color=41)
        label_ids.append(todoist_label['id'])

    project_id = project['id'] if project else None

    item = api.items.add(content, auto_parse_labels=True, due=due, labels=label_ids, project_id=project_id)

    if comment:
        api.notes.add(item.data['id'], comment if len(comment) <= 15000 else comment[0:14997] + '...')

    api.commit()

    return item.data


def archive_item(item: Item) -> None:
    if not item['checked']:
        item.complete()
    item.archive()
    api.commit()


def get_item_notes(item: Item) -> List[Note]:
    notes = [note for note in api.state['notes'] if note['item_id'] == item['id'] and not note['is_deleted']]
    return notes


def get_item_detail(item_id: int) -> ItemDetail:
    return api.items.get(item_id)


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


def get_file_comment(note_id: int, last_id: int = None):
    uploads = api.uploads.get(limit=50, last_id=last_id)
    for upload in uploads:
        if upload['note_id'] == note_id:
            return upload

    if len(uploads) == 50:
        return get_file_comment(note_id, uploads[-1]['id'])

    return None


# def add_new_task_from_message(msg):
#     # TODO
#     pass
#
#
# def add_new_task_from_file(file):
#     # TODO
#     pass
