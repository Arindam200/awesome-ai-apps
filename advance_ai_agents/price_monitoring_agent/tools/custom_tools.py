from typing import Dict, Callable, Optional
import os

from agents.decision_logic import is_significant_change
from crewai.tools import BaseTool
from dotenv import load_dotenv
from notifier.email_notifier import send_notification
from pydantic import Field
load_dotenv("api.env")

class DecisionTool(BaseTool):
    previous_data: Dict = Field(default_factory=dict)
    name: str = "DecisionTool"
    description: str = "Compares new and old product data for meaningful changes."

    def _run(self, new_data: Dict) -> bool:
        try:
            change_detected = is_significant_change(self.previous_data, new_data)
            self.previous_data = new_data
            return change_detected
        except Exception:
            return False


class NotifyTool(BaseTool):
    generate_message_fn: Callable = Field(...)
    default_recipient: Optional[Dict[str, str]] = Field(default_factory=dict)
    name: str = "NotifyTool"
    description: str = "Send alert via SMS and WhatsApp when product change detected."

    def _run(self, scraped_data: Dict, recipient: Optional[Dict[str, str]] = None) -> Dict:
        try:
            message = self.generate_message_fn(scraped_data)
            if recipient is None:
                recipient = self.default_recipient or {
                    "sms": os.getenv("CLIENT_PHONE_NO"),    # Use actual number from env
                    "whatsapp": os.getenv("CLIENT_WHATSAPP_NO")   # Use actual number from env
                }
            return send_notification(
                subject="Price Alert",
                body=message,
                channels=["sms", "whatsapp"],
                recipient=recipient
            )
        except Exception as e:
            return {"status": "failed", "error": str(e)}