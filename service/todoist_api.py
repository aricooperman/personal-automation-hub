import re
from io import BytesIO
from typing import Optional

import markdown
import requests
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Project, Label, Task, Comment, Section

from configuration import todoist_configs

token = todoist_configs['api-key']
api = TodoistAPI(token)


def get_all_projects() -> list[Project]:
    return api.get_projects()


def get_active_projects() -> list[Project]:
    return [proj for proj in get_all_projects() if proj.name[0] != '.']


def get_project(project_id: str) -> Project:
    return api.get_project(project_id)


def create_project(proj_name: str) -> Project:
    return api.add_project(proj_name)


def get_project_sections(project: Project) -> list[Section]:
    return api.get_sections(project_id=project.id)


def get_project_tasks(project: Project) -> list[Task]:
    return api.get_tasks(project_id=project.id)


def get_labels() -> list[Label]:
    return api.get_labels()


def get_label(label_name: str) -> Optional[Label]:
    if not label_name or len(label_name.strip()) == 0:
        return None

    label_name_lower = label_name.lower()
    return next((label for label in get_labels() if label.name.lower() == label_name_lower), None)


def get_tasks_with_label(label: Label) -> list[Task]:
    return api.get_tasks(label=label.name)


def add_task(content: str, due: str = None, labels: list[str] = None, project: Project = None):
    project_id = project.id if project else None
    return api.add_task(content, due_datetime=due, labels=labels, project_id=project_id)


def complete_task(task: Task) -> None:
    if not task.is_completed:
        api.close_task(task.id)


def get_task_comments(task: Task) -> list[Comment]:
    return api.get_comments(task_id=task.id)


def get_task(item_id: str) -> Task:
    return api.get_task(item_id)


def add_file_comment(task: Task, file_bytes, file_name: str, file_type) -> Comment:
    data = {"token": token, 'file_name': file_name, 'file_type': file_type}
    url = "https://api.todoist.com/sync/v9/uploads/add"
    with BytesIO(file_bytes) as file_data:
        response = requests.post(url, data=data, files={"file": file_data}, headers={"Authorization": f"Bearer {token}"})
        if response.status_code != requests.codes.ok:
            raise RuntimeError(
                f"Received bad status code ({response.status_code} in post response for {response.request}")
        file_upload = response.json()
        content = file_name if file_name else "no_name"
        return api.add_comment(task_id=task.id, content=content, attachment=file_upload)


def add_comment(task: Task, comment: str) -> Comment:
    if re.search("\\| ---+ \\|", comment) is not None:
        html = markdown.markdown(comment, extensions=['tables'])
        comment = f"<html><head></head><body>{html}</body></html>"
        return add_file_comment(task, bytes(comment, 'utf-8'), "note.html", "text/html")
    else:
        # comment = re.sub(r'!?\[.*\]\(:/[a-f0-9]+\)', '', comment).strip()
        comment = comment if len(comment) <= 15000 else comment[0:14997] + '...'
        return api.add_comment(comment, task_id=task.id)

# def get_file_comment(comment_id: str, last_id: str = None):
#     uploads = api.uploads.get(limit=50, last_id=last_id)
#     for upload in uploads:
#         if upload['note_id'] == comment_id:
#             return upload
#
#     if len(uploads) == 50:
#         return get_file_comment(comment_id, uploads[-1]['id'])
#
#     return None
