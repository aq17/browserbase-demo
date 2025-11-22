import os
import asyncio
from dotenv import load_dotenv
from stagehand import Stagehand

load_dotenv()
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
BROWERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")


async def main():
    stagehand = Stagehand(
        env="BROWSERBASE",
        model_api_key=MODEL_API_KEY,
    )
    await stagehand.init()
    page = stagehand.page
    
    await page.goto("https://google.com")
    
    # # Act on the page
    # await page.act("Click the Google button")
    
    # Extract structured data
    result = await page.extract({
        "instruction": "extract the page title",
        "schema": {
            "title": {
                "type": "string"
            }
        }
    })
    
    print(result["title"])
    await stagehand.close()

if __name__ == "__main__":
    asyncio.run(main())