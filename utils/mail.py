import datetime
import email
import imaplib
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import default

from configuration import mail_configs, joplin_configs
from constants import PDF_MIME_TYPE, PNG_MIME_TYPE
from enums import MimeType

UID_PATTERN = re.compile(r'\d+ \(UID (?P<uid>\d+) RFC822.*')
GM_MSGID_PATTERN = re.compile(r'\d+ \(X-GM-MSGID (?P<uid>\d+) RFC822.*')


def send_mail(msg, to_addr):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host=mail_configs['smtp']['server'], port=mail_configs['smtp']['port'],
                          context=context) as server:
        server.login(mail_configs['smtp']['username'], mail_configs['smtp']['password'])
        msg["To"] = to_addr
        server.send_message(msg, mail_configs['smtp']['username'], to_addr)


def get_mail_client(host: str, port: int, username: str, password: str, mailbox: str) -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(host=host, port=port)
    result, data = mail.login(username, password)
    if result != 'OK':
        raise RuntimeError(f"Unable to login to mail server: {result} - {data}")

    result, data = mail.select(mailbox)
    if result != 'OK':
        raise RuntimeError(f"Unable to select mailbox {mailbox}: {result} - {data}")

    return mail


def fetch_mail(host: str, port: int, username: str, password: str, mailbox: str) -> dict[int, EmailMessage]:
    messages = {}

    with get_mail_client(host, port, username, password, mailbox) as mail:
        resp, items = mail.search(None, 'All')
        if resp != 'OK':
            print(f"Failed to list mailbox {mailbox}: {resp} - {items}")
            return messages

        for i in items[0].split():
            # if host == 'imap.gmail.com':
            #     id_pattern = GM_MSGID_PATTERN
            #     fetch_command = '(X-GM-MSGID RFC822)'
            # else:
            id_pattern = UID_PATTERN
            fetch_command = '(UID RFC822)'

            resp, data = mail.fetch(i, fetch_command)
            if resp != 'OK':
                print(f"Failed to retrieve mail #{i} from mailbox {mailbox}: {resp} - {data}")
                continue

            if len(data) < 1 or data[0] is None or not isinstance(data[0], tuple):
                raise RuntimeError("Unexpected mail fetch data: " + ' '.join(map(str, data)))

            data_desc, msg_data = data[0]
            match = id_pattern.match(str(data_desc, 'utf-8'))
            if match is None:
                print(f"Could not parse email UID from {data_desc}")
                continue

            uid = int(match.group('uid'))
            msg = email.message_from_bytes(msg_data, policy=default)
            if isinstance(msg, EmailMessage):
                messages[uid] = msg
            else:
                raise RuntimeError("Received a message that was not type EmailMessage: " + str(msg))

    return messages


def archive_mail(host, port, username, password, mailbox, msg_uid, archive_folder):
    with get_mail_client(host, port, username, password, mailbox) as mail:
        if archive_folder:
            result, data = mail.uid('COPY', msg_uid, archive_folder)
            if result != 'OK':
                print(f"Failed to copy message to mailbox {archive_folder}: {result} - {data}")

        # if host == 'imap.gmail.com':
        #     #  Move it to the [Gmail]/Trash folder.
        #     #  Delete it from the [Gmail]/Trash folder.
        #     result, data = mail.uid('STORE', msg_uid, '+X-GM-LABELS', r"(\Trash)")
        #     if result != 'OK':
        #         print(f"Unable to move GMail email to trash: {result} - {data}")
        #
        #     result, data = mail.select(r"(\Trash)")
        #     if result != 'OK':
        #         print(f"Unable to select mailbox {mailbox}: {result} - {data}")

        result, data = mail.uid('STORE', str(msg_uid), '+FLAGS', r'(\Deleted)')
        if result == 'OK':
            mail.expunge()
        else:
            print(f"Failed to archive email from mailbox {mailbox}: {result} - {data}")


def get_subject(msg):
    subject = msg['subject']
    if not subject:
        return "[Subject Unknown]"

    return subject if len(subject) < 1000 else subject[0:996] + '...'


def get_title_from_subject(s):
    s = re.sub(r"(\s+#[\w\-_]+\s*)", "", s)
    s = re.sub(r"(\s+@[\w\-_]+\s*)", "", s)

    if s and len(s.strip()) > 0:
        return s.strip()
    else:
        title = f"{joplin_configs['default-title-prefix']} - {str(datetime.datetime.now())}"
        print(f"No title found in '{s}', setting to '{title}'")
        return title


def get_tags_from_subject(s):
    s = re.findall(r"\s+(?:#)([\w\-_]+)", s)
    return s


def get_notebook_from_subject(subject: str) -> str:
    subject = re.search(r"\s+@([\w\-_]+)", subject)
    return subject.group(1) if subject else None


def determine_mime_type(filename: str, content_type: str) -> MimeType:
    if filename.endswith(".txt") or filename.endswith(".md") or content_type == "text/plain":
        return MimeType.TEXT
    elif filename.endswith(".html") or filename.endswith(".htm") or content_type == 'text/html':
        return MimeType.HTML
    elif filename.endswith(".pdf") or content_type == PDF_MIME_TYPE:
        return MimeType.PDF
    elif filename.endswith(".jpg") or filename.endswith(".jpeg") or content_type == "image/jpeg" \
            or filename.endswith(".png") or content_type == PNG_MIME_TYPE \
            or filename.endswith(".gif") or content_type == "image/gif":
        return MimeType.IMG
    else:
        # print(f"Unhandled attachment content type: {content_type}")
        return MimeType.OTHER


def get_email_body(msg: EmailMessage) -> (str, str):
    body_part = msg.get_body(preferencelist=('html', 'plain', 'related'))
    content_type = body_part.get_content_type()
    body_content = body_part.get_content()
    return body_content, content_type
