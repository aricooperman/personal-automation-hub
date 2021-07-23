import traceback

from configuration import mail_configs
from mail.functions import fetch_mail, send_mail, archive_mail, get_subject


def forward_mail():
    print("Processing Mail Forwarding")

    for account in mail_configs['accounts']:
        print(f" Handling account '{account['name']}'")

        forwarding_map = account['mail-forward']
        for mailbox, email in forwarding_map.items():
            try:
                messages = fetch_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                      account['password'], mailbox)
                for uid, msg in messages.items():
                    try:
                        print(f"  Forwarding '{get_subject(msg)}' in {mailbox} mailbox")
                        send_mail(msg, email)
                        if mail_configs['archive']:
                            print("  Archiving message")
                            archive_mail(account['imap']['server'], account['imap']['port'], account['username'],
                                         account['password'], mailbox, uid,
                                         account['archive-folder'] if 'archive-folder' in account else None)
                    except Exception as e:
                        traceback.print_exc()
                        print(f"Error: Mail '{get_subject(msg)}' could not be forwarded: {str(e)}")

            except Exception as e:
                traceback.print_exc()
                print(f"Error: Problem forwarding emails in {mailbox} mailbox: {str(e)}")


if __name__ == "__main__":
    forward_mail()
