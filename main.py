import os
import asyncio
from dotenv import load_dotenv
from stagehand import Stagehand

load_dotenv()
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
BROWERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

def get_website_from_user():
    website = input("Hello! Please enter a restaurant website URL: ")
    return website

async def main():
    try:
        # Initialize Stagehand client
        stagehand = Stagehand(
            env="BROWSERBASE",
            model_api_key=MODEL_API_KEY,
        )
        await stagehand.init()
        page = stagehand.page
        
        # Get a restaurant website URL from the user
        website_url = get_website_from_user()
        await page.goto(website_url)
        
        # Use observe() to find a "menu" link on the website
        menu_link = await page.observe("find the menu link on the page")
        print(menu_link)
        
        # # Extract structured data
        # result = await page.extract({
        #     "instruction": "extract the page title",
        #     "schema": {
        #         "title": {
        #             "type": "string"
        #         }
        #     }
        # })
        
        # print(result["title"])
    finally:
        await stagehand.close()

if __name__ == "__main__":
    asyncio.run(main())