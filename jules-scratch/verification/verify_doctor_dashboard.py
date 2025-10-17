from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Log in as a doctor
        page.goto("http://127.0.0.1:5000/login")
        page.select_option("select#role", "doctor")
        page.fill("input#username", "doctor_test")
        page.fill("input#password", "password123")
        page.click("button[type=submit]")

        # Add a default doctor if none exists
        if "Invalid credentials" in page.text_content("body"):
            page.goto("http://127.0.0.1:5000/login")
            page.select_option("select#role", "admin")
            page.fill("input#username", "admin")
            page.fill("input#password", "admin123")
            page.click("button[type=submit]")
            page.goto("http://127.0.0.1:5000/admin/doctor/add")
            page.fill("input#username", "doctor_test")
            page.fill("input#full_name", "Test Doctor")
            page.fill("input#email", "test.doctor@example.com")
            page.fill("input#password", "password123")
            page.select_option("select#department_id", "1")
            page.click("button[type=submit]")
            page.goto("http://127.0.0.1:5000/logout")

            # Log in again as the new doctor
            page.goto("http://127.0.0.1:5000/login")
            page.select_option("select#role", "doctor")
            page.fill("input#username", "doctor_test")
            page.fill("input#password", "password123")
            page.click("button[type=submit]")

        # Verify navigation to the doctor dashboard
        if "Doctor Dashboard" not in page.text_content("h2"):
            raise Exception("Failed to navigate to the doctor dashboard")

        # Take a screenshot of the doctor dashboard
        page.screenshot(path="jules-scratch/verification/doctor_dashboard.png")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)