import os
import asyncio
import logging
from dotenv import load_dotenv
from stagehand import Stagehand
import model
import json
import os

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


def get_website_from_user():
    return input("Hello! Please enter a restaurant website URL: ")


async def find_menu_link(page, max_retries=3):
    """
    Attempt to locate the restaurant's menu link using Stagehand observe.
    Retries up to `max_retries` times if it fails.
    """
    instruction = (
        "Task: From the HTML of a restaurant webpage, return the best menu link. "
        "Rules: (1) Inspect all <a> tags and extract visible text, aria-label, title, alt (from images), "
        "and href. (2) Lowercase all text and URLs. (3) A link is a candidate if any apply: "
        "text/label contains 'menu','menus','food','dining','dinner','lunch','brunch','order',"
        "'takeout'; URL contains those keywords or ends in .pdf/.jpg/.png; URL contains a known menu/"
        "ordering domain: toasttab, clover, opentable.com/menu, ubereats, doordash, grubhub. (4) "
        "Ranking priority: (1) URL with 'menu' or 'menus'; (2) PDF files; (3) other food/dining URLs; "
        "(4) ordering-platform links. (5) Output exactly one thing: the best URL or 'NO_MENU_LINK_FOUND'. "
        "No explanations."
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

        # TODO: extract restaurant name, phone number, address, hours, etc.
        # Define Pydantic schema for structured data extraction

        # Locate menu link with retries
        menu_link = await find_menu_link(page)
        if menu_link == NO_MENU_LINK_FOUND:
            logger.error("Could not find menu link after multiple attempts.")
            return

        # TODO: figure out what this returns and how to extract the menu_link data, in what schema, etc.
        logger.info(f"Menu link found: {menu_link}")
        # Act() on observe() output, avoiding additional LLM call
        await page.act(menu_link[0])

        # Create file to write output to
        # filename = f""

        # go to each subsection link (if applicable, i.e. breakfast/lunch/dinner) and extract each section
        sections = await page.observe("Find all subsection links on the menu page, i.e. 'Lunch', 'Dinner', 'Happy Hour', etc." \
        "and return the list of links. If none found, return the current page link only in a list.")
        for section in sections:
            logger.info(f"Navigating to menu section: {section.description} ...")
            await page.act(section)
            await page.extract(
                "Extract all menu sections, item names, descriptions, "
                "and prices from the provided website text. "
                "If categories are unclear, infer reasonable section names. "
                "Preserve price formatting exactly as written.",
                schema=model.Menu,
            )
        # TODO: write output to file (mimicing a DB write)
    finally:
        await stagehand.close()


if __name__ == "__main__":
    asyncio.run(main())
