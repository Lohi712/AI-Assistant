"""
WhatsApp automation command for VEGA AI Assistant.

Uses pyautogui to control the WhatsApp Desktop application.
"""

import time
from pathlib import Path

import pyautogui

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppCommand(BaseCommand):
    """Send WhatsApp messages via desktop app automation."""

    priority = 30

    @property
    def triggers(self) -> list[str]:
        return ["whatsapp", "send whatsapp"]

    def execute(self, query: str, assistant) -> None:
        # Collect recipient
        assistant.speech.speak("Who should I send the message to?")
        recipient_name = input("👤 Enter the recipient name: ").strip()
        if not recipient_name:
            assistant.speech.speak("I need a recipient name to proceed.")
            return

        # Collect message
        assistant.speech.speak(f"Got it. What message do you want to send to {recipient_name}?")
        print(f"💬 Listening for message to {recipient_name}...")
        message = assistant.speech.listen()

        retries = 0
        while message == "None" and retries < 3:
            assistant.speech.speak("Sorry, I didn't catch the message. Please say it again.")
            message = assistant.speech.listen()
            retries += 1

        if message == "None":
            assistant.speech.speak("I couldn't get your message. Cancelling.")
            return

        assistant.speech.speak(
            f"I'll send '{message}' to {recipient_name}. "
            "Opening WhatsApp now."
        )

        try:
            self._send_via_desktop(recipient_name, message, assistant.settings.assets_dir)
            assistant.speech.speak("The message has been sent!")
            logger.info("WhatsApp message sent to %s", recipient_name)
        except Exception as e:
            logger.error("WhatsApp automation error: %s", e)
            assistant.speech.speak(
                "Sorry, I encountered an error while controlling WhatsApp."
            )

    @staticmethod
    def _send_via_desktop(recipient: str, message: str, assets_dir: str) -> None:
        """
        Automate WhatsApp Desktop to send a message.

        Args:
            recipient: Contact name to search for.
            message: Message text to send.
            assets_dir: Path to assets directory containing WhatsappTextBox.png.
        """
        # Open WhatsApp from Start Menu
        pyautogui.press("win")
        time.sleep(1)
        pyautogui.write("WhatsApp", interval=0.05)
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(3)  # Wait for app to load

        # Search for contact
        pyautogui.hotkey("ctrl", "f")
        time.sleep(1)
        pyautogui.write(recipient, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("enter")
        time.sleep(1)
        pyautogui.press("tab")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1)

        # Find and click the text box
        textbox_img = Path(assets_dir) / "WhatsappTextBox.png"
        if textbox_img.exists():
            text_box_loc = pyautogui.locateCenterOnScreen(
                str(textbox_img), confidence=0.8
            )
            if text_box_loc:
                pyautogui.click(text_box_loc)
                time.sleep(0.5)
            else:
                logger.warning("Could not locate WhatsApp text box via image.")

        # Type and send
        pyautogui.write(message, interval=0.02)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2)

        # Close WhatsApp
        pyautogui.hotkey("alt", "F4")
