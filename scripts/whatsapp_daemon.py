"""
WhatsApp Web Background Daemon for VEGA AI Assistant.

A lightweight TCP server that keeps a single Playwright browser open
in the background, ready to send messages near-instantly.

Features:
  - Auto-sleep: shuts down after 10 minutes of inactivity
  - Resource blocking: blocks images, media, fonts, CSS to save RAM
  - Chromium performance flags: disables GPU, limits JS heap

Protocol (JSON over TCP):
  Request:  {"action": "send", "recipient": "Name", "message": "Hello"}
  Request:  {"action": "ping"}
  Request:  {"action": "shutdown"}
  Response: {"status": "MESSAGE_SENT", "contacts": [...]}
  Response: {"status": "LOGIN_REQUIRED"}
  Response: {"status": "SEND_FAILED", "error": "..."}
  Response: {"status": "PONG"}
"""

import json
import os
import socket
import sys
import threading
import time

# Reconfigure stdout to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── Configuration ───────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 5824
IDLE_TIMEOUT_SECONDS = 600  # 10 minutes

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

CHROMIUM_ARGS = [
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--no-first-run",
    "--js-flags=--max-old-space-size=128",
]

# Resource types to block (saves ~50% RAM)
BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

SESSION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".whatsapp_session",
)


class WhatsAppDaemon:
    """Background daemon that keeps a headless WhatsApp Web browser alive."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self._ready = False       # True once chat-list is visible
        self._last_activity = time.time()
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self):
        """Initialize Playwright, launch browser, navigate to WhatsApp Web."""
        from playwright.sync_api import sync_playwright

        print("[daemon] Starting Playwright...", flush=True)
        self._playwright = sync_playwright().start()

        print("[daemon] Launching Chromium (headless)...", flush=True)
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="msedge",
            args=CHROMIUM_ARGS,
        )

        self._page = (
            self._browser.pages[0] if self._browser.pages
            else self._browser.new_page()
        )

        # Block heavy resources to save memory
        self._page.route("**/*", self._route_handler)

        print("[daemon] Navigating to WhatsApp Web...", flush=True)
        self._page.goto("https://web.whatsapp.com")

        # Check if logged in
        try:
            self._page.wait_for_selector(
                'div[data-testid="chat-list"]', timeout=20000
            )
        except Exception:
            print("[daemon] NOT logged in — LOGIN_REQUIRED", flush=True)
            self._ready = False
            return

        # Dismiss any modal dialogs
        self._page.wait_for_timeout(1000)
        try:
            dialog = self._page.locator('div[role="dialog"]')
            if dialog.count() > 0:
                self._page.keyboard.press("Escape")
                self._page.wait_for_timeout(300)
        except Exception:
            pass

        self._ready = True
        self._last_activity = time.time()
        print("[daemon] WhatsApp Web is READY.", flush=True)

    def stop(self):
        """Clean up browser and Playwright."""
        print("[daemon] Shutting down...", flush=True)
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._ready = False
        print("[daemon] Stopped.", flush=True)

    # ── Resource blocking ────────────────────────────────────────

    def _route_handler(self, route):
        """Abort blocked resource types, allow everything else."""
        try:
            if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
                route.abort()
            else:
                route.continue_()
        except Exception:
            pass

    # ── Message sending ──────────────────────────────────────────

    def send_message(self, recipient: str, message: str) -> dict:
        """Send a WhatsApp message. Returns a status dict."""
        with self._lock:
            self._last_activity = time.time()

            if not self._ready:
                return {"status": "LOGIN_REQUIRED"}

            page = self._page

            try:
                print("[daemon] send: dismissing dialogs...", flush=True)
                try:
                    dialog = page.locator('div[role="dialog"]')
                    if dialog.count() > 0:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)
                except Exception:
                    pass

                # Clear any previous search
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)

                print("[daemon] send: clicking search box...", flush=True)
                search_box = page.get_by_role(
                    "textbox", name="Search or start a new chat"
                )
                try:
                    search_box.click(timeout=5000)
                except Exception:
                    try:
                        search_box.click(force=True, timeout=5000)
                    except Exception as e:
                        return {
                            "status": "SEND_FAILED",
                            "error": f"Could not click search box - {e}",
                        }

                print(f"[daemon] send: typing recipient '{recipient}'...", flush=True)
                search_box.fill("")
                page.keyboard.type(recipient, delay=30)

                # Wait for search results
                page.wait_for_timeout(1500)

                print("[daemon] send: clicking first result...", flush=True)
                try:
                    first_result = page.locator(
                        'div[data-testid="chat-list"] span[title]'
                    ).first
                    first_result.click(timeout=3000)
                except Exception:
                    page.keyboard.press("ArrowDown")
                    page.wait_for_timeout(300)
                    page.keyboard.press("Enter")

                print("[daemon] send: waiting for message box...", flush=True)
                message_box = None
                for _ in range(8):
                    textboxes = page.get_by_role("textbox").all()
                    if len(textboxes) >= 2:
                        message_box = textboxes[-1]
                        break
                    page.wait_for_timeout(500)

                if not message_box:
                    return {
                        "status": "SEND_FAILED",
                        "error": "Could not find message box after opening chat",
                    }

                try:
                    message_box.click(timeout=5000)
                except Exception:
                    return {
                        "status": "SEND_FAILED",
                        "error": "Could not click message box",
                    }

                print("[daemon] send: typing message...", flush=True)
                page.keyboard.type(message, delay=10)
                page.wait_for_timeout(200)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)

                print("[daemon] send: scraping contacts...", flush=True)
                contacts = self._scrape_contacts()

                print("[daemon] send: MESSAGE_SENT", flush=True)
                return {"status": "MESSAGE_SENT", "contacts": contacts}

            except Exception as e:
                print(f"[daemon] send: EXCEPTION: {e}", flush=True)
                return {"status": "SEND_FAILED", "error": str(e)}

    def _scrape_contacts(self) -> list:
        """Scrape visible chat titles from the sidebar."""
        try:
            elements = self._page.locator(
                'div[data-testid="chat-list"] span[title]'
            ).all()
            contacts = set()
            for el in elements:
                title = el.get_attribute("title")
                if title:
                    contacts.add(title.strip())
            return sorted(contacts)
        except Exception:
            return []

    # ── TCP Server ───────────────────────────────────────────────

    def run_server(self):
        """Run the TCP server that accepts JSON commands."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.settimeout(5.0)  # Allow periodic idle checks

        try:
            server.bind((HOST, PORT))
        except OSError as e:
            print(f"[daemon] Port {PORT} in use: {e}", flush=True)
            sys.exit(1)

        server.listen(1)
        print(f"[daemon] Listening on {HOST}:{PORT}", flush=True)

        # Start the idle timeout watcher
        idle_thread = threading.Thread(
            target=self._idle_watcher, daemon=True
        )
        idle_thread.start()

        while not self._shutdown_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                self._handle_connection(conn)
            except Exception as e:
                print(f"[daemon] Connection error: {e}", flush=True)
            finally:
                conn.close()

        server.close()

    def _handle_connection(self, conn: socket.socket):
        """Handle a single client connection."""
        conn.settimeout(60.0)

        # Read all data until client closes their write end
        data = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        except Exception:
            pass

        if not data:
            return

        print(f"[daemon] Received: {data[:200]}", flush=True)

        try:
            request = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            response = {"status": "ERROR", "error": "Invalid JSON"}
            conn.sendall(json.dumps(response).encode("utf-8"))
            return

        action = request.get("action", "")
        self._last_activity = time.time()
        print(f"[daemon] Action: {action}", flush=True)

        if action == "ping":
            response = {"status": "PONG"}
        elif action == "shutdown":
            response = {"status": "SHUTTING_DOWN"}
            self._shutdown_event.set()
        elif action == "send":
            recipient = request.get("recipient", "")
            message = request.get("message", "")
            if not recipient or not message:
                response = {
                    "status": "ERROR",
                    "error": "recipient and message are required",
                }
            else:
                response = self.send_message(recipient, message)
        else:
            response = {"status": "ERROR", "error": f"Unknown action: {action}"}

        conn.sendall(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def _idle_watcher(self):
        """Background thread that shuts down the daemon after idle timeout."""
        while not self._shutdown_event.is_set():
            time.sleep(10)
            idle_seconds = time.time() - self._last_activity
            if idle_seconds >= IDLE_TIMEOUT_SECONDS:
                print(
                    f"[daemon] Idle for {idle_seconds:.0f}s — auto-shutting down.",
                    flush=True,
                )
                self._shutdown_event.set()
                break


def main():
    daemon = WhatsAppDaemon()
    try:
        daemon.start()
        daemon.run_server()
    except KeyboardInterrupt:
        print("[daemon] Interrupted.", flush=True)
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()
