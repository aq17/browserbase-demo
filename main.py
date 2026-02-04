import os
import asyncio
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from stagehand import Stagehand
import model
from pathlib import Path
from typing import List, Dict, Any

# Define constants
NO_MENU_LINK_FOUND = "NO_MENU_LINK_FOUND"
WEBSITES_FILE = os.getenv("WEBSITES_FILE", "websites.txt")
OUTPUT_DIR = "results"

# Load env variables from .env file
load_dotenv()
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s]: %(message)s",
)
logger = logging.getLogger(__name__)


def load_websites_from_file(file_path: str = WEBSITES_FILE) -> List[str]:
    """
    Load website URLs from a text file.
    Lines starting with # are treated as comments and ignored.
    """
    websites = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    websites.append(normalize_url(line))
        logger.info(f"Loaded {len(websites)} websites from {file_path}")
        return websites
    except FileNotFoundError:
        logger.error(f"File {file_path} not found")
        return []


def ensure_output_directory():
    """Create output directory if it doesn't exist."""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


async def get_restaurant_details(page, max_retries=3):
    """
    Attempt to locate the restaurant's info links using Stagehand observe
    Retries up to `max_retries` times if it fails.
    """
    instruction = (
        "Close any modals or popups that may be blocking the view of the restaurant's detail, you should be starting from the home page of the restaurant."
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


async def process_restaurant(website_url: str, agent_id: int) -> Dict[str, Any]:
    """
    Web agent that processes a single restaurant website.
    This represents a single subprocessor in a production pipeline.

    Args:
        website_url: The restaurant website to scrape
        agent_id: Unique identifier for this agent instance

    Returns:
        Dictionary containing extraction results and metadata
    """
    agent_logger = logging.getLogger(f"Agent-{agent_id}")
    start_time = datetime.now()

    result = {
        "agent_id": agent_id,
        "url": website_url,
        "status": "pending",
        "start_time": start_time.isoformat(),
        "restaurant_info": None,
        "menu_data": [],
        "error": None,
    }

    # Configure Stagehand client for this agent
    stagehand = Stagehand(
        env="BROWSERBASE",
        model_name="google/gemini-2.5-flash",
        model_api_key=MODEL_API_KEY,
        api_key=BROWSERBASE_API_KEY,
        project_id=BROWSERBASE_PROJECT_ID,
        verbose=1,  # Reduced verbosity for parallel execution
    )

    try:
        agent_logger.info(f"Starting extraction for {website_url}")
        await stagehand.init()
        page = stagehand.page

        # Navigate to website
        agent_logger.info(f"Navigating to {website_url}")
        await page.goto(website_url)

        # Extract restaurant details
        restaurant_details_link = await get_restaurant_details(page)
        if restaurant_details_link == NO_MENU_LINK_FOUND:
            agent_logger.warning("Could not find restaurant details link")
        else:
            agent_logger.info(f"Restaurant details link: {restaurant_details_link}")
            await page.act(restaurant_details_link[0])
            restaurant_info = await page.extract(
                "Extract as many of the the restaurant's following details: "
                "name, phone number, email, address, hours of operation, social media links",
                schema=model.RestaurantInfo,
            )
            result["restaurant_info"] = restaurant_info

        # Extract menu data
        menu_link = await find_menu_link(page)
        if menu_link == NO_MENU_LINK_FOUND:
            agent_logger.warning("Could not find menu link")
        else:
            agent_logger.info(f"Menu link: {menu_link}")
            await page.act(menu_link[0])

            # Extract menu sections
            sections = await page.observe(
                "Find all subsections on the current menu page, i.e. 'Lunch', 'Dinner', 'Happy Hour', etc."
                "Return them as a list of links. If none found, return the current page link only in a list."
                "Do not return duplicates if a link appears multiple times."
            )

            for section in sections:
                agent_logger.info(f"Extracting menu section: {section.description}")
                # Ignore iframe links
                if "iframe" in section.description.lower():
                    agent_logger.info("Skipping iframe link")
                    continue

                await page.act(section)

                menu_data = await page.extract(
                    "Extract all menu sections, item names, descriptions, "
                    "and prices from the provided website text. "
                    "If categories are unclear, infer reasonable section names. "
                    "Preserve price formatting exactly as written."
                    "If the page link is a PDF menu, extract from the PDF content.",
                    schema=model.Menu,
                )
                result["menu_data"].append({
                    "section_description": section.description,
                    "data": menu_data
                })

        result["status"] = "success"
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        agent_logger.info(f"Completed extraction in {result['duration_seconds']:.2f}s")

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        agent_logger.error(f"Error processing {website_url}: {e}", exc_info=True)

    finally:
        await stagehand.close()

    return result


def format_restaurant_info(info) -> Dict[str, Any]:
    """Format restaurant info for readable output."""
    if not info or isinstance(info, str):
        return {"error": "No data extracted"}

    formatted = {
        "name": info.restaurant_name,
        "contact": {
            "phone": info.phone_number,
            "email": info.email,
        },
    }

    if info.address:
        formatted["address"] = {
            "street": info.address.street,
            "city": info.address.city,
            "state": info.address.state,
            "postal_code": info.address.postal_code,
            "country": info.address.country,
            "full_address": info.address.full_address,
        }
    else:
        formatted["address"] = None

    if info.hours:
        formatted["hours_of_operation"] = {
            "monday": info.hours.monday,
            "tuesday": info.hours.tuesday,
            "wednesday": info.hours.wednesday,
            "thursday": info.hours.thursday,
            "friday": info.hours.friday,
            "saturday": info.hours.saturday,
            "sunday": info.hours.sunday,
            "notes": info.hours.notes,
        }
    else:
        formatted["hours_of_operation"] = None

    if info.social_links:
        formatted["social_media"] = {
            "website": info.social_links.website,
            "instagram": info.social_links.instagram,
            "facebook": info.social_links.facebook,
            "twitter": info.social_links.twitter_x,
            "tiktok": info.social_links.tiktok,
            "yelp": info.social_links.yelp,
            "google_maps": info.social_links.google_maps,
        }
    else:
        formatted["social_media"] = None

    return formatted


def format_menu_data(menu_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format menu data for readable output."""
    if not menu_data:
        return []

    formatted_menus = []

    for menu_section in menu_data:
        menu_obj = menu_section.get("data")
        if not menu_obj or isinstance(menu_obj, str):
            continue

        formatted_section = {
            "page_section": menu_section.get("section_description", ""),
            "sections": []
        }

        for section in menu_obj.sections:
            formatted_menu_section = {
                "name": section.section_name,
                "categories": []
            }

            for category in section.categories:
                formatted_category = {
                    "name": category.category_name,
                    "items": []
                }

                for item in category.items:
                    formatted_item = {
                        "name": item.name,
                    }
                    if item.description:
                        formatted_item["description"] = item.description
                    if item.price:
                        formatted_item["price"] = item.price

                    formatted_category["items"].append(formatted_item)

                formatted_menu_section["categories"].append(formatted_category)

            formatted_section["sections"].append(formatted_menu_section)

        formatted_menus.append(formatted_section)

    return formatted_menus


def save_result(result: Dict[str, Any]):
    """Save individual agent result to a beautifully formatted JSON file."""
    ensure_output_directory()

    # Create filename from URL
    safe_name = result["url"].replace("https://", "").replace("http://", "")
    safe_name = "".join(c if c.isalnum() or c in ".-" else "_" for c in safe_name)
    filename = f"{OUTPUT_DIR}/agent_{result['agent_id']}_{safe_name}.json"

    # Format the output for readability
    formatted_result = {
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━": None,
        "                     EXTRACTION SUMMARY": None,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ": None,
        "agent_id": result["agent_id"],
        "url": result["url"],
        "status": result["status"],
        "execution": {
            "started_at": result["start_time"],
            "completed_at": result.get("end_time"),
            "duration_seconds": result.get("duration_seconds"),
        },
        "error": result.get("error"),
        "": None,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ": None,
        "                 RESTAURANT INFORMATION": None,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ": None,
        "restaurant": format_restaurant_info(result.get("restaurant_info")),
        "   ": None,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ": None,
        "                        MENU": None,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     ": None,
        "menu": format_menu_data(result.get("menu_data", [])),
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(formatted_result, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved result for agent {result['agent_id']} to {filename}")


async def main():
    """
    Main orchestrator that dispatches parallel web agents.
    Simulates a production system with multiple subprocessors.
    """
    logger.info("=" * 60)
    logger.info("Browserbase Parallel Web Agent Demo")
    logger.info("=" * 60)

    # Load websites from file
    websites = load_websites_from_file()

    if not websites:
        logger.error("No websites to process. Please add URLs to websites.txt")
        return

    logger.info(f"Dispatching {len(websites)} parallel web agents...")

    # Create tasks for parallel execution
    tasks = [
        process_restaurant(url, agent_id=idx)
        for idx, url in enumerate(websites, start=1)
    ]

    # Execute all agents in parallel and gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process and save results
    successful = 0
    failed = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Agent failed with exception: {result}")
            failed += 1
        elif isinstance(result, dict):
            save_result(result)
            if result["status"] == "success":
                successful += 1
            else:
                failed += 1

    # Summary
    logger.info("=" * 60)
    logger.info("Execution Summary")
    logger.info("=" * 60)
    logger.info(f"Total agents: {len(websites)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Results saved to: {OUTPUT_DIR}/")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
