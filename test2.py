import asyncio
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

# Configure logging
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
    business_data = []  # To store the details for each business
    
    for index, listing in enumerate(listings, start=1):
        try:
            # Get the business name from the listing's aria-label attribute
            business_name = await listing.get_attribute("aria-label")
            
            # Click on the business listing
            await listing.click()
            await page.wait_for_timeout(3000)  # Adjust timeout as necessary
            
            # Parse the listing content using the business name
            soup = await parse_listing_content(page, business_name)
            
            if soup:
                logging.info(f"Content for listing {index} ('{business_name}') retrieved successfully")
                
                # Temporarily store the basic business details (name, cleaned content)
                business_details = {
                    "name": business_name,
                    "content": soup,
                    "email": None,
                    "social_media": {}
                }

                # Store business details temporarily
                business_data.append(business_details)

        except Exception as e:
            logging.error(f"Error occurred while scraping business details for listing {index}: {e}")
    
    return business_data


async def parse_listing_content(page, business_name):
    try:
        # Create a dynamic XPath to target the container with role="main" and aria-label matching the business name
        xpath = f'//div[@role="main" and @aria-label="{business_name}"]'
        
        # Wait for the container to load
        await page.wait_for_selector(xpath, timeout=5000)
        
        # Extract the HTML content of the container
        content = await page.locator(xpath).inner_html()
        
        # Parse the extracted content with BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        logging.info(f"Successfully parsed content for business: {business_name}")
        
        # Clean the content: remove all non-text elements
        for element in soup.find_all(['script', 'style', 'img', 'link', 'iframe']):
            element.decompose()  # Removes the element from the soup

        # Remove specific fields
        for field in ["Specialty", "Community Engagement:", "Related Searches:", "Note:", "Last Updated"]:
            for section in soup.find_all(string=field):
                section_element = section.find_parent()
                if section_element:
                    section_element.decompose()

        # Extract the text from the soup
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Print or log the cleaned text content (for debugging purposes)
        print(text_content)  # Display the cleaned text content
        
        return text_content
    except Exception as e:
        logging.error(f"Error while parsing content for business '{business_name}': {e}")
        return None


async def get_email(page):
    try:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # Search for email pattern in the page content
        email = None
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zAZ]{2,}"
        email_match = re.search(email_pattern, soup.get_text())
        if email_match:
            email = email_match.group(0)
        
        return email
    except Exception as e:
        logging.error(f"Error extracting email: {e}")
        return None


async def get_social_media_links(page):
    try:
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        social_media_links = {}

        for link in soup.find_all('a', href=True):
            href = link['href']
            if "facebook.com" in href:
                social_media_links['Facebook'] = href
            elif "instagram.com" in href:
                social_media_links['Instagram'] = href
            elif "twitter.com" in href:
                social_media_links['Twitter'] = href
            elif "linkedin.com" in href:
                social_media_links['LinkedIn'] = href

        return social_media_links
    except Exception as e:
        logging.error(f"Error extracting social media links: {e}")
        return {}


async def visit_business_websites(page, business_data):
    for business_details in business_data:
        try:
            # Get the business name
            business_name = business_details["name"]
            logging.info(f"Visiting website for business: {business_name}")
            
            # Assume you have already found the business website
            website_url_xpath = '//a[@data-item-id="authority"]'
            website_url_locator = page.locator(website_url_xpath)
            
            if await website_url_locator.count() > 0:
                try:
                    async with page.context.expect_page() as new_page_info:
                        await website_url_locator.first.click()
                    new_page = await new_page_info.value
                    await new_page.wait_for_load_state("networkidle")

                    # Extract email and social media links for the business
                    email = await get_email(new_page)
                    social_media_links = await get_social_media_links(new_page)

                    # Update business data with the email and social media links
                    business_details["email"] = email
                    business_details["social_media"] = social_media_links

                    logging.info(f"Updated data for business: {business_name}")
                except Exception as e:
                    logging.error(f"Error visiting website for business {business_name}: {e}")
        except Exception as e:
            logging.error(f"Error handling business {business_name}: {e}")


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

                # Print the updated business data with email and social media links
                for data in business_data:
                    print(f"Updated data for business: {data['name']}")
                    print(f"Email: {data['email']}")
                    print(f"Social Media Links: {data['social_media']}")
                    print(f"Content: {data['content']}")
                    print("="*50)

        except Exception as e:
            logging.error(f"Error in main function: {e}")
        finally:
            await browser.close()


def get_google_maps_results(search_term, quantity):
    # Use asyncio.run to create a new event loop for the async function
    asyncio.run(main(search_term, quantity))
    return f"Search for '{search_term}' with quantity {quantity} has been completed successfully."