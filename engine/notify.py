import os
import smtplib


def send_text(message: str) -> None:
    """
    Send an SMS alert via Gmail SMTP-to-carrier gateway.

    Requires environment variables:
      NOTIFY_SENDER   — Gmail address (e.g. you@gmail.com)
      NOTIFY_PASSWORD — Gmail app password (not the account password)
      NOTIFY_RECEIVER — Carrier gateway address (e.g. 5551234567@txt.att.net)

    Logs a warning and returns silently if any variable is missing so that
    a missing config does not crash the scan pipeline.
    """
    sender = os.getenv("NOTIFY_SENDER")
    password = os.getenv("NOTIFY_PASSWORD")
    receiver = os.getenv("NOTIFY_RECEIVER")

    if not all([sender, password, receiver]):
        print(
            "WARNING: send_text() skipped — "
            "NOTIFY_SENDER / NOTIFY_PASSWORD / NOTIFY_RECEIVER not set."
        )
        return

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, message)
