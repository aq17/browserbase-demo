import os
import asyncio
import logging
from dotenv import load_dotenv
from stagehand import Stagehand
import model
from pathlib import Path

# Define constants
NO_MENU_LINK_FOUND = "NO_MENU_LINK_FOUND"

# Load env variables from .env file
load_dotenv()
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Get website URL from user input
def get_website_from_user():
    return input("Hello! Please enter a restaurant website URL: ")


async def get_restaurant_details(page, max_retries=3):
    """
    Attempt to locate the restaurant's info links using Stagehand observe
    Retries up to `max_retries` times if it fails.
    """
    instruction = (
        "Find the single most likely link containing as many of the the restaurant's following details: "
        "name, phone number, email, address, hours of operation, social media links."
        "The current webpage URL itself may be the best candidate. Return only the best link URL."
    )

    for attempt in range(1, max_retries + 1):
        try:
            result = await page.observe(instruction)
            return result
        except Exception as e:
            logger.warning(f"[Attempt {attempt}] Failed: {e}")
            await asyncio.sleep(1)
    return NO_MENU_LINK_FOUND


async def find_menu_link(page, max_retries=3):
    """
    Attempt to locate the restaurant's menu link using Stagehand observe.
    Retries up to `max_retries` times if it fails.
    """
    instruction = (
        "Find the most likely link to the restaurant's menu on this webpage. If the webpage"
        "already is the menu page, return the current page URL. Return only the link URL."
    )

    for attempt in range(1, max_retries + 1):
        try:
            result = await page.observe(instruction)
            return result
        except Exception as e:
            logger.warning(f"[Attempt {attempt}] Failed: {e}")
            await asyncio.sleep(1)
    return NO_MENU_LINK_FOUND


# Normalize URL so that absolute URL path is used (https://docs.stagehand.dev/v3/references/page)
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def main():
    # Configure Stagehand client
    stagehand = Stagehand(
        env="BROWSERBASE",
        model_name="google/gemini-2.0-flash",
        model_api_key=MODEL_API_KEY,
        api_key=BROWSERBASE_API_KEY,
        project_id=BROWSERBASE_PROJECT_ID,
        verbose=2,  # Maximum logging detail for development
        logInferenceToFile=True,  # Writes files to ./inference_summary/ for LLM debugging
    )

    try:
        await stagehand.init()
        page = stagehand.page

        # Get website URL from user
        website_url = normalize_url(get_website_from_user())
        logger.info(f"Navigating to {website_url} ...")
        await page.goto(website_url)

        # Locate restaurant details link with retries
        restaurant_details_link = await get_restaurant_details(page)
        if restaurant_details_link == NO_MENU_LINK_FOUND:
            logger.error(
                "Could not find restaurant details link after multiple attempts."
            )
            return
        logger.info(f"Restaurant details link found: {restaurant_details_link}")

        # Act() on observe() output, avoiding additional LLM call
        await page.act(restaurant_details_link[0])
        await page.extract(
            "Extract as many of the the restaurant's following details: "
            "name, phone number, email, address, hours of operation, social media links",
            schema=model.RestaurantInfo,
        )

        # Locate menu link with retries
        menu_link = await find_menu_link(page)
        if menu_link == NO_MENU_LINK_FOUND:
            logger.error("Could not find menu link after multiple attempts.")
            return

        logger.info(f"Menu link found: {menu_link}")
        # Act() on observe() output, avoiding additional LLM call
        await page.act(menu_link[0])

        # Go to each subsection link (if applicable, i.e. /lunch/dinner/drinks) and extract each section
        sections = await page.observe(
            "Find all subsections on the current menu page, i.e. 'Lunch', 'Dinner', 'Happy Hour', etc."
            "Return them as a list of links. If none found, return the current page link only in a list."
            "Do not return duplicates if a link appears multiple times."
        )

        for section in sections:
            logger.info(f"Navigating to menu section: {section.description} ...")
            await page.act(section)

            await page.extract(
                "Extract all menu sections, item names, descriptions, "
                "and prices from the provided website text. "
                "If categories are unclear, infer reasonable section names. "
                "Preserve price formatting exactly as written."
                "If the page link is a PDF menu, extract from the PDF content.",
                schema=model.Menu,
            )

        # TODO: write output to file or database

    finally:
        await stagehand.close()


if __name__ == "__main__":
    asyncio.run(main())
