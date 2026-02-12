from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Start the app
    # This assumes the app is running on localhost:5000
    import time
    time.sleep(5)
    page.goto("http://localhost:5000/login")

    # Log in as admin
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin123")
    page.get_by_label("Role").select_option("admin")
    page.get_by_role("button", name="Login").click()

    # Navigate to Manage Doctors page
    page.get_by_role("link", name="Manage Doctors").click()

    # Take a screenshot
    page.screenshot(path="jules-scratch/verification/admin_manage_doctors.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)