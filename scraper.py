import asyncio
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


logging.basicConfig(level=logging.INFO)


async def accept_cookies(page):
    try:
        await page.goto("https://www.google.com/maps", timeout=30000)
        await page.wait_for_selector("form[action='https://consent.google.com/save'] button", timeout=5000)

        cookies_button = page.locator("form[action='https://consent.google.com/save'] button")
        if await cookies_button.count() > 0:
            await cookies_button.first.click()
            logging.info("Accepted cookies")
    except Exception as e:
        logging.warning(f"Error while trying to accept cookies: {e}")


async def get_listings(page, search_for, total):
    try:
        await page.locator('//input[@id="searchboxinput"]').fill(search_for)
        await page.keyboard.press("Enter")
        await page.wait_for_selector('a[href*="https://www.google.com/maps/place"]', timeout=10000)

        listings = []
        while len(listings) < total:
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(1000)

            current_listings = await page.locator('a[href*="https://www.google.com/maps/place"]').all()
            for listing in current_listings:
                if len(listings) >= total:
                    break
                listings.append(listing)
            
            if len(current_listings) == 0:
                break
        
        logging.info(f"Total Scraped: {len(listings)}")
        return listings[:total]

    except Exception as e:
        logging.error(f"Error scraping listings: {e}")
        return []


async def scrape_business_details(page, listings):
    business_data = []
    for index, listing in enumerate(listings, start=1):
        try:
            business_name = await listing.get_attribute("aria-label")
            await listing.click()
            await page.wait_for_timeout(3000)

            content = await parse_listing_content(page, business_name)
            if content:
                business_data.append({"name": business_name, "content": content})
                logging.info(f"Content for listing {index} ('{business_name}') retrieved successfully")
        except Exception as e:
            logging.error(f"Error occurred while scraping business details for listing {index}: {e}")
    return business_data


async def parse_listing_content(page, business_name):
    try:
        xpath = f'//div[@role="main" and @aria-label="{business_name}"]'
        await page.wait_for_selector(xpath, timeout=5000)
        content = await page.locator(xpath).inner_html()
        soup = BeautifulSoup(content, "html.parser")

        for element in soup.find_all(['script', 'style', 'img', 'link', 'iframe']):
            element.decompose()

        text_content = soup.get_text(separator=' ', strip=True)
        return text_content
    except Exception as e:
        logging.error(f"Error while parsing content for business '{business_name}': {e}")
        return None


async def get_email(page):
    try:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        email = None
        for anchor in soup.find_all("a", href=True):
            if "mailto:" in anchor["href"]:
                email = anchor["href"].replace("mailto:", "")
                break
        return email
    except Exception as e:
        logging.error(f"Error extracting email: {e}")
        return None


async def get_social_media_links(page):
    try:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        social_media_links = {}
        platforms = ["Facebook", "Instagram", "Twitter", "LinkedIn"]
        for anchor in soup.find_all("a", href=True):
            for platform in platforms:
                if platform.lower() in anchor["href"].lower():
                    social_media_links[platform] = anchor["href"]
        return social_media_links
    except Exception as e:
        logging.error(f"Error extracting social media links: {e}")
        return {}


async def visit_business_websites(page, business_data):
    website_url_xpath = '//a[@data-item-id="authority"]'
    for business in business_data:
        try:
            website_url_locator = page.locator(website_url_xpath)
            if await website_url_locator.count() > 0:
                async with page.context.expect_page() as new_page_info:
                    await website_url_locator.first.click()
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("networkidle")

                email = await get_email(new_page)
                social_media_links = await get_social_media_links(new_page)

                business["content"] += f"\nEmail: {email}" if email else ""
                for platform, link in social_media_links.items():
                    business["content"] += f"\n{platform} Link: {link}"

                logging.info(f"Updated content for business: {business['name']}")
        except Exception as e:
            logging.error(f"Error visiting website for business {business['name']}: {e}")


async def main(search_term, quantity):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            await accept_cookies(page)
            listings = await get_listings(page, search_term, quantity)
            if listings:
                business_data = await scrape_business_details(page, listings)
                await visit_business_websites(page, business_data)
                logging.info(f"Final scraped data: {business_data}")
        except Exception as e:
            logging.error(f"Error in main function: {e}")
        finally:
            await browser.close()


def get_google_maps_results(search_term, quantity):
    asyncio.run(main(search_term, quantity))
    return f"Search for '{search_term}' with quantity {quantity} has been completed successfully."
