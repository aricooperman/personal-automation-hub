import os
import json
import datetime
import tempfile
from shlex import quote

import mail_functions
from configuration import joplin_configs


def run_joplin_command(action, *argv):
    params = " ".join(argv)
    cmd = f"joplin {action} {params}"
    ret = os.system(cmd)
    if ret != 0:
        raise RuntimeError(f"Failed to run command {cmd}, return code = {ret}")


def switch_to_notebook(nb, auto_create_notebook=joplin_configs['auto-create-notebook']):
    try:
        run_joplin_command("use", nb)
    except RuntimeError:  # Likely that notebook does not exist
        if auto_create_notebook:
            print(f"Info: notebook {nb} not found - creating automatically")
            run_joplin_command("mkbook", nb)
            run_joplin_command("use", nb)
        else:
            default_notebook = joplin_configs['default-notebook']
            print(f"Warning: notebook {nb} not found - using default notebook {default_notebook} instead")
            try:
                run_joplin_command("use", default_notebook)
            except RuntimeError:
                print(f"Warning: default notebook {default_notebook} not found - creating automatically")
                run_joplin_command("mkbook", default_notebook)
                run_joplin_command("use", default_notebook)


def create_new_note(name):
    run_joplin_command("mknote", f"'{name}'")
    list_cmd = f"joplin ls -s created_time -l -t n -f json '{name}'"
    with os.popen(list_cmd) as output:
        notes = json.load(output)
        if notes is None or len(notes) < 1:
            raise RuntimeError(f"Did not find any notes named {name}")

        notes = sorted(notes, key=lambda k: k['user_created_time'], reverse=True)
        return notes[0]['id']


def set_note_title(note_id, title=None):
    if title is None or len(title) == 0:
        title = joplin_configs['default-title-prefix'] + f" - {str(datetime.datetime.now())}"

    print(f"Setting title to '{title}'")
    run_joplin_command("set", note_id, "title", f"'{title}'")


def set_note_tags(note_id, tags):
    for tag in tags:
        print(f"Adding tag '{tag}'")
        run_joplin_command("tag", "add", f"'{tag}'", note_id)


def determine_mail_part_type(part):
    content_type = part.get_content_type()
    filename = part.get_filename(failobj="")
    # if type =~ ^.*\/textfile[0-9]*$:
    #     return "CONTENT"
    if filename.endswith(".txt") or filename.endswith(".md") or content_type == "text/plain" or \
            filename.endswith(".html") or content_type == 'text/html':
        return "TXT"
    elif filename.endswith(".pdf") or content_type == "application/pdf":
        return "PDF"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg") or content_type == "image/jpeg":
        return "IMG"
    elif filename.endswith(".png") or content_type == "image/png":
        return "IMG"
    elif filename.endswith(".gif") or content_type == "image/gif":
        return "IMG"
    else:
        print(f"Unhandled attachment content type: {content_type}")
        return "UNKNOWN"


def set_note_body(note_id, msg):
    body_part = msg.get_body()
    content_type = body_part.get_content_type()
    body_content = body_part.get_content()
    if content_type == 'text/html':
        body_content = convert_to_markdown(body_content)
    elif content_type != 'text/plain':
        raise RuntimeError(f"Unhandled content type for note body: {content_type} - {body_content}")

    print("Setting body")
    append_to_note(note_id, body_content)


def convert_to_markdown(body_content):
    from markdownify import markdownify as md
    body_content = md(body_content, heading_style="ATX", strip=["style"])
    return body_content


def attach_file(note_id, part):
    file_name = part.get_filename(failobj="unknown")
    with tempfile.TemporaryDirectory() as tmpdir:
        file = f"{tmpdir}/{file_name}"
        content = part.get_content()
        if isinstance(content, bytes):
            mode = "wb"
        else:
            mode = "w"
        with open(file, mode=mode) as f:
            f.write(content)

        print(f"Attaching file {file_name}")
        run_joplin_command("attach", note_id, f"'{file}'")
        os.remove(file)


def attach_text_from_file(note_id, part):
    print(f"Add text from {part.get_filename()}")
    text = part.get_content().strip('\0')
    if part.get_content_type() == 'text/html':
        text = convert_to_markdown(text)

    append_to_note(note_id, text)


def get_note_body(note_id):
    cat_cmd = f"joplin cat {note_id} | tail -n +2"
    with os.popen(cat_cmd) as output:
        orig_body = output.read()
    return orig_body


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
        run_joplin_command("attach", note_id, f"'{file_name}'")
        os.remove(file_name)


def append_to_note(note_id, text):
    orig_body = get_note_body(note_id)
    if len(orig_body.strip()) > 0:
        orig_body += '\n'

    run_joplin_command('set', note_id, 'body', quote(f"{orig_body}{text}"))


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


def add_new_note_from_message(msg):
    subject = mail_functions.get_subject(msg)
    title = mail_functions.get_title_from_subject(subject)
    tags = mail_functions.get_tags_from_subject(subject)
    notebook = mail_functions.get_notebook_from_subject(subject, joplin_configs['default-notebook'])

    switch_to_notebook(notebook, joplin_configs['auto-create-notebook'])
    print(f"Creating new note with name '{subject}' in '{notebook}'")
    note_id = create_new_note(title)
    print(f"New note created - ID is: {note_id}")

    set_note_title(note_id, title)
    set_note_tags(note_id, tags)
    set_note_body(note_id, msg)
    add_attachments_from_file_parts(note_id, msg)
    add_full_text_from_file_parts(note_id, msg)


def sync():
    run_joplin_command("sync")
