from playwright.sync_api import sync_playwright
import json


with sync_playwright() as playwright:

    browser = playwright.chromium.launch(
        headless=False,
        # ignore_default_args=["--headless"],
        # args=["--headless=new"],
        channel="chrome",
    )

    context = browser.new_context()

    page = context.new_page()
    page.goto("https://www.roblox.com/transactions")
    input("Press enter to copy cookies")
    with open("test", "w") as f:
        cookies = context.cookies()
        f.write(json.dumps(cookies, indent=4))

    quit()
