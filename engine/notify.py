import smtplib


def send_text(message: str):

    sender = "mkowusu0522@gmail.com"
    password = "xydrev-2fywzy-Fuwpuf"

    receiver = "4438265706@txt.att.net"   # your phone via carrier gateway

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, message)
