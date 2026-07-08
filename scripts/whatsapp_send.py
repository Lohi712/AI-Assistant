"""
WhatsApp Web automation helper script for VEGA AI Assistant.

This script runs in a SEPARATE process from VEGA to avoid
asyncio event loop conflicts between Playwright and edge-tts.

Usage:
  # Headless send (background):
  python whatsapp_send.py --session <dir> --recipient "Name" --message "Hello" --headless

  # Login only (visible browser for QR scan):
  python whatsapp_send.py --session <dir> --login-only

  # Visible send (for testing):
  python whatsapp_send.py --session <dir> --recipient "Name" --message "Hello"

Output codes (printed to stdout):
  MESSAGE_SENT    — message was sent successfully
  LOGIN_REQUIRED  — not logged in, need QR scan
  LOGIN_SUCCESS   — QR login completed
  LOGIN_TIMEOUT   — QR login timed out
  SEND_FAILED     — could not send the message
  ERROR: <msg>    — unexpected error
"""

import argparse
import sys

# Real Chrome user-agent — WhatsApp Web rejects headless Chromium's default UA
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


# Reconfigure stdout to use UTF-8 to prevent encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description="WhatsApp Web automation")
    parser.add_argument("--session", required=True, help="Path to browser session directory")
    parser.add_argument("--recipient", help="Contact name to send to")
    parser.add_argument("--message", help="Message text to send")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser")
    parser.add_argument("--login-only", action="store_true", help="Only perform QR login")
    parser.add_argument("--fetch-contacts", action="store_true", help="Fetch recent chat names")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright, TimeoutError
    except ImportError:
        print("ERROR: Playwright is not installed")
        sys.exit(1)

    if args.login_only:
        _do_login(args.session, sync_playwright, TimeoutError)
    elif args.fetch_contacts:
        _do_fetch_contacts(args.session, sync_playwright, TimeoutError)
    else:
        _do_send(args.session, args.recipient, args.message, args.headless,
                 sync_playwright, TimeoutError)


def _do_login(session_dir, sync_playwright, TimeoutError):
    """Open a visible browser so the user can scan the QR code."""
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=False,
            channel="msedge"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://web.whatsapp.com")

        try:
            # Wait up to 90 seconds for the user to scan QR
            page.wait_for_selector(
                'div[data-testid="chat-list"]', timeout=90000
            )
            print("LOGIN_SUCCESS")
            # Scrape contacts right after login
            page.wait_for_timeout(2000)
            try:
                elements = page.locator('div[data-testid="chat-list"] span[title]').all()
                contacts = set()
                for el in elements:
                    title = el.get_attribute("title")
                    if title:
                        contacts.add(title.strip())
                if contacts:
                    print("CONTACTS_START")
                    for c in sorted(contacts):
                        print(c)
                    print("CONTACTS_END")
            except Exception:
                pass
        except TimeoutError:
            print("LOGIN_TIMEOUT")
        finally:
            browser.close()


def _do_fetch_contacts(session_dir, sync_playwright, TimeoutError):
    """Fetch the titles of recent chats on WhatsApp Web."""
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=True,
            channel="msedge"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://web.whatsapp.com")

        # Check if logged in
        try:
            page.wait_for_selector(
                'div[data-testid="chat-list"]', timeout=15000
            )
        except TimeoutError:
            print("LOGIN_REQUIRED")
            browser.close()
            return

        # Dismiss any dialogs
        page.wait_for_timeout(1000)
        try:
            dialog = page.locator('div[role="dialog"]')
            if dialog.count() > 0:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
        except Exception:
            pass

        try:
            # Wait for titles to render
            page.wait_for_selector('div[data-testid="chat-list"] span[title]', timeout=5000)
            elements = page.locator('div[data-testid="chat-list"] span[title]').all()
            contacts = set()
            for el in elements:
                title = el.get_attribute("title")
                if title:
                    contacts.add(title.strip())
            if contacts:
                print("CONTACTS_START")
                for c in sorted(contacts):
                    print(c)
                print("CONTACTS_END")
            else:
                print("NO_CONTACTS")
        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            browser.close()


def _do_send(session_dir, recipient, message, headless,
             sync_playwright, TimeoutError):
    """Send a WhatsApp message."""
    if not recipient or not message:
        print("ERROR: recipient and message are required")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=session_dir,
            headless=headless,
            channel="msedge"
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://web.whatsapp.com")

        # Check if logged in
        try:
            page.wait_for_selector(
                'div[data-testid="chat-list"]', timeout=15000
            )
        except TimeoutError:
            print("LOGIN_REQUIRED")
            browser.close()
            return

        # Dismiss any modal dialogs (e.g. "Turn on desktop notifications")
        # that block interaction with the search box
        page.wait_for_timeout(1000)
        try:
            dialog = page.locator('div[role="dialog"]')
            if dialog.count() > 0:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
        except Exception:
            pass

        # Search for the contact
        search_box = page.get_by_role(
            "textbox", name="Search or start a new chat"
        )
        try:
            search_box.click(timeout=5000)
        except Exception:
            # Force click bypasses the pointer-events interception check
            try:
                search_box.click(force=True, timeout=5000)
            except Exception as e:
                print(f"SEND_FAILED: Could not click search box - {e}")
                browser.close()
                return

        # Type the recipient name
        search_box.fill("")
        page.keyboard.type(recipient, delay=30)

        # Wait for search results to load
        page.wait_for_timeout(1500)

        # Try to click the first search result directly
        # WhatsApp search results appear as list items in the chat list
        try:
            # Look for search result items with matching text
            first_result = page.locator(
                'div[data-testid="chat-list"] span[title]'
            ).first
            first_result.click(timeout=3000)
        except Exception:
            # Fallback: use keyboard navigation to select first result
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")

        # Wait for the message box to appear (means chat has opened)
        # Give it more time and retry more aggressively
        message_box = None
        for attempt in range(8):
            textboxes = page.get_by_role("textbox").all()
            if len(textboxes) >= 2:
                message_box = textboxes[-1]
                break
            page.wait_for_timeout(500)

        if not message_box:
            print("SEND_FAILED: Could not find message box after opening chat")
            browser.close()
            return

        try:
            message_box.click(timeout=5000)
        except Exception:
            print("SEND_FAILED: Could not click message box")
            browser.close()
            return

        # Type and send the message
        page.keyboard.type(message, delay=10)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)  # Brief wait for delivery

        # Scrape contacts to update cache after sending
        try:
            elements = page.locator('div[data-testid="chat-list"] span[title]').all()
            contacts = set()
            for el in elements:
                title = el.get_attribute("title")
                if title:
                    contacts.add(title.strip())
            if contacts:
                print("CONTACTS_START")
                for c in sorted(contacts):
                    print(c)
                print("CONTACTS_END")
        except Exception:
            pass

        print("MESSAGE_SENT")
        browser.close()


if __name__ == "__main__":
    main()
