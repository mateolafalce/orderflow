"""
Message Interface - Twilio WhatsApp Integration
Handles sending and receiving WhatsApp messages via Twilio API
"""

import os
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class WhatsAppMessenger:
    """
    WhatsApp messaging interface using Twilio API
    """
    
    def __init__(self):
        """Initialize Twilio client with credentials from environment variables"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
        self.to_number = os.getenv('TWILIO_TO_NUMBER')
        
        # Validate required credentials
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing Twilio credentials. Please check your .env file for "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
            )
        
        # Initialize Twilio client
        self.client = Client(self.account_sid, self.auth_token)
    
    def send_message(
        self, 
        body: str, 
        to_number: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> dict:
        """
        Send a WhatsApp message via Twilio
        
        Args:
            body: The message text to send
            to_number: Optional recipient number (defaults to TWILIO_TO_NUMBER from .env)
            media_url: Optional URL to media file (image, video, etc.)
        
        Returns:
            dict: Response containing message SID and status
        
        Raises:
            TwilioRestException: If message sending fails
        """
        # Use default recipient if none provided
        recipient = to_number or self.to_number
        
        if not recipient:
            raise ValueError("No recipient number provided")
        
        # Format numbers for WhatsApp (must include 'whatsapp:' prefix)
        from_whatsapp = f"whatsapp:{self.from_number}"
        to_whatsapp = f"whatsapp:{recipient}"
        
        try:
            # Prepare message parameters
            message_params = {
                'from_': from_whatsapp,
                'body': body,
                'to': to_whatsapp
            }
            
            # Add media URL if provided
            if media_url:
                message_params['media_url'] = [media_url]
            
            # Send message
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
        """
        Send a WhatsApp message to the default number configured in .env
        
        Args:
            body: The message text to send
            media_url: Optional URL to media file
        
        Returns:
            dict: Response containing message SID and status
        """
        return self.send_message(body, media_url=media_url)
    
    def get_message_status(self, message_sid: str) -> dict:
        """
        Get the status of a previously sent message
        
        Args:
            message_sid: The SID of the message to check
        
        Returns:
            dict: Message status information
        """
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


# Singleton instance for easy access
_messenger_instance = None

def get_messenger() -> WhatsAppMessenger:
    """
    Get or create the WhatsApp messenger singleton instance
    
    Returns:
        WhatsAppMessenger: The messenger instance
    """
    global _messenger_instance
    if _messenger_instance is None:
        _messenger_instance = WhatsAppMessenger()
    return _messenger_instance


# Convenience functions
def send_whatsapp_message(body: str, to_number: Optional[str] = None, media_url: Optional[str] = None) -> dict:
    """
    Convenience function to send a WhatsApp message
    
    Args:
        body: The message text to send
        to_number: Optional recipient number
        media_url: Optional URL to media file
    
    Returns:
        dict: Response containing message SID and status
    """
    messenger = get_messenger()
    return messenger.send_message(body, to_number, media_url)


def send_order_notification(order_id: int, customer_name: str, order_details: str) -> dict:
    """
    Send an order notification via WhatsApp
    
    Args:
        order_id: The order ID
        customer_name: Customer's name
        order_details: Details of the order
    
    Returns:
        dict: Response containing message SID and status
    """
    message = f"""
*New Order - #{order_id}*

Customer: {customer_name}

Order details:
{order_details}

Please confirm receipt of this order!
    """.strip()
    
    return send_whatsapp_message(message)


if __name__ == "__main__":
    # Test the integration
    print("Testing Twilio WhatsApp Integration...")
    
    try:
        messenger = WhatsAppMessenger()
        print(f"Messenger initialized")
        print(f"  From: {messenger.from_number}")
        print(f"  To: {messenger.to_number}")
        
        # Send test message
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
