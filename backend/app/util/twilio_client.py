from twilio.rest import Client
from typing import Optional
from config import settings

class TwilioClient:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_phone = settings.TWILIO_FROM_PHONE
        self.client = Client(self.account_sid, self.auth_token)

    def send_sms(self, to_phone: str, message: str) -> Optional[str]:
        """
        Send SMS using Twilio
        
        Args:
            to_phone (str): Recipient phone number in E.164 format (+1234567890)
            message (str): Message content to send
            
        Returns:
            Optional[str]: Message SID if successful, None if failed
        """
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=to_phone
            )
            return message.sid
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
            return None

    def get_message_status(self, message_sid: str) -> Optional[str]:
        """
        Get the status of a sent message
        
        Args:
            message_sid (str): The SID of the message to check
            
        Returns:
            Optional[str]: Message status if found, None if not found
        """
        try:
            message = self.client.messages(message_sid).fetch()
            return message.status
        except Exception as e:
            print(f"Error getting message status: {str(e)}")
            return None 