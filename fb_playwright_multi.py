import asyncio
import json
import logging
import random
import sqlite3
import time


from playwright.async_api import async_playwright
from telegram import Bot
from telegram.constants import ParseMode

# Default parameters for faster usage/debug
DEFAULT_SETTINGS = [3, "carrera", 0, 250]

# Configuration of Telegram
TELEGRAM_API = ""
bot = Bot(TELEGRAM_API)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Main")

# Database setup
# TODO: Find more uses for the database beyond just sorting
con = sqlite3.connect("fb_database.db")
cur = con.cursor()
cur.execute(
    f"CREATE TABLE IF NOT EXISTS data(name, price, location, img, link TEXT UNIQUE primary key, time_stamp)"
)


# Function to scrape Facebook Marketplace
async def scrap_items(link_scrap):
    async with async_playwright() as playwright:
        # Launch browser with specific configurations
        browser = await playwright.chromium.launch(
            # Uncomment to run in headful mode for debugging
            # headless=False,
            ignore_default_args=["--headless"],
            args=[
                "--headless=new",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        # Set up browser context to mimic a real user's user-agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
        )

        # Load cookies from a file
        with open("cookies.json", "r") as f:
            COOKIES = json.loads(f.read())
            await context.add_cookies(COOKIES)

        # Create a new page and navigate to the specified link
        page = await context.new_page()
        await page.goto(link_scrap)

        # Scrape the last item on the page
        item = await page.locator(
            "xpath=/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div[3]/div/div[2]/div[1]"
        ).inner_text()
        item = item.replace("$", "£").replace("Free", "£0").split("\n")

        # Extract the link of the item
        link = await page.locator(
            "xpath=/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div[3]/div/div[2]/div[1]/div/div/span/div/div/div/div/a"
        ).get_attribute("href")
        link = "facebook.com" + link
        link_head, _, _ = link.partition("/?")

        # Extract the image source of the item
        img = await page.locator(
            "xpath=/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[2]/div/div/div[3]/div/div[2]/div[1]/div/div/span/div/div/div/div/a/div/div[1]/div/div/div/div/div/img"
        ).get_attribute("src")

        # Assign different info to separate variables for easier management
        price = item[0]
        name = item[1]
        location = item[2]

        data = [(name, price, location, img, link_head, time.time())]

        # Add the new info to the database
        cur.executemany(f"INSERT OR IGNORE INTO data VALUES(?, ?, ?, ?, ?, ?)", data)
        con.commit()

        # Retrieve the newest item from the database
        res = cur.execute(
            "SELECT name, price, location, img, link FROM data ORDER BY time_stamp DESC"
        )

        # Select the newest item from the database
        name, price, location, img, link_head = res.fetchall()[0]

        return [name, price, location, img, link_head]


# Function to send the info via a Telegram bot
# TODO: Add a way to check if the bot is running (client-debug)
async def send_photo(scrapper_result):
    try:
        await bot.send_photo(
            chat_id=1260011714,
            photo=scrapper_result[3],
            caption=f"<a href='{scrapper_result[4]}'>{scrapper_result[0]}</a>\n{scrapper_result[1]}\n{scrapper_result[2]}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Error sending photo: {e}")


# Main functionality
async def main(DEFAULT_SETTINGS):
    # To stop the program after certain amount of errors
    error_attempt = 0
    error_attempt_critical = 0

    # To compare if the last item in the database is the last item scrapped
    valid_item = ""

    # User input
    try:
        # Prompt user for the number of items to scrape with a default value fallback
        NUMBERS_OF_ITEMS = int(
            input(
                f"Enter number of items to scrape (default {DEFAULT_SETTINGS[0]}) --> "
            )
            or DEFAULT_SETTINGS[0]
        )

        # Prompt user for the names of items to scrape
        ITEM_LIST = [
            input(f"Enter item #{i+1} to scrape --> ") for i in range(NUMBERS_OF_ITEMS)
        ]

        # Prompt user for the lower and upper price limits with default value fallbacks
        ITEM_PRICE_LOW = float(
            input(f"Enter low limit to scrape (default £{DEFAULT_SETTINGS[2]}) --> £")
            or DEFAULT_SETTINGS[2]
        )

        ITEM_PRICE_HIGH = float(
            input(f"Enter high limit to scrape (default £{DEFAULT_SETTINGS[3]}) --> £")
            or DEFAULT_SETTINGS[3]
        )

    except Exception as e:
        logger.critical(f"Error with user input: {e}")

    ######################################################################
    # Main logic
    while True:
        try:
            for item in ITEM_LIST:

                # Scraping
                link_scrap = f"https://www.facebook.com/marketplace/112372102112762/search?minPrice={ITEM_PRICE_LOW}&maxPrice={ITEM_PRICE_HIGH}&sortBy=creation_time_descend&query={item}&exact=false"
                scrapper_result = await scrap_items(link_scrap=link_scrap)

                # Use the item's link as its ID
                item_link = str(scrapper_result[4])
                if item_link != valid_item:
                    logger.info(f"New item: {scrapper_result[0:3]}")
                    valid_item = item_link
                    await send_photo(scrapper_result)
                else:
                    logger.info(f"No new item: {scrapper_result[0:3]}")

            # Wait between 1 and 15 minutes to avoid detection
            await asyncio.sleep(random.randint(60, 900))
            print("\n")

        # Error managing

        except Exception as e:
            logging.error(e)
            error_attempt += 1

            if error_attempt >= 4:
                error_attempt = 0
                error_attempt_critical += 1

                # Sleep for 15 minutes
                await asyncio.sleep(900)
                await bot.send_message(chat_id=1260011714, text=f"Error occurred: {e}")

                if error_attempt_critical >= 3:
                    logging.critical("Too many critical errors. Exiting.")
                    await bot.send_message(
                        chat_id=1260011714, text=f"Critical error occurred: {e}"
                    )
                    return


if __name__ == "__main__":
    asyncio.run(main(DEFAULT_SETTINGS))
