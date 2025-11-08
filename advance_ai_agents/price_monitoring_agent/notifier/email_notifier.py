import os

from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
load_dotenv("api.env")

MAX_TWILIO_LENGTH = 1600

_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
_client = TwilioClient(_account_sid, _auth_token) if _account_sid and _auth_token else None

def _truncate_message(body):
    if len(body) > MAX_TWILIO_LENGTH:
        return body[:MAX_TWILIO_LENGTH - 3] + "..."
    return body

def _send_message(body, to_number, from_number, channel="sms"):
    if not _client:
        return f"[{channel.upper()} Failed] Twilio credentials missing!"

    if not to_number or not from_number:
        return f"[{channel.upper()} Failed] Missing phone numbers!"

    body = _truncate_message(body)

    try:
        if channel == "whatsapp":
            from_number = f"whatsapp:{from_number}"
            to_number = f"whatsapp:{to_number}"

        message = _client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        return f"[✅ {channel.upper()} Sent] SID: {message.sid}"
    except Exception as e:
        return f"[{channel.upper()} Failed] {e}"

def send_sms(body, to_number):
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    return _send_message(body, to_number, from_number, channel="sms")

def send_whatsapp(body, to_number):
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
    return _send_message(body, to_number, from_number, channel="whatsapp")

def send_notification(subject, body, channels=["sms", "whatsapp"], recipient=None):
    send_results = {}

    if recipient is None:
        recipient = {
            "sms": os.getenv("CLIENT_PHONE_NO"),
            "whatsapp": os.getenv("CLIENT_WHATSAPP_NO")
        }

    if "sms" in channels and recipient.get("sms"):
        send_results["sms"] = send_sms(body, recipient.get("sms"))

    if "whatsapp" in channels and recipient.get("whatsapp"):
        send_results["whatsapp"] = send_whatsapp(body, recipient.get("whatsapp"))

    return {
        "subject": subject,
        "body": body,
        "recipient": recipient,
        "status": send_results
    }