import os.path
from io import BytesIO
from typing import Optional, List, IO, BinaryIO

import html2text

from configuration import obsidian_configs
from enums import MimeType
from utils.ocr import get_image_full_text
from utils.pdf import get_pdf_full_text

H2T = html2text.HTML2Text()


def create_new_note(name: str, body: str, path: Optional[str] = None, is_html: bool = False, tags: Optional[List[str]] = None) -> (str, str):
    if is_html:
        body = H2T.handle(body)

    if path is None:
        path = get_default_notebook()

    if tags is not None and len(tags) > 0:
        body += "\n\n---\n\n"
        for tag in tags:
            body += f"#{tag.lower()}\n\n"

    filename = f"{name}.md"
    file_path = to_vault_path(path, filename)
    for i in range(1, 10):
        if not os.path.exists(file_path):
            break
        filename = f"{name}-{i}.md"
        file_path = to_vault_path(path, filename)

    try:
        with open(file_path, 'x') as file:
            file.write(body)
    except FileExistsError:
        print(f"File {path}/{name} already exists.")

    return path, filename


# def get_active_projects() -> List[Notebook]:
#     active_project = get_notebook(".Active")
#     if active_project is None:
#         return []
#     return [notebook for notebook in get_notebooks() if notebook['parent_id'] == active_project['id']]
#
#
# def get_inactive_projects() -> List[Notebook]:
#     return [t for t in get_tags() if len(t['title']) > 2 and t['title'][0] == '#' and t['title'][1] == '#']
#
#
# def get_tags() -> List[Tag]:
#     tags = get_items(TAGS_API_URL)
#     return tags
#
#
# def create_tag(tag_name: str) -> Tag:
#     tag = post_item(TAGS_API_URL, {'title': tag_name})
#     return tag
#
#
# def delete_tag(tag: Tag):
#     out = delete_item(TAG_API_URL.format(tag_id=tag['id']))
#     return out
#
#
# def add_note_tag(note: Note, tag: Tag) -> None:
#     tag_id = tag['id']
#     print(f"   Adding tag '{tag['title']} to note {note['title']}'")
#     post_item(TAG_NOTE_API_URL.format(tag_id=tag_id), {'id': note['id']})
#
#
# def add_note_tags(note: Note, tags: List[str]) -> None:
#     if len(tags) > 0:
#         existing_tags = get_tags()
#         for tag in tags:
#             tag_lower = tag.lower()
#             existing_tag = next((t for t in existing_tags if t['title'].lower() == tag_lower), None)
#             if existing_tag is None:
#                 print(f"Tag {tag} does not exist, creating....")
#                 tag_id = create_tag(tag)['id']
#             else:
#                 tag_id = existing_tag['id']
#
#             print(f"   Adding tag '{tag} to note {note['title']}'")
#             post_item(TAG_NOTE_API_URL.format(tag_id=tag_id), {'id': note['id']})
#
#
# def remove_note_tag(note: Note, tag: Tag) -> None:
#     delete_item(TAG_REMOVE_FROM_NOTE_API_URL.format(tag_id=tag['id'], note_id=note['id']))


def add_generic_attachment(path: str, filename: str, attachment_name: str, file_like: IO):
    add_resource(path, attachment_name, file_like)
    append_to_note(path, filename, f"![[{attachment_name}]]")


def add_resource(path: str, file_name: str, file_like: IO):
    vault_path = to_vault_path(path, file_name)

    mode = "wb" if isinstance(file_like, BytesIO) else "w"
    with open(vault_path, mode) as file:
        file.write(file_like.read())


# def delete_note(note):
#     delete_item(NOTES_NOTE_API_URL.format(note_id=note['id']))


def attach_text_to_note(path: str, filename: str, file_like: IO, is_html: bool = False) -> None:
    text = file_like.read()
    if is_html:
        text = H2T.handle(text)

    append_to_note(path, filename, text)


def to_vault_path(path: str, filename: str) -> str:
    return f"{obsidian_configs['vault-path']}/{path}/{filename}"


def append_to_note(path: str, filename: str, body: str) -> None:
    if not body:
        return

    if isinstance(body, bytes):
        body = body.decode('utf-8')

    if len(body.strip()) == 0:
        return

    vault_file_path = to_vault_path(path, filename)

    if os.path.exists(vault_file_path):
        body = f"\n\n---\n\n{body}"

    with open(vault_file_path, 'a') as file:
        file.write(body)


def add_pdf_attachment(path: str, filename: str, attachment_name: str, file_like: IO) -> None:
    add_resource(path, attachment_name, file_like)
    file_like.seek(0)
    pdf_text = get_pdf_full_text(file_like)
    append_to_note(path, filename, f"![[{attachment_name}]]\n\n{pdf_text}")


def add_img_attachment(path: str, filename: str, attachment_name: str, file_like: IO) -> None:
    if attachment_name.startswith("image"):
        attachment_name = f"{filename[:-3]}{attachment_name[5:]}"

    add_resource(path, attachment_name, file_like)
    file_like.seek(0)
    body = f"![[{attachment_name}]]"
    img_text = get_image_full_text(file_like)
    if len(img_text.strip()) != 0:
        body += f"\n\n{img_text}"
    append_to_note(path, filename, body)


def add_attachment(path: str, filename: str, attachment_name: str, file_like: IO, mime_type: MimeType) -> None:
    if mime_type == MimeType.TEXT:
        attach_text_to_note(path, filename, file_like, False)
    elif mime_type == MimeType.HTML:
        attach_text_to_note(path, filename, file_like, True)
    elif mime_type == MimeType.PDF:
        add_pdf_attachment(path, filename, attachment_name, file_like)
    elif mime_type == MimeType.IMG:
        add_img_attachment(path, filename, attachment_name, file_like)
    else:
        add_generic_attachment(path, filename, attachment_name, file_like)


# def get_notebooks():
#     folders = get_items(FOLDERS_API_URL)
#     return folders
#

def get_default_notebook():
    notebook = obsidian_configs['default-notebook']
    if notebook is None:
        print(f"Warning: default notebook not configured, using 'Inbox'")
        notebook = 'Inbox'

    return notebook


# def get_tag(tag_name, auto_create=joplin_configs['auto-create-tag']):
#     if not tag_name or not tag_name.strip():
#         return None
#
#     tag_name_lower = tag_name.lower()
#     tags = get_tags()
#     tag = next((tag for tag in tags if tag['title'].lower() == tag_name_lower), None)
#     if tag is None:
#         if auto_create:
#             tag = create_tag(tag_name)
#         else:
#             return None
#
#     return tag
#
#
# def add_new_note_from_file(file):
#     file_name = os.path.basename(file)
#     if file_name.startswith('.'):
#         print(f"Ignoring hidden file {file_name}")
#         return False
#
#     title = get_title_from_filename(file_name)
#     tags = get_tags_from_filename(file_name)
#     creation_time = get_last_modified_time_from_filename(file)
#
#     note = create_new_note(title, "", creation_time=creation_time)
#
#     add_note_tags(note, tags)
#
#     import mimetypes
#     content_type = mimetypes.MimeTypes().guess_type(file)[0]
#     file_type = determine_mime_type(file_name, content_type)
#     with open(file, "rb") as f:
#         add_attachment(note, file_name, f, file_type)
#
#
# def get_notes_in_notebook(notebook: Notebook) -> List[Note]:
#     if not notebook:
#         return []
#
#     notes = get_items(FOLDERS_NOTES_API_URL.format(notebook_id=notebook['id']))
#     return notes
#
#
# def get_notes_with_tag(tag: Tag) -> List[Note]:
#     if not tag:
#         return []
#
#     notes = get_items(TAG_NOTE_API_URL.format(tag_id=tag['id']))
#     return notes
#
#
# def get_note_tags(note: Note) -> List[Tag]:
#     tags = get_items(NOTES_TAGS_API_URL.format(note_id=note['id']))
#     return tags
#
#
# def get_note_resources(note: Note) -> List[Resource]:
#     resources = get_items(NOTES_RESOURCES_API_URL.format(note_id=note['id']))
#     return resources
#
#
# def get_resource(resource_id: str) -> Resource:
#     resource = get_item(RESOURCES_RESOURCE_API_URL.format(resource_id=resource_id))
#     return resource
#
#
# def get_resource_file(resource_id):
#     return get_item(RESOURCES_RESOURCE_FILE_API_URL.format(resource_id=resource_id))
#
#
# def move_note(note, nb_name):
#     notebook = get_notebook(nb_name, default_on_missing=False, auto_create=True)
#     if not notebook:
#         print(f"No notebook found with name {nb_name}")
#         return
#
#     if note['parent_id'] == notebook['id']:
#         print(f"Note '{note['title']} is already in notebook {nb_name}")
#         return
#
#     updated_note = put_item(NOTES_NOTE_API_URL.format(note_id=note['id']), {'parent_id': notebook['id']})
#     return updated_note
#
#
# def tag_note(note, tag_name):
#     tag = get_tag(tag_name, auto_create=True)
#     if not tag:
#         print(f"No tag found with name {tag_name}")
#         return
#
#     note_tag_relation = post_item(TAG_NOTE_API_URL.format(tag_id=tag['id']), {'id': note['id']})
#     return note_tag_relation
#
#
# def handle_processed_note(note):
#     if 'delete-processed' in joplin_configs and joplin_configs['delete-processed']:
#         print(" Deleting note")
#         delete_note(note)
#     elif 'processed-tag' in joplin_configs and len(joplin_configs['processed-tag'].strip()) > 0:
#         print(" Tagging note as processed")
#         tag_note(note, joplin_configs['processed-tag'])
#     else:
#         raise RuntimeError("Missing Joplin config processed-tag and delete-processed is missing or false")
#
#
# def is_processed(note):
#     processed_tag_name = joplin_configs['processed-tag'].lower()
#     processed_tag = next((tag for tag in get_note_tags(note) if tag['title'].lower() == processed_tag_name), None)
#     return True if processed_tag else False
