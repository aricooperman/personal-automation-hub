import traceback

from configuration import mail_configs
from mail.functions import fetch_mail, send_mail, archive_mail


def forward_mail():
    print("-------------------")
    print("Processing mail forwarding")

    forwarding_map = mail_configs['mail-forward']
    for mailbox, email in forwarding_map.items():
        print(f"Handling {mailbox} mailbox")
        try:
            messages = fetch_mail(mailbox)
            if len(messages) < 1:
                print("Did not find any messages")

            for uid, msg in messages.items():
                try:
                    send_mail(msg, email)
                    if mail_configs['archive']:
                        print("Archiving message")
                        archive_mail(mailbox, uid)
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error: Mail '{msg['subject']}' could not be forwarded: {str(e)}")

        except Exception as e:
            traceback.print_exc()
            print(f"Error: Problem forwarding emails in {mailbox} mailbox: {str(e)}")

        print("-------------------")


if __name__ == "__main__":
    forward_mail()
