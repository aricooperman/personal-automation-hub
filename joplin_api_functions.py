import json
import os
import tempfile
import requests
import datetime
import mail_functions
from configuration import joplin_configs
from mail_functions import determine_mail_part_type

ITEMS_KEY = 'items'
HAS_MORE_KEY = 'has_more'

BASE_URL = f"http://localhost:{joplin_configs['api-port']}"
NOTES_API_URL = f"{BASE_URL}/notes"
NOTE_API_URL = NOTES_API_URL + "/{note_id}"
FOLDERS_API_URL = f"{BASE_URL}/folders"
TAGS_API_URL = f"{BASE_URL}/tags"
NOTE_TAGS_API = TAGS_API_URL + "/{tag_id}/notes"
RESOURCES_API_URL = f"{BASE_URL}/resources"

def get_default_params():
    return {'token': joplin_configs['api-key'], 'limit': 100}


def get_item(url, params):
    response = requests.get(url, params=params)
    if response.status_code == 404:
        return None
    elif response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    else:
        return response.json()


def get_items(url, params=get_default_params()):
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


def post_item(url, payload, params=get_default_params()):
    response = requests.post(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    return response.json()


def update_item(url, payload, params=get_default_params()):
    response = requests.post(url, json=payload, params=params)
    if response.status_code != requests.codes.ok:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")
    return response.json()


def delete_item(url, params=get_default_params()):
    response = requests.delete(url, params=params)
    print(response)


def create_notebook(notebook_name):
    print(f"Creating notebook {notebook_name}")
    body = {'title': notebook_name}
    notebook = post_item(FOLDERS_API_URL, body)
    return notebook


def create_new_note(title, body, notebook_id=None, is_html=False):
    payload = {'title': title}
    if is_html:
        payload['body_html'] = body
    else:
        payload['body'] = body

    if notebook_id is not None:
        payload['parent_id'] = notebook_id

    note = post_item(NOTES_API_URL, payload)
    return note


def get_tags():
    tags = get_items(TAGS_API_URL)
    return tags


def create_tag(tag):
    tag = post_item(TAGS_API_URL, {'title': tag})
    return tag


def set_note_tags(note_id, tags):
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
            post_item(NOTE_TAGS_API.format(tag_id=tag_id), {'id': note_id})


def get_email_body(msg):
    body_part = msg.get_body()
    content_type = body_part.get_content_type()
    body_content = body_part.get_content()
    return body_content, content_type


# def convert_to_markdown(body_content):
#     from markdownify import markdownify as md
#     body_content = md(body_content, heading_style="ATX", strip=["style"])
#     return body_content


def attach_file(note_id, part):
    # file_name = part.get_filename(failobj="unknown")
    # with tempfile.TemporaryDirectory() as tmpdir:
    #     file = f"{tmpdir}/{file_name}"
    #     content = part.get_content()
    #     if isinstance(content, bytes):
    #         mode = "wb"
    #     else:
    #         mode = "w"
    #     with open(file, mode=mode) as f:
    #         f.write(content)
    #
    #     print(f"Attaching file {file_name}")
    #     run_joplin_command("attach", note_id, f"'{file}'")
    #     os.remove(file)
    pass


def delete_note(note_id):
    delete_item(NOTE_API_URL.format(note_id=note_id))


def attach_text_from_file(note_id, part):
    print(f"Adding text from {part.get_filename()}")
    text = part.get_content() # .strip('\0')
    if part.get_content_type() == 'text/html':
        note = create_new_note("Temp", text, is_html=True)
        # text = convert_to_markdown(text)
        text = note['body']
        delete_note(note['id'])

    append_to_note(note_id, text)


def get_note_body(note_id):
    params = get_default_params()
    params['fields'] = 'body'
    note = get_item(NOTE_API_URL.format(note_id=note_id), params=params)
    return note['body'] if note is not None else None


def attach_file_to_note(note_id, file, mime=None):
    files = {'data': open(file, 'rb')}
    file_name = os.path.basename(file)
    # 'file_extension': os.path.splitext(file)
    payload = {'title': file_name, 'filename': file_name}
    if mime is not None:
        payload['mime'] = mime
    data = [('props', json.dump(payload))]
    response = requests.post(RESOURCES_API_URL, data=data, files=files)
    if response.status_code != requests.codes.ok0:
        raise RuntimeError(f"Received bad status code ({response.status_code} in get response for {response.request}")


def add_pdf_thumbnails(note_id, part):
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/tmp.pdf", mode="wb") as pdf_file:
            pdf_file.write(part.get_content())

        cmd = f"pdftoppm -scale-to 300 -singlefile -png '{tmpdir}/tmp.pdf' '{tmpdir}/thumb'"
        ret = os.system(cmd)
        if ret != 0:
            print(f"Error executing command '{cmd}'")
        os.remove(f"{tmpdir}/tmp.pdf")

        file_name = f"{tmpdir}/thumb.png"
        print(f"Adding pdf thumbnail: {file_name}")
        attach_file_to_note(note_id, file_name)
        os.remove(file_name)


def set_note_body(note_id, body):
    update_item(NOTE_API_URL.format(note_id=note_id), {'body': body})


def append_to_note(note_id, text):
    orig_body = get_note_body(note_id)
    if orig_body is not None and len(orig_body.strip()) > 0:
        orig_body += '\n'
    orig_body += text
    set_note_body(note_id, orig_body)


def add_last_image_as_link(note_id):
    print("Adding explicit image link")
    orig_body = get_note_body(note_id)
    orig_body_lines = orig_body.splitlines()
    last_line = ""
    for line in reversed(orig_body_lines):
        if len(line.strip()) > 0:
            last_line = line
            break
    link = last_line[1:1000] if len(last_line) > 999 else last_line[1:]
    append_to_note(note_id, link)


def add_attachment_from_file(note_id, part):
    part_type = determine_mail_part_type(part)
    if part_type == "TXT":
        attach_text_from_file(note_id, part)
    elif part_type == "PDF":
        add_pdf_thumbnails(note_id, part)
        attach_file(note_id, part)
    elif part_type == "IMG":
        attach_file(note_id, part)
        add_last_image_as_link(note_id)
    elif part_type == "UNKNOWN":
        attach_file(note_id, part)
    else:
        print(f"Unhandled file type {part_type}")


def add_attachments_from_file_parts(note_id, msg):
    for part in msg.iter_attachments():
        add_attachment_from_file(note_id, part)


def add_pdf_full_text(note_id, pdf_part):
    filename = pdf_part.get_filename()
    print(f"Adding pdf text for {filename}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/{filename}"
        with open(tmp_file_name, mode="wb") as pdf_file:
            pdf_file.write(pdf_part.get_content())

        pdf_to_text_cmd = f"pdftotext -raw -nopgbrk '{tmp_file_name}' -"
        out_pipe = os.popen(pdf_to_text_cmd, mode="r")
        pdf_text = out_pipe.read()
        os.remove(tmp_file_name)

        append_to_note(note_id, f"\n---\n\n{pdf_text}")


def add_image_full_text(note_id, part):
    filename = part.get_filename()
    print(f"Adding image text for {filename}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/{filename}"
        with open(tmp_file_name, mode="wb") as img_file:
            img_file.write(part.get_content())

        ocr_cmd = f"tesseract -l eng '{tmp_file_name}' -"
        out_pipe = os.popen(ocr_cmd, mode="r")
        img_text = out_pipe.read().strip()
        os.remove(tmp_file_name)

        if len(img_text) != 0:
            append_to_note(note_id, f"\n---\n\n{img_text}")


def add_full_text_from_file(note_id, part):
    part_type = determine_mail_part_type(part)
    if part_type == "PDF":
        add_pdf_full_text(note_id, part)
    elif part_type == "IMG":
        add_image_full_text(note_id, part)
    else:
        pass


def add_full_text_from_file_parts(note_id, msg):
    for part in msg.iter_attachments():
        add_full_text_from_file(note_id, part)


# ---
## Usage: setCreationDate note-id date
# ---
# function setCreationDate {
# 	if [[ "$2" != "" ]]; then
# 		local DATINT=`date -jf "%Y-%m-%d %H.%M.%S" "$2" +%s`
#    		echo "Set creation date $2 (${DATINT}000)"
# 		joplin set "$1" user_created_time ${DATINT}000
# 	fi
# }


def get_notebooks():
    folders = get_items(FOLDERS_API_URL)
    return folders


def get_notebook(nb_name):
    nb_name_lower = nb_name.lower()
    notebooks = get_notebooks()
    notebook = next((nb for nb in notebooks if nb['title'].lower() == nb_name_lower), None)
    return notebook


def add_new_note_from_message(msg):
    subject = mail_functions.get_subject(msg)
    title = mail_functions.get_title_from_subject(subject)
    tags = mail_functions.get_tags_from_subject(subject)
    notebook_name = mail_functions.get_notebook_from_subject(subject, joplin_configs['default-notebook'])
    body, content_type = get_email_body(msg)

    if title is None or len(title) == 0:
        title = f"{joplin_configs['default-title-prefix']} - {str(datetime.datetime.now())}"
        print(f"No title found, setting to '{title}'")

    notebook = get_notebook(notebook_name)
    if notebook is None:
        if joplin_configs['auto-create-notebook']:
            notebook = create_notebook(notebook_name)
        else:
            notebook_name = joplin_configs['default-notebook']
            notebook = get_notebook(notebook_name)
            if notebook is None:
                print(f"Warning: default notebook {notebook_name} not found - creating automatically")
                notebook = create_notebook(notebook_name)

    print(f"Creating new note with name '{subject}' in '{notebook_name}'")
    note = create_new_note(title, body, notebook_id=notebook['id'], is_html=(content_type == 'text/html'))
    print(f"New note created - ID is: {note['id']}")
    set_note_tags(note['id'], tags)

    add_attachments_from_file_parts(note['id'], msg)
    # add_full_text_from_file_parts(note_id, msg)


def sync():
    # run_joplin_command("sync")
    pass
