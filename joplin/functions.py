import json
import os
import tempfile
import requests
from io import StringIO, BytesIO

from constants import PNG_MIME_TYPE, PDF_MIME_TYPE
from mail import functions
from file import functions
from configuration import joplin_configs
from enums import MimeType
from mail.functions import determine_mime_type

ITEMS_KEY = 'items'
HAS_MORE_KEY = 'has_more'

BASE_URL = f"http://localhost:{joplin_configs['api-port']}"

NOTES_API_URL = f"{BASE_URL}/notes"
NOTES_NOTE_API_URL = NOTES_API_URL + "/{note_id}"
NOTES_TAGS_API_URL = NOTES_NOTE_API_URL + "/tags"
NOTES_RESOURCES_API_URL = NOTES_NOTE_API_URL + "/resources?fields=id,title,mime,filename,file_extension,size"

FOLDERS_API_URL = f"{BASE_URL}/folders"
FOLDERS_NOTES_API_URL = FOLDERS_API_URL + "/{notebook_id}/notes?fields=id,parent_id,title,body,source_url,is_todo," \
                                          "todo_due "

TAGS_API_URL = f"{BASE_URL}/tags"
TAGS_NOTE_API_URL = TAGS_API_URL + "/{tag_id}/notes"

RESOURCES_API_URL = f"{BASE_URL}/resources"
RESOURCES_RESOURCE_API_URL = RESOURCES_API_URL + "/{resource_id}"
RESOURCES_RESOURCE_FILE_API_URL = RESOURCES_RESOURCE_API_URL + "/file"


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

    response = requests.post(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    return response.json()


def update_item(url, payload, params=None):
    if params is None:
        params = get_default_params()

    response = requests.put(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    return response.json()


def delete_item(url, params=None):
    if params is None:
        params = get_default_params()

    response = requests.delete(url, params=params)
    response.raise_for_status()


def create_notebook(notebook_name):
    print(f"Creating notebook {notebook_name}")
    body = {'title': notebook_name}
    notebook = post_item(FOLDERS_API_URL, body)
    return notebook


def create_new_note(title, body, notebook_id=None, is_html=False, creation_time=None):
    payload = {'title': title}
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

    note = post_item(NOTES_API_URL, payload)
    return note


def get_tags():
    tags = get_items(TAGS_API_URL)
    return tags


def create_tag(tag):
    tag = post_item(TAGS_API_URL, {'title': tag})
    return tag


def add_note_tags(note_id, tags):
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

            print(f"Adding tag '{tag} to note {note_id}'")
            post_item(TAGS_NOTE_API_URL.format(tag_id=tag_id), {'id': note_id})


def get_email_body(msg):
    body_part = msg.get_body()
    content_type = body_part.get_content_type()
    body_content = body_part.get_content()
    return body_content, content_type


def add_generic_attachment(note_id, file_name, file_like):
    resource = add_resource(file_name, file_like)
    append_to_note(note_id, f"[{file_name}](:/{resource['id']})")
    return resource


def add_resource(file_name, file_like, mime_type=None):
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


def attach_text_to_note(note_id, file_like, is_html=False):
    text = file_like.read()
    if is_html:
        # Create temporary note to convert html to md consistently
        note = create_new_note("Temp", text, is_html=is_html)
        text = note['body']
        delete_note(note['id'])

    append_to_note(note_id, text)


def get_note_body(note_id):
    params = get_default_params()
    params['fields'] = 'body'
    note = get_item(NOTES_NOTE_API_URL.format(note_id=note_id), params=params)
    return note['body'] if note and 'body' in note else None


def add_pdf_thumbnail(pdf_file_like):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/tmp.pdf", mode="wb") as f:
            f.write(pdf_file_like.read())

        cmd = f"pdftoppm -scale-to 300 -singlefile -png '{tmpdir}/tmp.pdf' '{tmpdir}/thumb'"
        ret = os.system(cmd)
        if ret != 0:
            print(f"Error executing command '{cmd}'")
        os.remove(f"{tmpdir}/tmp.pdf")

        file_name = f"{tmpdir}/thumb.png"
        with open(file_name, 'rb') as f:
            resource = add_resource('thumb.png', f, mime_type=PNG_MIME_TYPE)

        os.remove(file_name)
        return resource


def set_note_body(note_id, body):
    update_item(NOTES_NOTE_API_URL.format(note_id=note_id), {'body': body})


def append_to_note(note_id, text):
    if not text:
        return

    if isinstance(text, bytes):
        text = text.decode('utf-8')

    if len(text.strip()) == 0:
        return

    orig_body = get_note_body(note_id)
    if orig_body is not None and len(orig_body.strip()) > 0:
        orig_body += '\n\n---\n\n'
    orig_body += text
    set_note_body(note_id, orig_body)


def add_pdf_attachment(note_id, file_name, file_like):
    thumbnail = add_pdf_thumbnail(file_like)
    file_like.seek(0)
    resource = add_resource(file_name, file_like, PDF_MIME_TYPE)
    file_like.seek(0)
    pdf_text = get_pdf_full_text(file_like)
    append_to_note(note_id, f"[![{file_name}](:/{thumbnail['id']})](:/{resource['id']})\n\n{pdf_text}")


def add_img_attachment(note_id, file_name, file_like):
    resource = add_resource(file_name, file_like)
    body = f"![{file_name}](:/{resource['id']})"
    file_like.seek(0)
    img_text = get_image_full_text(file_name, file_like)
    if len(img_text.strip()) != 0:
        body += f"\n\n{img_text}"
    append_to_note(note_id, body)


def add_attachment(note_id, file_name, file_like, mime_type):
    if mime_type == MimeType.TEXT:
        attach_text_to_note(note_id, file_like, False)
    elif mime_type == MimeType.HTML:
        attach_text_to_note(note_id, file_like, True)
    elif mime_type == MimeType.PDF:
        add_pdf_attachment(note_id, file_name, file_like)
    elif mime_type == MimeType.IMG:
        add_img_attachment(note_id, file_name, file_like)
    elif mime_type == MimeType.OTHER:
        add_generic_attachment(note_id, file_name, file_like)
    else:
        print(f"Unhandled file type {mime_type}")


def add_attachments_from_msg_parts(note_id, msg):
    for part in msg.iter_attachments():
        file_name = part.get_filename(failobj="unknown_file_name")
        content_type = part.get_content_type()
        part_type = determine_mime_type(file_name, content_type)
        content = part.get_content()
        if isinstance(content, bytes):
            with BytesIO(content) as f:
                add_attachment(note_id, file_name, f, part_type)
        else:
            with StringIO(content) as f:
                add_attachment(note_id, file_name, f, part_type)


def get_pdf_full_text(pdf_file_like):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/tmp.pdf"
        with open(tmp_file_name, mode="wb") as pdf_file:
            pdf_file.write(pdf_file_like.read())

        pdf_to_text_cmd = f"pdftotext -raw -nopgbrk '{tmp_file_name}' -"
        out_pipe = os.popen(pdf_to_text_cmd, mode="r")
        pdf_text = ""
        lines = out_pipe.readlines()
        for line in lines:
            pdf_text += '> ' + line.replace('>', r'\>')
        os.remove(tmp_file_name)
        return pdf_text


def get_image_full_text(file_name, img_file_like):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/{file_name}"
        with open(tmp_file_name, mode="wb") as img_file:
            img_file.write(img_file_like.read())

        ocr_cmd = f"tesseract -l eng '{tmp_file_name}' -"
        out_pipe = os.popen(ocr_cmd, mode="r")
        img_text = ""
        lines = out_pipe.readlines()
        for line in lines:
            img_text += '> ' + line.replace('>', r'\>')

        os.remove(tmp_file_name)
        return img_text


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


def add_new_note_from_message(msg):
    subject = functions.get_subject(msg)
    title = functions.get_title_from_subject(subject)
    tags = functions.get_tags_from_subject(subject)
    notebook_name = functions.get_notebook_from_subject(subject)
    body, content_type = get_email_body(msg)
    notebook = get_notebook(notebook_name)
    print(f"Creating new note with name '{title}' in '{notebook['title']}'")
    note = create_new_note(title, body, notebook_id=notebook['id'], is_html=(content_type == 'text/html'))
    print(f"New note created - ID is: {note['id']}")
    add_note_tags(note['id'], tags)
    add_attachments_from_msg_parts(note['id'], msg)


def add_new_note_from_file(file):
    print(f"Processing {os.path.abspath(file)}")

    file_name = os.path.basename(file)
    if file_name.startswith('.'):
        print(f"Ignoring hidden file {file_name}")
        return False

    title = functions.get_title_from_filename(file_name)
    tags = functions.get_tags_from_filename(file_name)
    creation_time = functions.get_last_modified_time_from_filename(file)
    notebook = get_default_notebook()

    print(f"Creating new note with name '{file_name}' in '{notebook['title']}'")
    note = create_new_note(title, "", creation_time=creation_time)
    print(f"New note created - ID is: {note['id']}")

    add_note_tags(note['id'], tags)

    import mimetypes
    content_type = mimetypes.MimeTypes().guess_type(file)[0]
    file_type = determine_mime_type(file_name, content_type)
    with open(file, "rb") as f:
        add_attachment(note['id'], file_name, f, file_type)


def sync():
    pass  # TODO


def get_notes(notebook):
    if not notebook:
        return []

    notes = get_items(FOLDERS_NOTES_API_URL.format(notebook_id=notebook['id']))
    return notes


def get_note_tags(note_id):
    tags = get_items(NOTES_TAGS_API_URL.format(note_id=note_id))
    return tags


def get_resources(note_id):
    resources = get_items(NOTES_RESOURCES_API_URL.format(note_id=note_id))
    return resources


def get_resource(resource_id):
    resource = get_item(RESOURCES_RESOURCE_API_URL.format(resource_id=resource_id))
    return resource


def get_resource_file(resource_id):
    file = get_item(RESOURCES_RESOURCE_FILE_API_URL.format(resource_id=resource_id))
    return file


def move_note(note, nb_name):
    notebook = get_notebook(nb_name, default_on_missing=False, auto_create=False)
    if not notebook:
        print(f"No notebook found with name {nb_name}")
        return

    if note['parent_id'] == notebook['id']:
        print(f"Note '{note['title']} is already in notebook {nb_name}")
        return

    updated_note = put_item(NOTES_NOTE_API_URL.format(note_id=note['id']), {'parent_id': notebook['id']})
    return updated_note


def handle_processed_note(note):
    if 'delete-processed' in joplin_configs and joplin_configs['delete-processed']:
        print("Deleting note")
        delete_note(note)
    elif 'archive-notebook' in joplin_configs and len(joplin_configs['archive-notebook'].strip()) > 0:
        print("Archiving note")
        move_note(note, joplin_configs['archive-notebook'])
