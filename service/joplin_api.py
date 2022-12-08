import json
import os
import tempfile
from typing import TypedDict, List, Optional, IO, Dict

import requests

from configuration import joplin_configs
from constants import PNG_MIME_TYPE, PDF_MIME_TYPE
from enums import MimeType
from utils.file import get_title_from_filename, get_tags_from_filename, get_last_modified_time_from_filename
from utils.mail import determine_mime_type
from utils.ocr import get_image_full_text
from utils.pdf import get_pdf_full_text

ITEMS_KEY = 'items'
HAS_MORE_KEY = 'has_more'

BASE_URL = f"http://localhost:{joplin_configs['api-port']}"

NOTE_FIELDS = "id,parent_id,title,body,source_url,is_todo,todo_due"

NOTES_API_URL = f"{BASE_URL}/notes"
NOTES_NOTE_API_URL = NOTES_API_URL + "/{note_id}"
NOTES_TAGS_API_URL = NOTES_NOTE_API_URL + "/tags"
NOTES_RESOURCES_API_URL = NOTES_NOTE_API_URL + "/resources?fields=id,title,mime,filename,file_extension,size"

FOLDERS_API_URL = f"{BASE_URL}/folders"
FOLDERS_NOTES_API_URL = FOLDERS_API_URL + "/{notebook_id}/notes?fields=" + NOTE_FIELDS

TAGS_API_URL = f"{BASE_URL}/tags"
TAG_API_URL = TAGS_API_URL + "/{tag_id}"
TAG_NOTE_API_URL = TAG_API_URL + "/notes?fields=" + NOTE_FIELDS
TAG_REMOVE_FROM_NOTE_API_URL = TAG_API_URL + "/notes/{note_id}"

RESOURCES_API_URL = f"{BASE_URL}/resources"
RESOURCES_RESOURCE_API_URL = RESOURCES_API_URL + "/{resource_id}"
RESOURCES_RESOURCE_FILE_API_URL = RESOURCES_RESOURCE_API_URL + "/file"


# Types
# note 	1
# folder 	2
# setting 	3
# resource 	4
# tag 	5
# note_tag 	6
# search 	7
# alarm 	8
# master_key 	9
# item_change 	10
# note_resource 	11
# resource_local_state 	12
# revision 	13
# migration 	14
# smart_filter 	15
# command 	16

class Notebook(TypedDict):
    id: str
    parent_id: str
    title: str


class Tag(TypedDict):
    id: str
    parent_id: str
    title: str


class Note(TypedDict):
    id: str
    parent_id: str
    title: str
    body: str
    source_url: str
    is_todo: int
    todo_due: int


class Resource(TypedDict):
    id: str
    title: str
    mime: str
    filename: str
    created_time: int
    updated_time: int
    # When the resource was created. It may differ from created_time as it can be manually set by the user.
    user_created_time: int
    # When the resource was last updated. It may differ from updated_time as it can be manually set by the user.
    user_updated_time: int
    file_extension: str
    encryption_cipher_text: str
    encryption_applied: int
    encryption_blob_encrypted: int
    size: int
    is_shared: int
    share_id: str
    master_key_id: str


def get_default_params():
    return {'token': joplin_configs['api-key'], 'limit': 100}


def get_item(url, params=None):
    if params is None:
        params = get_default_params()

    response = requests.get(url, params=params)
    if response.status_code == 404:
        return None
    elif response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    else:
        try:
            return response.json()
        except ValueError:
            return response.content


def get_items(url, params=None):
    if params is None:
        params = get_default_params()

    page = 1
    has_more = True
    items = []
    while has_more:
        params['page'] = page
        # order_by = updated_time
        # order_dir = ASC
        response = requests.get(url, params=params)
        if response.status_code != requests.codes.ok:
            raise RuntimeError(
                f"Received bad status code ({response.status_code} in get response for {response.request}")

        json_body = response.json()
        has_more = json_body[HAS_MORE_KEY]
        items.extend(json_body[ITEMS_KEY])
        page += 1

    return items


def put_item(url, payload, params=None):
    if params is None:
        params = get_default_params()

    response = requests.put(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in put response for {response.request}")
    return response.json()


def post_item(url, payload, params=None):
    if params is None:
        params = get_default_params()

    response = requests.post(url, json=payload, params=params, timeout=60)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in post response for {response.request}")
    return response.json()


def delete_item(url: str, payload=None, params: dict = None) -> any:
    if params is None:
        params = get_default_params()

    response = requests.delete(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(
            f"Received bad status code ({response.status_code} in delete response for {response.request}")
    return response.json() if len(response.content) > 0 else None


def update_item(url, payload, params=None):
    if params is None:
        params = get_default_params()

    response = requests.put(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    return response.json()


def create_notebook(notebook_name):
    print(f"Creating notebook {notebook_name}")
    body = {'title': notebook_name}
    notebook = post_item(FOLDERS_API_URL, body)
    return notebook


def create_new_note(title: str, body: str, notebook_id: Optional[int] = None, is_html: bool = False, creation_time=None,
                    due_date=None) -> Note:
    payload = {'title': title}
    if body is not None and len(body) > 0:
        if is_html:
            payload['body_html'] = body
        else:
            payload['body'] = body

    if notebook_id is None:
        notebook = get_default_notebook()
        notebook_id = notebook['id']
    payload['parent_id'] = notebook_id

    if creation_time is not None:
        payload['user_created_time'] = creation_time

    if due_date is not None:
        payload['is_todo'] = 1
        payload['todo_due'] = due_date

    note = post_item(NOTES_API_URL, payload)
    return note


def get_active_projects() -> List[Tag]:
    return [t for t in get_tags() if len(t['title']) > 1 and t['title'][0] == '#' and t['title'][1] != '#']


def get_inactive_projects() -> List[Tag]:
    return [t for t in get_tags() if len(t['title']) > 2 and t['title'][0] == '#' and t['title'][1] == '#']


def get_tags() -> List[Tag]:
    tags = get_items(TAGS_API_URL)
    return tags


def create_tag(tag_name: str) -> Tag:
    tag = post_item(TAGS_API_URL, {'title': tag_name})
    return tag


def delete_tag(tag: Tag):
    out = delete_item(TAG_API_URL.format(tag_id=tag['id']))
    return out


def add_note_tag(note: Note, tag: Tag) -> None:
    tag_id = tag['id']
    print(f"   Adding tag '{tag['title']} to note {note['title']}'")
    post_item(TAG_NOTE_API_URL.format(tag_id=tag_id), {'id': note['id']})


def add_note_tags(note: Note, tags: List[str]) -> None:
    if len(tags) > 0:
        existing_tags = get_tags()
        for tag in tags:
            tag_lower = tag.lower()
            existing_tag = next((t for t in existing_tags if t['title'].lower() == tag_lower), None)
            if existing_tag is None:
                print(f"Tag {tag} does not exist, creating....")
                tag_id = create_tag(tag)['id']
            else:
                tag_id = existing_tag['id']

            print(f"   Adding tag '{tag} to note {note['title']}'")
            post_item(TAG_NOTE_API_URL.format(tag_id=tag_id), {'id': note['id']})


def remove_note_tag(note: Note, tag: Tag) -> None:
    delete_item(TAG_REMOVE_FROM_NOTE_API_URL.format(tag_id=tag['id'], note_id=note['id']))


def add_generic_attachment(note: Note, file_name: str, file_like: IO) -> Resource:
    resource = add_resource(file_name, file_like)
    append_to_note(note, f"[{file_name}](:/{resource['id']})")
    return resource


def add_resource(file_name: str, file_like: IO, mime_type: str = None) -> Resource:
    file_parts = file_name.split('.')
    ext = file_parts[1] if len(file_parts) > 1 else None
    payload = {'title': file_name, 'filename': file_name, 'file_extension': ext}
    if mime_type:
        payload['mime'] = mime_type

    data = [('props', json.dumps(payload))]
    response = requests.post(RESOURCES_API_URL, data=data, files={'data': file_like}, params=get_default_params())
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    resource = response.json()
    return resource


def delete_note(note):
    delete_item(NOTES_NOTE_API_URL.format(note_id=note['id']))


def attach_text_to_note(note: Note, file_like: IO, is_html: bool = False) -> None:
    text = file_like.read()
    if is_html:
        # Create temporary note to convert html to md consistently
        tmp_note = create_new_note("Temp", text, is_html=is_html)
        text = tmp_note['body']
        delete_note(tmp_note)

    append_to_note(note, text)


def get_note_body(note: Note) -> Optional[str]:
    params = get_default_params()
    params['fields'] = 'body'
    note = get_item(NOTES_NOTE_API_URL.format(note_id=note['id']), params=params)
    return note['body'] if note and 'body' in note else None


def add_pdf_thumbnail(pdf_file_like: IO) -> Optional[Resource]:
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/tmp.pdf", mode="wb") as f:
            f.write(pdf_file_like.read())

        cmd = f"pdftoppm -scale-to 300 -singlefile -png '{tmpdir}/tmp.pdf' '{tmpdir}/thumb'"
        ret = os.system(cmd)
        os.remove(f"{tmpdir}/tmp.pdf")
        if ret != 0:
            print(f"Error executing command '{cmd}'")
            return None
        else:
            file_name = f"{tmpdir}/thumb.png"
            with open(file_name, 'rb') as f:
                resource = add_resource('thumb.png', f, mime_type=PNG_MIME_TYPE)

            os.remove(file_name)
            return resource


def set_note_body(note: Note, body: str) -> None:
    update_item(NOTES_NOTE_API_URL.format(note_id=note['id']), {'body': body})


def append_to_note(note: Note, text: str) -> None:
    if not text:
        return

    if isinstance(text, bytes):
        text = text.decode('utf-8')

    if len(text.strip()) == 0:
        return

    orig_body = get_note_body(note)
    if orig_body is not None and len(orig_body.strip()) > 0:
        orig_body += '\n\n---\n\n'
    orig_body += text
    set_note_body(note, orig_body)


def add_pdf_attachment(note: Note, file_name: str, file_like: IO) -> None:
    thumbnail = add_pdf_thumbnail(file_like)
    file_like.seek(0)
    resource = add_resource(file_name, file_like, PDF_MIME_TYPE)
    file_like.seek(0)
    pdf_text = get_pdf_full_text(file_like)

    if thumbnail is None:
        append_to_note(note, f"[{file_name}](:/{resource['id']})\n\n{pdf_text}")
    else:
        append_to_note(note, f"[![{file_name}](:/{thumbnail['id']})](:/{resource['id']})\n\n{pdf_text}")


def add_img_attachment(note: Note, file_name: str, file_like: IO) -> None:
    resource = add_resource(file_name, file_like)
    body = f"![{file_name}](:/{resource['id']})"
    file_like.seek(0)
    img_text = get_image_full_text(file_like)
    if len(img_text.strip()) != 0:
        body += f"\n\n{img_text}"
    append_to_note(note, body)


def add_attachment(note: Note, file_name: str, file_like: IO, mime_type: MimeType):
    if mime_type == MimeType.TEXT:
        attach_text_to_note(note, file_like, False)
    elif mime_type == MimeType.HTML:
        attach_text_to_note(note, file_like, True)
    elif mime_type == MimeType.PDF:
        add_pdf_attachment(note, file_name, file_like)
    elif mime_type == MimeType.IMG:
        add_img_attachment(note, file_name, file_like)
    elif mime_type == MimeType.OTHER:
        add_generic_attachment(note, file_name, file_like)
    else:
        print(f"Unhandled file type {mime_type}")


def get_notebooks():
    folders = get_items(FOLDERS_API_URL)
    return folders


def get_default_notebook():
    notebook = get_notebook(joplin_configs['default-notebook'])
    if notebook is None:
        print(f"Warning: default notebook {joplin_configs['default-notebook']} not found - creating automatically")
        notebook = create_notebook(joplin_configs['default-notebook'])

    return notebook


def get_notebook(nb_name, default_on_missing=True, auto_create=joplin_configs['auto-create-notebook']):
    if not nb_name or not nb_name.strip():
        return get_default_notebook() if default_on_missing else None

    nb_name_lower = nb_name.lower()
    notebooks = get_notebooks()
    notebook = next((nb for nb in notebooks if nb['title'].lower() == nb_name_lower), None)
    if notebook is None:
        if auto_create:
            notebook = create_notebook(nb_name)
        elif default_on_missing:
            notebook = get_default_notebook()
        else:
            return None

    return notebook


def get_tag(tag_name, auto_create=joplin_configs['auto-create-tag']):
    if not tag_name or not tag_name.strip():
        return None

    tag_name_lower = tag_name.lower()
    tags = get_tags()
    tag = next((tag for tag in tags if tag['title'].lower() == tag_name_lower), None)
    if tag is None:
        if auto_create:
            tag = create_tag(tag_name)
        else:
            return None

    return tag


def add_new_note_from_file(file):
    file_name = os.path.basename(file)
    if file_name.startswith('.'):
        print(f"Ignoring hidden file {file_name}")
        return False

    title = get_title_from_filename(file_name)
    tags = get_tags_from_filename(file_name)
    creation_time = get_last_modified_time_from_filename(file)

    note = create_new_note(title, "", creation_time=creation_time)

    add_note_tags(note, tags)

    import mimetypes
    content_type = mimetypes.MimeTypes().guess_type(file)[0]
    file_type = determine_mime_type(file_name, content_type)
    with open(file, "rb") as f:
        add_attachment(note, file_name, f, file_type)


def sync():
    pass  # TODO


def get_notes_in_notebook(notebook: Notebook) -> List[Note]:
    if not notebook:
        return []

    notes = get_items(FOLDERS_NOTES_API_URL.format(notebook_id=notebook['id']))
    return notes


def get_notes_with_tag(tag: Tag) -> List[Note]:
    if not tag:
        return []

    notes = get_items(TAG_NOTE_API_URL.format(tag_id=tag['id']))
    return notes


def get_note_tags(note: Note) -> List[Tag]:
    tags = get_items(NOTES_TAGS_API_URL.format(note_id=note['id']))
    return tags


def get_note_resources(note: Note) -> List[Resource]:
    resources = get_items(NOTES_RESOURCES_API_URL.format(note_id=note['id']))
    return resources


def get_resource(resource_id: str) -> Resource:
    resource = get_item(RESOURCES_RESOURCE_API_URL.format(resource_id=resource_id))
    return resource


def get_resource_file(resource_id):
    return get_item(RESOURCES_RESOURCE_FILE_API_URL.format(resource_id=resource_id))


def move_note(note, nb_name):
    notebook = get_notebook(nb_name, default_on_missing=False, auto_create=True)
    if not notebook:
        print(f"No notebook found with name {nb_name}")
        return

    if note['parent_id'] == notebook['id']:
        print(f"Note '{note['title']} is already in notebook {nb_name}")
        return

    updated_note = put_item(NOTES_NOTE_API_URL.format(note_id=note['id']), {'parent_id': notebook['id']})
    return updated_note


def tag_note(note, tag_name):
    tag = get_tag(tag_name, auto_create=True)
    if not tag:
        print(f"No tag found with name {tag_name}")
        return

    note_tag_relation = post_item(TAG_NOTE_API_URL.format(tag_id=tag['id']), {'id': note['id']})
    return note_tag_relation


def handle_processed_note(note):
    if 'delete-processed' in joplin_configs and joplin_configs['delete-processed']:
        print(" Deleting note")
        delete_note(note)
    elif 'processed-tag' in joplin_configs and len(joplin_configs['processed-tag'].strip()) > 0:
        print(" Tagging note as processed")
        tag_note(note, joplin_configs['processed-tag'])
    else:
        raise RuntimeError("Missing Joplin config processed-tag and delete-processed is missing or false")


def is_processed(note):
    processed_tag_name = joplin_configs['processed-tag'].lower()
    processed_tag = next((tag for tag in get_note_tags(note) if tag['title'].lower() == processed_tag_name), None)
    return True if processed_tag else False
