from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        def handle_response(response):
            if "back.shilendans.gov.mn" in response.url:
                try:
                    req = response.request
                    if req.method == "GET" and ("supplier" in response.url.lower() or "integration" in response.url.lower()):
                        print(f"[{req.method}] {response.url}")
                except:
                    pass
        
        page.on("response", handle_response)
        page.goto("https://shilendans.gov.mn/supplier")
        time.sleep(3)
        page.fill("input[type='text']", "АПУ")
        page.keyboard.press("Enter")
        time.sleep(4)
        
        print("Clicking first supplier result...")
        page.click("table tbody tr:first-child")
        time.sleep(4)
        page.screenshot(path="supplier_clicked.png")
        
        print("Clicking first state org result...")
        try:
            page.click("table tbody tr:first-child", timeout=3000)
            time.sleep(4)
        except Exception as e:
            print("Could not click second table:", e)
        page.screenshot(path="supplier_clicked2.png")
        
        browser.close()

if __name__ == "__main__":
    run()
