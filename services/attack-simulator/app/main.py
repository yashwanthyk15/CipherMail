import smtplib
from email.message import EmailMessage
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp-gateway")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

def send_phishing_email():
    msg = EmailMessage()
    msg.set_content("""
    Dear Customer,
    
    Your account will be suspended in 24 hours due to suspicious activity.
    Please verify your identity immediately by clicking the link below:
    
    http://secure-update-billing-verification.com/login
    
    Failure to verify will result in account closure.
    
    Regards,
    Support Team
    """)
    
    msg['Subject'] = "URGENT: Verify Your Account Information"
    msg['From'] = "support@paypal-security-update.com"
    msg['To'] = "user@company.com"
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg)
        logger.info("Sent phishing simulation email")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    logger.info("Starting Attack Simulator...")
    # Wait for gateway to start
    time.sleep(15)
    
    # Send a test email every 30 seconds
    while True:
        send_phishing_email()
        time.sleep(30)
