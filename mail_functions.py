import imaplib
import smtplib, ssl
import email
import re
from email.policy import default
from configuration import mail_configs

UID_PATTERN = re.compile(r'\d+ \(UID (?P<uid>\d+) RFC822.*')


def send_mail(msg, to_addr):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host=mail_configs['smtp']['server'], port=mail_configs['smtp']['port'],
                          context=context) as server:
        server.login(mail_configs['username'], mail_configs['password'])
        server.send_message(msg, mail_configs['username'], to_addr)


def get_mail_client(mailbox):
    mail = imaplib.IMAP4_SSL(host=mail_configs['imap']['server'], port=mail_configs['imap']['port'])
    result, data = mail.login(mail_configs['username'], mail_configs['password'])
    if result != 'OK':
        raise RuntimeError(f"Unable to login to mail server: {result} - {data}")

    result, data = mail.select(mailbox)
    if result != 'OK':
        raise RuntimeError(f"Unable to select mailbox {mailbox}: {result} - {data}")

    return mail


def fetch_mail(mailbox):
    messages = {}

    with get_mail_client(mailbox) as mail:
        resp, items = mail.search(None, 'All')
        if resp != 'OK':
            print(f"Failed to list mailbox {mailbox}: {resp} - {items}")
            return messages

        for i in items[0].split():
            resp, data = mail.fetch(i, '(UID RFC822)')
            if resp != 'OK':
                print(f"Failed to retrieve mail #{i} from mailbox {mailbox}: {resp} - {data}")
                continue

            data_desc, msg_data = data[0]
            # b'1 (UID 2 RFC822 {934635}'
            match = UID_PATTERN.match(str(data_desc, 'utf-8'))
            if match is None:
                print(f"Could not parse email UID from {data_desc}")
                continue

            uid = match.group('uid')
            msg = email.message_from_bytes(msg_data, policy=default)
            messages[uid] = msg

    return messages


def archive_mail(mailbox, msg_uid):
    with get_mail_client(mailbox) as mail:
        result, data = mail.uid('COPY', msg_uid, mail_configs['archive-folder'])
        if result == 'OK':
            result, data = mail.uid('STORE', msg_uid, '+FLAGS', r'(\Deleted)')
            if result == 'OK':
                mail.expunge()
            else:
                print(f"Failed to remove email from mailbox {mail_configs['archive-folder']}: {result} - {data}")
        else:
            print(f"Failed to copy email to archive folder: {result} - {data}")


def get_subject(msg):
    subject = msg['subject']
    return subject if len(subject) < 1000 else subject[0:996] + '...'


def get_title_from_subject(s):
    s = re.sub(r"(#[\w\-_]+\s*)", "", s)
    s = re.sub(r"(@[\w\-_]+\s*)", "", s)
    return s.strip()


def get_tags_from_subject(s):
    s = re.findall(r"(?:#)([\w\-_]+)", s)
    return s


def get_notebook_from_subject(subject: str, default_notebook: str) -> str:
    """

    :rtype: str
    """
    subject = re.search(r"@([\w\-_]+)", subject)
    nb = subject.group(1) if subject is not None else None
    return nb if nb is not None else default_notebook


def determine_mail_part_type(part):
    content_type = part.get_content_type()
    filename = part.get_filename(failobj="")
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