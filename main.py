import os
import asyncio
from dotenv import load_dotenv
from stagehand import Stagehand

load_dotenv()
MODEL_API_KEY = os.getenv("MODEL_API_KEY")          
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def get_website_from_user():
    return input("Hello! Please enter a restaurant website URL: ")

async def find_menu_link(page, max_retries=3):
    """
    Attempt to locate the restaurant's menu link using Stagehand observe.
    Retries up to `max_retries` times if it fails.
    """
    instruction = "Task: From the HTML of a restaurant webpage, return the best menu link. " \
    "Rules: (1) Inspect all <a> tags and extract visible text, aria-label, title, alt (from images), " \
    "and href. (2) Lowercase all text and URLs. (3) A link is a candidate if any apply: " \
    "text/label contains 'menu','menus','food','dining','dinner','lunch','brunch','order'," \
    "'takeout'; URL contains those keywords or ends in .pdf/.jpg/.png; URL contains a known menu/" \
    "ordering domain: toasttab, clover, opentable.com/menu, ubereats, doordash, grubhub. (4) " \
    "Ranking priority: (1) URL with 'menu' or 'menus'; (2) PDF files; (3) other food/dining URLs; " \
    "(4) ordering-platform links. (5) Output exactly one thing: the best URL or " \
    "'NO_MENU_LINK_FOUND'. No explanations."


    for attempt in range(1, max_retries + 1):
        try:
            result = await page.observe(instruction)
            return result
        except Exception as e:
            print(f"[Attempt {attempt}] Failed: {e}")
            await asyncio.sleep(1)
    return "Failed to locate menu link after retries"


async def main():
    stagehand = Stagehand(
        env="BROWSERBASE",
        model_name="google/gemini-2.0-flash",
        model_api_key=MODEL_API_KEY,
        api_key=BROWSERBASE_API_KEY,
        project_id=BROWSERBASE_PROJECT_ID,
    )

    try:
        await stagehand.init()
        page = stagehand.page
        
        # Get website URL from user
        website_url = get_website_from_user()
        print(f"Navigating to {website_url} ...")
        await page.goto(website_url)

        # Locate menu link with retries
        menu_link = await find_menu_link(page)
        print("Menu link found:", menu_link)
        if menu_link:
            await page.act(menu_link[0])

    finally:
        await stagehand.close()

if __name__ == "__main__":
    asyncio.run(main())
