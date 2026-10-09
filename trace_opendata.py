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
                    if "export" in response.url.lower() or "file" in response.url.lower() or "download" in response.url.lower():
                        print(f"[{req.method}] {response.url}")
                        if req.post_data:
                            print(f"   Payload: {req.post_data}")
                except:
                    pass
        
        page.on("response", handle_response)
        page.goto("https://shilendans.gov.mn/openData")
        time.sleep(3)
        
        print("Clicking export button for a form...")
        try:
            # Let's find any button that might be export/download (like a cloud icon or text saying ТАТАХ, EXCEL, CSV, etc)
            # Find all buttons and click the first one that has a download icon or is inside the grid
            page.evaluate('''
                const buttons = Array.from(document.querySelectorAll('button, a'));
                const dl = buttons.find(b => b.innerText.includes('ТАТАХ') || b.innerText.includes('XLS') || b.innerHTML.includes('download'));
                if (dl) dl.click();
            ''')
            time.sleep(10)
        except Exception as e:
            print("Error clicking:", e)
        
        browser.close()

if __name__ == "__main__":
    run()
