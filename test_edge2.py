import os
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        print("Launching msedge channel...")
        try:
            # We use msedge channel but NO user_agent and NO AutomationControlled flag
            # This ensures it looks exactly like a normal user browser
            browser = p.chromium.launch_persistent_context(
                user_data_dir=".whatsapp_test_session2",
                headless=False,
                channel="msedge"
            )
            print("Edge launched.")
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            # Navigate
            page.goto("https://web.whatsapp.com")
            print("Navigated to WhatsApp. Waiting 15s...")
            page.wait_for_timeout(15000)
            page.screenshot(path="edge_test2.png")
            print("Screenshot saved.")
            browser.close()
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    test()
