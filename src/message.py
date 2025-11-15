import os
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

load_dotenv()


class WhatsAppMessenger:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
        self.to_number = os.getenv('TWILIO_TO_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing Twilio credentials. Please check your .env file for "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
            )
        
        self.client = Client(self.account_sid, self.auth_token)
    
    def send_message(
        self, 
        body: str, 
        to_number: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> dict:
        recipient = to_number or self.to_number
        
        if not recipient:
            raise ValueError("No recipient number provided")
        
        from_whatsapp = f"whatsapp:{self.from_number}"
        to_whatsapp = f"whatsapp:{recipient}"
        
        try:
            message_params = {
                'from_': from_whatsapp,
                'body': body,
                'to': to_whatsapp
            }
            
            if media_url:
                message_params['media_url'] = [media_url]
            
            message = self.client.messages.create(**message_params)
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'to': recipient,
                'from': self.from_number
            }
            
        except TwilioRestException as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code,
                'to': recipient
            }
    
    def send_message_to_default(self, body: str, media_url: Optional[str] = None) -> dict:
        return self.send_message(body, media_url=media_url)
    
    def get_message_status(self, message_sid: str) -> dict:
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'to': message.to,
                'from': message.from_,
                'body': message.body,
                'date_sent': message.date_sent,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except TwilioRestException as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': e.code
            }


_messenger_instance = None

def get_messenger() -> WhatsAppMessenger:
    global _messenger_instance
    if _messenger_instance is None:
        _messenger_instance = WhatsAppMessenger()
    return _messenger_instance


def send_whatsapp_message(body: str, to_number: Optional[str] = None, media_url: Optional[str] = None) -> dict:
    messenger = get_messenger()
    return messenger.send_message(body, to_number, media_url)


def send_order_notification(order_id: int, customer_name: str, order_details: str) -> dict:
    message = f"""
*New Order - #{order_id}*

Customer: {customer_name}

Order details:
{order_details}

Please confirm receipt of this order!
    """.strip()
    
    return send_whatsapp_message(message)


if __name__ == "__main__":
    try:
        messenger = WhatsAppMessenger()
        print(f"Messenger initialized")
        print(f"  From: {messenger.from_number}")
        print(f"  To: {messenger.to_number}")
        
        print("\nSending test message...")
        response = messenger.send_message_to_default(
            "Hello! This is a test message from OrderFlow"
        )
        
        if response['success']:
            print(f"Message sent successfully!")
            print(f"  Message SID: {response['message_sid']}")
            print(f"  Status: {response['status']}")
        else:
            print(f"Failed to send message")
            print(f"  Error: {response['error']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
