# core_utils/comms_utils.py
"""
Communication utilities: Email, SMS, WhatsApp
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import logging
import database

# === EMAIL ===
def send_email(to: str, subject: str, body: str):
    """
    Sends email via Gmail SMTP.
    Requires: Gmail App Password (not regular password)
    """
    sender = database.load_profile_setting('EMAIL_ADDRESS')
    password = database.load_profile_setting('EMAIL_APP_PASSWORD')
    
    if not sender or not password:
        return {"error": "Email not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD."}
    
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        
        logging.info(f"[Email] Sent to {to}")
        return {"success": True, "to": to, "subject": subject}
        
    except Exception as e:
        logging.error(f"[Email] Failed: {e}")
        return {"error": str(e)}

# === SMS (Twilio) ===
def send_sms(to: str, message: str):
    """
    Sends SMS via Twilio.
    Requires: Twilio account (free trial available)
    """
    account_sid = database.load_profile_setting('TWILIO_ACCOUNT_SID')
    auth_token = database.load_profile_setting('TWILIO_AUTH_TOKEN')
    from_number = database.load_profile_setting('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, from_number]):
        return {"error": "Twilio not configured"}
    
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        sms = client.messages.create(
            body=message,
            from_=from_number,
            to=to
        )
        
        logging.info(f"[SMS] Sent to {to}")
        return {"success": True, "sid": sms.sid, "to": to}
        
    except Exception as e:
        logging.error(f"[SMS] Failed: {e}")
        return {"error": str(e)}

# === WHATSAPP (via Twilio) ===
def send_whatsapp(to: str, message: str):
    """
    Sends WhatsApp message via Twilio.
    Format: to = '+1234567890' (must include country code)
    """
    account_sid = database.load_profile_setting('TWILIO_ACCOUNT_SID')
    auth_token = database.load_profile_setting('TWILIO_AUTH_TOKEN')
    
    if not all([account_sid, auth_token]):
        return {"error": "Twilio not configured"}
    
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        msg = client.messages.create(
            body=message,
            from_='whatsapp:+14155238886',  # Twilio WhatsApp sandbox
            to=f'whatsapp:{to}'
        )
        
        logging.info(f"[WhatsApp] Sent to {to}")
        return {"success": True, "sid": msg.sid, "to": to}
        
    except Exception as e:
        logging.error(f"[WhatsApp] Failed: {e}")
        return {"error": str(e)}

# === QUICK CONTACTS ===
CONTACTS = {
    'mom': {
        'email': 'fadheela.sajid@gmail.com',
        'phone': '+919744887988',
        'name': 'Fadheela'
    },
    'dad': {
        'email': 'sajidm75@gmail.com',
        'phone': '+919744883288',
        'name': 'Sajid'
    }
}

def message_contact(contact_name: str, message: str, method='auto'):
    """
    Smart contact messaging.
    method: 'auto', 'email', 'sms', 'whatsapp'
    """
    contact = CONTACTS.get(contact_name.lower())
    if not contact:
        return {"error": f"Contact '{contact_name}' not found"}
    
    if method == 'auto':
        # Try WhatsApp first, fallback to SMS, then email
        result = send_whatsapp(contact['phone'], message)
        if 'error' not in result:
            return result
        
        result = send_sms(contact['phone'], message)
        if 'error' not in result:
            return result
        
        return send_email(contact['email'], "Message from ARGUS", message)
    
    elif method == 'email':
        return send_email(contact['email'], "Message from ARGUS", message)
    elif method == 'sms':
        return send_sms(contact['phone'], message)
    elif method == 'whatsapp':
        return send_whatsapp(contact['phone'], message)