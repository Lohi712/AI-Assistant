from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        print("Launching default chromium...")
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=".whatsapp_test_session",
                headless=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
            print("Chromium launched.")
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://web.whatsapp.com")
            print("Navigated to WhatsApp. Waiting 15s...")
            page.wait_for_timeout(15000)
            page.screenshot(path="chromium_test.png")
            print("Screenshot saved.")
            browser.close()
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    test()
