from playwright.sync_api import sync_playwright
import time
import json

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Intercept all responses to log API endpoints
        def handle_response(response):
            if "back.shilendans.gov.mn" in response.url or "api" in response.url:
                try:
                    if response.status == 200 and response.request.method != "OPTIONS":
                        req = response.request
                        print(f"[{req.method}] {response.url}")
                        if req.post_data:
                            print(f"   Payload: {req.post_data}")
                except:
                    pass
        
        page.on("response", handle_response)
        
        print("Navigating to shilendans.gov.mn...")
        page.goto("https://shilendans.gov.mn/")
        time.sleep(5)
        
        print("Navigating to Open Data page...")
        page.goto("https://shilendans.gov.mn/openData")
        time.sleep(5)
        
        print("Local Storage:")
        print(page.evaluate("() => JSON.stringify(localStorage)"))
        
        browser.close()

if __name__ == "__main__":
    run()
