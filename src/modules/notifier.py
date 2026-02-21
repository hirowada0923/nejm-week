import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

class GmailNotifier:
    def __init__(self, sender_email, app_password):
        self.sender_email = sender_email
        self.app_password = app_password
        self.logger = logging.getLogger(__name__)

    def send_notification(self, recipient_emails, subject, body):
        """
        Sends an email notification via Gmail SMTP.
        recipient_emails can be a string (single email) or a list of strings.
        """
        if isinstance(recipient_emails, str):
            recipient_list = [email.strip() for email in recipient_emails.split(',')]
            recipient_str = recipient_emails
        else:
            recipient_list = recipient_emails
            recipient_str = ", ".join(recipient_list)

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = recipient_str
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        try:
            self.logger.info(f"Sending notification to {recipient_str}...")
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.sender_email, self.app_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, recipient_list, text)
            server.quit()
            self.logger.info("Notification sent successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return False
