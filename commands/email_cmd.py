"""
Email command for VEGA AI Assistant.

Sends emails via Gmail SMTP with App Password authentication.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class EmailCommand(BaseCommand):
    """Compose and send emails via Gmail."""

    priority = 30

    @property
    def triggers(self) -> list[str]:
        return ["email", "send email", "send mail"]

    def execute(self, query: str, assistant) -> None:
        gmail_user = assistant.settings.gmail_user
        gmail_psw = assistant.settings.gmail_app_password

        if not gmail_user or not gmail_psw:
            assistant.speech.speak(
                "Email is not configured. Please set your Gmail credentials "
                "in the environment file."
            )
            return

        # Collect recipient
        assistant.speech.speak("Who is the recipient? Please type their email address.")
        recipient = input("📧 Enter recipient's email: ").strip()
        if not recipient or "@" not in recipient:
            assistant.speech.speak("That doesn't look like a valid email address.")
            return

        # Collect subject
        assistant.speech.speak("What is the subject of the email?")
        subject = assistant.speech.listen()
        while subject == "None":
            assistant.speech.speak("I didn't catch the subject. Please try again.")
            subject = assistant.speech.listen()

        # Collect body
        assistant.speech.speak("Now, please say the body of your email.")
        body = assistant.speech.listen()
        while body == "None":
            assistant.speech.speak("Sorry, I didn't get the body. Please try again.")
            body = assistant.speech.listen()

        # Confirm before sending
        assistant.speech.speak(
            f"Sending email to {recipient} with subject: {subject}. "
            "Shall I proceed? Say yes or no."
        )
        confirm = assistant.speech.listen().lower()
        if "yes" not in confirm and "yeah" not in confirm and "send" not in confirm:
            assistant.speech.speak("Email cancelled.")
            return

        # Send
        assistant.speech.speak("Authenticating and sending email...")
        success = self._send(gmail_user, gmail_psw, recipient, subject, body)

        if success:
            assistant.speech.speak("Email has been sent successfully!")
            logger.info("Email sent to %s", recipient)
        else:
            assistant.speech.speak("Sorry, the email could not be sent.")

    @staticmethod
    def _send(sender: str, password: str, to: str, subject: str, body: str) -> bool:
        """
        Send an email via Gmail SMTP.

        Args:
            sender: Gmail address.
            password: Gmail App Password.
            to: Recipient email address.
            subject: Email subject line.
            body: Email body text.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False
