from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            if "back.shilendans.gov.mn" in response.url:
                try:
                    req = response.request
                    if req.method == "GET" and "search" in response.url.lower():
                        print(f"[{req.method}] {response.url}")
                    elif req.method == "POST":
                        print(f"[{req.method}] {response.url}")
                        print(f"   Payload: {req.post_data}")
                except:
                    pass
        
        page.on("response", handle_response)
        
        print("Navigating to shilendans.gov.mn...")
        page.goto("https://shilendans.gov.mn/")
        time.sleep(3)
        
        print("Typing 'Цогбэйс' in search...")
        # Try to find input placeholders
        page.fill("input[type='text']", "Цогбэйс")
        page.keyboard.press("Enter")
        time.sleep(5)
        
        browser.close()

if __name__ == "__main__":
    run()
