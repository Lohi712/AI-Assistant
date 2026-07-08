"""
WhatsApp automation command for VEGA AI Assistant.

Uses playwright to control WhatsApp Web headlessly.
On first use, opens a visible browser for QR code login.
All subsequent uses run completely in the background.
"""

import os
import subprocess
import sys

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

# Session directory for persistent WhatsApp Web login
_SESSION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.whatsapp_session'
)

# Contacts cache file to enable fuzzy matching
_CONTACTS_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '.whatsapp_contacts.txt'
)

# Daemon connection settings (must match scripts/whatsapp_daemon.py)
_DAEMON_HOST = "127.0.0.1"
_DAEMON_PORT = 5824


class WhatsAppCommand(BaseCommand):
    """Send WhatsApp messages via headless browser automation."""

    priority = 30

    @property
    def triggers(self) -> list[str]:
        return ["whatsapp", "send whatsapp"]

    def execute(self, query: str, assistant) -> None:
        contacts = self._load_cached_contacts()

        # ── Smart parsing: try to extract recipient and message from the query ──
        # Patterns: "send whatsapp to <name> saying <msg>"
        #           "whatsapp <name> <msg>"
        #           "message <name> on whatsapp saying <msg>"
        import re
        parsed_name = None
        parsed_message = None

        # Pattern 1: "to <name> saying/that/message <msg>"
        m = re.search(
            r'(?:to|message)\s+(.+?)\s+(?:saying|that|message|say)\s+(.+)',
            query, re.IGNORECASE,
        )
        if m:
            parsed_name = m.group(1).strip()
            parsed_message = m.group(2).strip()
        else:
            # Pattern 2: "to <name>" (no message)
            m2 = re.search(r'(?:to|message)\s+(.+?)$', query, re.IGNORECASE)
            if m2:
                candidate = m2.group(1).strip()
                # Filter out command words
                noise = {"on", "via", "through", "using", "whatsapp", "a", "an"}
                if candidate.lower() not in noise and len(candidate) > 1:
                    parsed_name = candidate

        # ── Resolve recipient ──
        recipient_name = None

        if parsed_name:
            # Try fuzzy match against cached contacts
            matched_name = parsed_name
            if contacts:
                import difflib
                matches = difflib.get_close_matches(parsed_name, contacts, n=1, cutoff=0.5)
                if matches:
                    matched_name = matches[0]

            # Confirm
            assistant.speech.speak(
                f"I'll send the message to {matched_name}. Is that correct? "
                "Say yes, no, or say 'type' to type the name."
            )
            confirm = assistant.speech.listen()
            if not confirm:
                confirm = ""
            confirm_clean = "".join(
                c for c in confirm if c.isalnum() or c.isspace()
            ).strip().lower()
            confirm_words = confirm_clean.split()

            is_positive = any(
                w in confirm_words
                for w in ("yes", "yeah", "yep", "correct", "right", "yup", "sure", "ok", "okay", "y")
            )
            is_type = any(
                w in confirm_words
                for w in ("type", "keyboard", "spell", "write", "enter")
            )

            if is_type:
                assistant.speech.speak("Please type the recipient name in the terminal.")
                recipient_name = input("👤 Enter the recipient name: ").strip()
                if not recipient_name:
                    assistant.speech.speak("No name entered. Cancelling.")
                    return
            elif is_positive:
                recipient_name = matched_name
            else:
                parsed_name = None  # Fall through to the interactive loop

        if not recipient_name:
            # Interactive name collection (original loop)
            assistant.speech.speak("Who should I send the message to?")

            while True:
                print("👤 Listening for recipient name...")
                name_heard = assistant.speech.listen()
                if not name_heard or name_heard.lower() in ("none", "cancel", "cancel it", "stop"):
                    assistant.speech.speak("Cancelling WhatsApp message.")
                    return

                name_heard = name_heard.strip()
                matched_name = None

                # Fuzzy match if we have cached contacts
                if contacts:
                    import difflib
                    matches = difflib.get_close_matches(name_heard, contacts, n=1, cutoff=0.5)
                    if matches:
                        matched_name = matches[0]

                if matched_name:
                    prompt_msg = (
                        f"I heard {name_heard}, matched with {matched_name}. Is that correct? "
                        "Say yes, no, or say 'type' to type the name."
                    )
                else:
                    prompt_msg = (
                        f"I heard {name_heard}. Is that correct? "
                        "Say yes, no, or say 'type' to type the name."
                    )
                    matched_name = name_heard

                # Confirmation loop for the current name
                assistant.speech.speak(prompt_msg)
                confirmed = False
                try_again = False

                while True:
                    print("👤 Listening for confirmation ('yes', 'no', 'type')...")
                    confirm = assistant.speech.listen()
                    if not confirm:
                        confirm = "no"

                    confirm_clean = "".join(char for char in confirm if char.isalnum() or char.isspace()).strip().lower()
                    confirm_words = confirm_clean.split()

                    is_negative = any(word in confirm_words for word in ("no", "nope", "wrong", "incorrect", "false", "none"))
                    is_positive = any(word in confirm_words for word in ("yes", "yeah", "yep", "correct", "right", "yup", "sure", "ok", "okay", "y"))
                    is_type = any(word in confirm_words for word in ("type", "keyboard", "spell", "write", "enter"))

                    if is_type:
                        assistant.speech.speak("Please type the recipient name in the terminal.")
                        recipient_name = input("👤 Enter the recipient name: ").strip()
                        if not recipient_name:
                            assistant.speech.speak("No name entered. Cancelling.")
                            return
                        confirmed = True
                        break
                    elif is_positive and not is_negative:
                        recipient_name = matched_name
                        confirmed = True
                        break
                    elif is_negative:
                        try_again = True
                        break
                    else:
                        assistant.speech.speak(
                            f"Sorry, I didn't catch that. Is the recipient name {matched_name}? "
                            "Please say yes, no, or type."
                        )

                if confirmed:
                    break
                if try_again:
                    assistant.speech.speak("Okay, please say the recipient name again.")
                    continue

        print(f"👤 Recipient: {recipient_name}")

        # ── Resolve message ──
        message = parsed_message

        if not message:
            assistant.speech.speak(
                f"Got it. What message do you want to send to {recipient_name}?"
            )
            print(f"💬 Listening for message to {recipient_name}...")
            message = assistant.speech.listen()
            if not message:
                message = "None"

            retries = 0
            while message == "None" and retries < 3:
                assistant.speech.speak(
                    "Sorry, I didn't catch the message. Please say it again."
                )
                message = assistant.speech.listen()
                if not message:
                    message = "None"
                retries += 1

            if message == "None":
                assistant.speech.speak("I couldn't get your message. Cancelling.")
                return

        assistant.speech.speak(
            f"I'll send '{message}' to {recipient_name}. Please wait."
        )

        try:
            self._send_message(recipient_name, message, assistant)
        except Exception as e:
            logger.error("WhatsApp automation error: %s", e)
            assistant.speech.speak(
                "Sorry, I encountered an error while sending the WhatsApp message."
            )

    def _send_message(self, recipient: str, message: str, assistant) -> None:
        """
        Send a WhatsApp message, preferring the fast background daemon.

        Flow:
          1. Try to connect to the background daemon (instant send).
          2. If daemon is not running, launch it and retry.
          3. If daemon reports LOGIN_REQUIRED, fall back to visible QR login
             via the old subprocess script, then retry through daemon.
        """
        import json, socket

        # Step 1: Try the daemon
        response = self._send_via_daemon(recipient, message)

        if response is None:
            # Daemon not running — launch it and retry
            logger.info("Daemon not running, launching...")
            print("🚀 Starting WhatsApp background service...")
            if not self._launch_daemon():
                # Daemon failed to start — fall back to subprocess
                logger.warning("Daemon failed to start, using subprocess fallback")
                self._send_via_subprocess(recipient, message, assistant)
                return

            response = self._send_via_daemon(recipient, message)
            if response is None:
                logger.error("Daemon still unreachable after launch")
                self._send_via_subprocess(recipient, message, assistant)
                return

        status = response.get("status", "")

        if status == "MESSAGE_SENT":
            # Cache contacts if returned
            contacts = response.get("contacts", [])
            if contacts:
                self._save_contacts_cache(contacts)
            assistant.speech.speak("The message has been sent!")
            logger.info("WhatsApp message sent to %s (via daemon)", recipient)
            print(f"✅ WhatsApp message sent to {recipient}")
            return

        if status == "LOGIN_REQUIRED":
            # Need QR login — use visible browser via subprocess
            assistant.speech.speak(
                "You need to log into WhatsApp Web. "
                "I am opening the browser now. Please scan the QR code."
            )

            login_script = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'scripts', 'whatsapp_send.py'
            )
            login_result = subprocess.run(
                [sys.executable, login_script,
                 "--session", _SESSION_DIR,
                 "--login-only"],
                capture_output=True, encoding='utf-8', timeout=120,
            )
            login_output = login_result.stdout.strip()
            self._parse_and_cache_contacts(login_output)

            if "LOGIN_SUCCESS" not in login_output:
                assistant.speech.speak("Login failed or timed out. Please try again.")
                return

            assistant.speech.speak(
                "Login successful! Sending your message now."
            )

            # Shutdown old daemon (if any) and relaunch with new session
            self._shutdown_daemon()
            self._launch_daemon()

            # Retry via daemon
            response = self._send_via_daemon(recipient, message)
            if response and response.get("status") == "MESSAGE_SENT":
                contacts = response.get("contacts", [])
                if contacts:
                    self._save_contacts_cache(contacts)
                assistant.speech.speak("The message has been sent!")
                logger.info("WhatsApp message sent to %s", recipient)
                print(f"✅ WhatsApp message sent to {recipient}")
            else:
                # Final fallback via subprocess
                self._send_via_subprocess(recipient, message, assistant)
            return

        if status == "SEND_FAILED":
            error = response.get("error", "Unknown error")
            logger.error("Daemon send failed: %s", error)
            assistant.speech.speak(
                "Sorry, something went wrong while sending the WhatsApp message."
            )
            return

        # Unknown status
        logger.error("Unexpected daemon response: %s", response)
        assistant.speech.speak(
            "Sorry, something went wrong while sending the WhatsApp message."
        )

    # ── Daemon Communication ─────────────────────────────────────

    def _send_via_daemon(self, recipient: str, message: str) -> dict | None:
        """
        Send a message request to the background daemon via TCP.
        Returns the parsed JSON response dict, or None if daemon is unreachable.
        """
        import json, socket

        request = json.dumps({
            "action": "send",
            "recipient": recipient,
            "message": message,
        })

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(45)  # Allow up to 45s for the send operation
            sock.connect((_DAEMON_HOST, _DAEMON_PORT))
            sock.sendall(request.encode("utf-8"))
            sock.shutdown(socket.SHUT_WR)  # Signal end of request

            # Read response
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            sock.close()

            return json.loads(data.decode("utf-8"))
        except (ConnectionRefusedError, ConnectionResetError, OSError):
            return None
        except Exception as e:
            logger.error("Daemon communication error: %s", e)
            return None

    def _launch_daemon(self) -> bool:
        """Launch the daemon process in the background. Returns True if started."""
        daemon_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'whatsapp_daemon.py'
        )

        if not os.path.isfile(daemon_script):
            logger.error("Daemon script not found: %s", daemon_script)
            return False

        try:
            # Launch daemon as a detached background process
            subprocess.Popen(
                [sys.executable, daemon_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
            )

            # Wait for daemon to be ready (up to 25 seconds)
            import socket as _sock
            for i in range(50):
                import time
                time.sleep(0.5)
                try:
                    test = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                    test.settimeout(2)
                    test.connect((_DAEMON_HOST, _DAEMON_PORT))
                    # Send a ping to verify it's responsive
                    test.sendall(b'{"action":"ping"}')
                    test.shutdown(_sock.SHUT_WR)
                    resp = test.recv(1024)
                    test.close()
                    if b"PONG" in resp:
                        logger.info("Daemon started successfully (took %.1fs)", (i + 1) * 0.5)
                        return True
                except (ConnectionRefusedError, OSError):
                    continue
                except Exception:
                    continue

            logger.error("Daemon did not start within 25 seconds")
            return False
        except Exception as e:
            logger.error("Failed to launch daemon: %s", e)
            return False

    def _shutdown_daemon(self):
        """Tell the daemon to shut down."""
        import json, socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((_DAEMON_HOST, _DAEMON_PORT))
            sock.sendall(b'{"action":"shutdown"}')
            sock.shutdown(socket.SHUT_WR)
            sock.recv(1024)
            sock.close()
        except Exception:
            pass

    def _send_via_subprocess(self, recipient: str, message: str, assistant) -> None:
        """Fallback: send via the old subprocess method."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'whatsapp_send.py'
        )

        if not os.path.isfile(script_path):
            logger.error("WhatsApp send script not found: %s", script_path)
            assistant.speech.speak("WhatsApp send script is missing.")
            return

        result = subprocess.run(
            [sys.executable, script_path,
             "--session", _SESSION_DIR,
             "--recipient", recipient,
             "--message", message,
             "--headless"],
            capture_output=True, encoding='utf-8', timeout=60,
        )

        output = result.stdout.strip()
        self._parse_and_cache_contacts(output)

        if "MESSAGE_SENT" in output:
            assistant.speech.speak("The message has been sent!")
            logger.info("WhatsApp message sent to %s (subprocess fallback)", recipient)
            print(f"✅ WhatsApp message sent to {recipient}")
        else:
            logger.error("Subprocess send failed: %s", output)
            assistant.speech.speak(
                "Sorry, something went wrong while sending the WhatsApp message."
            )

    def _load_cached_contacts(self) -> list[str]:
        """Load cached contacts from the local cache file."""
        if not os.path.exists(_CONTACTS_CACHE_FILE):
            return []
        try:
            with open(_CONTACTS_CACHE_FILE, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error("Failed to load cached contacts: %s", e)
            return []

    def _save_contacts_cache(self, contacts: list[str]) -> None:
        """Save unique contacts to the local cache file."""
        try:
            with open(_CONTACTS_CACHE_FILE, 'w', encoding='utf-8') as f:
                for c in sorted(set(contacts)):
                    f.write(f"{c}\n")
        except Exception as e:
            logger.error("Failed to save contacts cache: %s", e)

    def _parse_and_cache_contacts(self, stdout: str) -> None:
        """Parse the line-by-line contacts block from script stdout and cache them."""
        if "CONTACTS_START" not in stdout:
            return
        try:
            lines = stdout.splitlines()
            start_idx = -1
            end_idx = -1
            for i, line in enumerate(lines):
                if line.strip() == "CONTACTS_START":
                    start_idx = i
                elif line.strip() == "CONTACTS_END":
                    end_idx = i
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                contacts = [lines[j].strip() for j in range(start_idx + 1, end_idx) if lines[j].strip()]
                if contacts:
                    self._save_contacts_cache(contacts)
                    logger.debug("Successfully updated contacts cache with %d contacts", len(contacts))
        except Exception as e:
            logger.error("Failed to parse and cache contacts: %s", e)
