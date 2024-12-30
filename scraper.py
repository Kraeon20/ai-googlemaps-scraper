from playwright.async_api import async_playwright, TimeoutError, Page, Locator
from dataclasses import dataclass, asdict, field
import logging
import pandas as pd
import re
import asyncio
from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class Business:
    name: str = ""
    address: str = ""
    website: str = ""
    phone_number: str = ""
    email: str = ""
    facebook: str = ""
    instagram: str = ""
    twitter: str = ""
    linkedin: str = ""


@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)

    def dataframe(self):
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )


async def get_emails(page):
    try:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # Find email pattern
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_matches = re.findall(email_pattern, soup.get_text())
        
        # Remove duplicates by converting the list to a set and back to a list
        email_matches = list(set(email_matches))
        
        if email_matches:
            logging.info(f"Emails found: {', '.join(email_matches)}")
        return email_matches  # Return all found email addresses without duplicates
    except Exception as e:
        logging.error(f"Error while extracting emails: {e}")
        return []
    

async def extract_social_media_links(page: Page):
    """
    Extracts social media links from a webpage using BeautifulSoup.
    """
    social_media_links = {
        "Facebook": None,
        "Instagram": None,
        "Twitter": None,
        "LinkedIn": None
    }
    
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")

    # Look for all <a> tags with href attributes
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "facebook.com" in href and social_media_links["Facebook"] is None:
            social_media_links["Facebook"] = href
        elif "instagram.com" in href and social_media_links["Instagram"] is None:
            social_media_links["Instagram"] = href
        elif "twitter.com" in href and social_media_links["Twitter"] is None:
            social_media_links["Twitter"] = href
        elif "linkedin.com" in href and social_media_links["LinkedIn"] is None:
            social_media_links["LinkedIn"] = href

    # If a social media platform wasn't found, set it to "None"
    for platform in social_media_links:
        if social_media_links[platform] is None:
            social_media_links[platform] = "None"

    logging.info(f"Social media links found: {social_media_links}")
    return social_media_links


async def main(search_term, quantity):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            await accept_cookies(page)
            business_list = BusinessList()

            logging.info(f"Searching for {search_term} with quantity: {quantity}")
            listings = await scrape_listings(page, search_term, quantity)
                
            if not listings:
                logging.warning(f"No listings found for {search_term}")
            else:
                async for business in scrape_business_details(page, listings):
                    business_list.business_list.append(business)

            return business_list
        except Exception as e:
            logging.error(f"An error occurred in the main process: {e}")
            return BusinessList()  
        finally:
            await browser.close()

async def accept_cookies(page):
    try:
        await page.goto("https://www.google.com/maps", timeout=30000)
        await page.wait_for_selector("form[action='https://consent.google.com/save'] button", timeout=5000)

        cookies_button = page.locator("form[action='https://consent.google.com/save'] button")
        if await cookies_button.count() > 0:
            await cookies_button.first.click()
            logging.info("Accepted cookies")
    except TimeoutError:
        logging.warning("Timeout while trying to accept cookies")

async def scrape_listings(page, search_for, total):
    try:
        await page.locator('//input[@id="searchboxinput"]').fill(search_for)
        await page.keyboard.press("Enter")
        await page.wait_for_selector('a[href*="https://www.google.com/maps/place"]', timeout=10000)
        await page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')

        previously_counted = 0
        while True:
            await page.mouse.wheel(0, 10000)
            await page.wait_for_timeout(2000)

            current_count = await page.locator('a[href*="https://www.google.com/maps/place"]').count()
            if current_count >= total:
                listings = await page.locator('a[href*="https://www.google.com/maps/place"]').all()
                listings = listings[:total]  
                logging.info(f"Total Scraped: {len(listings)}")
                return listings
            elif current_count == previously_counted:
                listings = await page.locator('a[href*="https://www.google.com/maps/place"]').all()
                logging.info(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                return listings
            else:
                previously_counted = current_count
                logging.info(f"Currently Scraped: {previously_counted}")
    except Exception as e:
        logging.error(f"Error scraping listings: {e}")
        return []

async def scrape_business_details(page, listings):
    for listing in listings:
        try:
            if listing is None:
                logging.warning("Encountered a NoneType listing. Skipping.")
                continue

            await listing.click()
            await page.wait_for_timeout(2000)  
            business = await extract_business_info(page, listing)
            if business:
                logging.info(f"Extracted business data: {asdict(business)}")
                yield business  
        except Exception as e:
            logging.error(f"Error occurred while scraping business details: {e}")

async def extract_business_info(page: Page, listing: Locator):
    """
    Extract business information from a listing and detailed page.
    """
    name_attribute = 'aria-label'
    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
    website_url_xpath = '//a[@data-item-id="authority"]'


    business = Business()

    try:
        business.name = await listing.get_attribute(name_attribute) or ""
        if not business.name:
            logging.warning("Name not found for the business.")

        address_locator = page.locator(address_xpath)
        website_locator = page.locator(website_xpath)
        phone_number_locator = page.locator(phone_number_xpath)
        website_url_locator = page.locator(website_url_xpath)

        business.address = (
            await address_locator.inner_text() if await address_locator.count() > 0 else ""
        )
        business.website = (
            await website_locator.inner_text() if await website_locator.count() > 0 else ""
        )
        business.phone_number = (
            await phone_number_locator.inner_text() if await phone_number_locator.count() > 0 else ""
        )

        if await website_url_locator.count() > 0:
            try:
                async with page.context.expect_page() as new_page_info:
                    await website_url_locator.first.click()
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("networkidle")

                business.email = await get_emails(new_page)

                social_media_links = await extract_social_media_links(new_page)
                business.facebook = social_media_links.get("Facebook", "None")
                business.instagram = social_media_links.get("Instagram", "None")
                business.twitter = social_media_links.get("Twitter", "None")
                business.linkedin = social_media_links.get("LinkedIn", "None")
            except Exception as e:
                logging.error(f"Error retrieving social media links: {e}")
                business.facebook = business.instagram = business.twitter = business.linkedin = "None"
            finally:
                if new_page:
                    await new_page.close()

        else:
            business.website = None

    except Exception as e:
        logging.error(f"Error retrieving data: {e}")
        return None

    return business


def split_scraped_data(scraped_data, max_length=6000):

    return [
        scraped_data[i:i + max_length]
        for i in range(0, len(scraped_data), max_length)
    ]

def get_google_maps_results(search_term, quantity):
    # Use asyncio.run to create a new event loop for the async function
    asyncio.run(main(search_term, quantity))
    return f"Search for '{search_term}' with quantity {quantity} has been completed successfully."
