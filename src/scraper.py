#!/usr/bin/env python3
"""
High-Performance SSRN Conference Scraper
Fast async scraping with concurrent processing and connection pooling
"""

import asyncio
import aiohttp
import time
import re
import pandas as pd
import requests
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import logging
from dataclasses import dataclass
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ConferenceData:
    title: str = ''
    conference_dates: str = ''
    location: str = ''
    description: str = ''
    ssrn_link: str = ''


class ConferenceScraper:
    """High-performance async SSRN conference scraper"""
    
    def __init__(self, max_concurrent: int = 3, timeout: int = 30):
        self.base_url = "https://www.ssrn.com"
        self.conference_url = "https://www.ssrn.com/index.cfm/en/janda/professional-announcements/?annsNet=203#AnnType_1"
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        # More realistic browser headers to avoid 403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers=headers
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def fetch_page_selenium(self, url: str) -> Optional[str]:
        """Selenium fallback method to bypass Cloudflare protection"""
        driver = None
        try:
            logger.info("🤖 Using Selenium to bypass Cloudflare protection...")
            
            # Set up Chrome options for headless browsing
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Navigate to the page
            logger.info(f"🔄 Loading page: {url}")
            driver.get(url)
            
            # Wait for page to load and handle Cloudflare if present
            try:
                # Wait for either the main content or Cloudflare challenge
                WebDriverWait(driver, 15).until(
                    lambda driver: (
                        driver.find_elements(By.TAG_NAME, "li") or
                        "Just a moment" in driver.page_source or
                        "challenge" in driver.page_source.lower()
                    )
                )
                
                # If Cloudflare challenge is detected, wait longer
                if "Just a moment" in driver.page_source or "challenge" in driver.page_source.lower():
                    logger.info("⏳ Cloudflare challenge detected, waiting...")
                    time.sleep(10)  # Wait for challenge to complete
                    
                    # Wait for actual content
                    WebDriverWait(driver, 20).until(
                        lambda driver: len(driver.find_elements(By.TAG_NAME, "li")) > 0
                    )
                
            except Exception as e:
                logger.warning(f"Timeout waiting for page content: {e}")
            
            # Get page source
            page_source = driver.page_source
            
            # Check if we got actual content
            if len(page_source) > 1000 and "conference" in page_source.lower():
                logger.info("✅ Successfully fetched page using Selenium")
                return page_source
            else:
                logger.warning("Selenium method returned incomplete content")
                return None
                
        except Exception as e:
            logger.error(f"Selenium method failed: {e}")
            return None
        finally:
            if driver:
                driver.quit()

    def fetch_page_sync(self, url: str) -> Optional[str]:
        """Fallback sync method using requests with better session handling"""
        try:
            session = requests.Session()
            
            # Set up headers that mimic a real browser more closely
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            })
            
            # First, visit the main SSRN page to establish session
            logger.info("🔗 Establishing session with SSRN...")
            session.get('https://www.ssrn.com', timeout=30)
            time.sleep(2)
            
            # Now try to get the conference page
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully fetched page using fallback method")
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} from fallback method")
                return None
                
        except Exception as e:
            logger.error(f"Fallback method failed: {e}")
            return None

    async def fetch_page(self, url: str, retry_count: int = 3) -> Optional[str]:
        """Fetch page content with error handling and retry logic"""
        for attempt in range(retry_count):
            try:
                # Add delay between requests to be respectful
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 403:
                        logger.warning(f"HTTP 403 (Forbidden) for {url} - attempt {attempt + 1}")
                        if attempt < retry_count - 1:
                            # Wait longer for 403 errors
                            await asyncio.sleep(5)
                            continue
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {url} - attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Failed to fetch {url} - attempt {attempt + 1}: {e}")
        
        # If async method fails, try Selenium as ultimate fallback
        logger.info("🔄 Trying Selenium fallback method...")
        selenium_result = self.fetch_page_selenium(url)
        if selenium_result:
            return selenium_result
        
        # If Selenium fails, try basic sync method
        logger.info("🔄 Trying basic sync method...")
        return self.fetch_page_sync(url)
    
    def parse_conference_list(self, html_content: str) -> List[BeautifulSoup]:
        """Extract conference elements from main page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        list_items = soup.find_all('li')
        conference_elements = []
        
        for li in list_items:
            text = li.get_text(strip=True)
            link = li.find('a', href=True)
            
            if (link and len(text) > 50 and
                ('Conference Date' in text or 'Conference Dates' in text) and
                ('Location:' in text or 'Posted:' in text)):
                conference_elements.append(li)
                
        return conference_elements
    
    def extract_basic_info(self, element: BeautifulSoup) -> ConferenceData:
        """Extract basic conference information from list element"""
        conference = ConferenceData()
        
        try:
            full_text = element.get_text(separator=' ', strip=True)
            
            # Extract title and link first
            title_link = element.find('a', href=True)
            if title_link:
                conference.title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                if href:
                    conference.ssrn_link = href if href.startswith('http') else urljoin(self.base_url, href)
            
            # Extract conference dates with multiple patterns
            date_patterns = [
                r'Conference Dates?:\s*([^LP\n]+?)(?=\s*Location:|Posted:|$)',  # Match until "Location:" or "Posted:"
                r'Conference Date:\s*([^LP\n]+?)(?=\s*Location:|Posted:|$)',
                r'(\d{1,2}\s+\w+\s+\d{4}\s*[-–]\s*\d{1,2}\s+\w+\s+\d{4})',  # Date ranges
                r'(\d{1,2}\s+\w+\s+\d{4})',  # Single dates
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, full_text, re.IGNORECASE)
                if date_match:
                    # Clean the date string to remove any location info
                    date_str = date_match.group(1).strip()
                    # Remove anything that looks like location (Location: text)
                    date_str = re.sub(r'\s*Location:.*$', '', date_str, flags=re.IGNORECASE)
                    conference.conference_dates = date_str.strip()
                    break
            
            # Extract location with improved patterns
            location_patterns = [
                r'Location:\s*([^P\n]+?)(?=\s*Posted:|$)',  # Match until "Posted:"
                r'Location:\s*\*\*([^*]+)\*\*',
                r'Location:\s*([^,\n]+(?:,\s*[^,\n]+)*?)(?=\s*Posted:|$)',  # Location with comma-separated parts until Posted
                # Try to extract location from structured patterns
                r',\s*([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)*)\s*(?:Posted:|$)',  # City, Country pattern
            ]
            
            for pattern in location_patterns:
                location_match = re.search(pattern, full_text, re.IGNORECASE)
                if location_match:
                    location_str = location_match.group(1).strip()
                    # Clean location to remove "Posted:" if it got included
                    location_str = re.sub(r'\s*Posted:.*$', '', location_str, flags=re.IGNORECASE)
                    # Remove extra whitespace and validate it's not empty
                    location_str = location_str.strip()
                    if location_str and len(location_str) > 2:
                        conference.location = location_str
                        break
            
            # Store basic description (will be enhanced from detail page)
            conference.description = full_text[:500]
                
        except Exception as e:
            logger.error(f"Error extracting basic info: {e}")
            
        return conference
    
    async def get_detailed_info(self, conference_url: str) -> Dict[str, str]:
        """Fetch detailed description from conference page"""
        detailed_info = {
            'description': ''
        }
        
        html_content = await self.fetch_page(conference_url)
        if not html_content:
            return detailed_info
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try to find the main content area
            content_areas = [
                soup.find('article'),
                soup.find('div', class_='main-content'),
                soup.find('div', {'id': 'content'}),
                soup.find('div', class_='content')
            ]
            
            description_parts = []
            
            for content_area in content_areas:
                if not content_area:
                    continue
                    
                # Look for form groups with descriptions
                form_groups = content_area.find_all('div', class_='form-group')
                
                for group in form_groups:
                    h3 = group.find('h3')
                    if not h3:
                        continue
                        
                    h3_text = h3.get_text(strip=True).lower()
                    
                    # Collect all relevant information sections
                    if any(keyword in h3_text for keyword in ['description', 'overview', 'call for papers', 
                                                             'topics', 'scope', 'about', 'details',
                                                             'submission', 'conference', 'additional']):
                        
                        # Get content from div or p tags after h3
                        content_div = group.find('div')
                        if content_div:
                            text = content_div.get_text(separator=' ', strip=True)
                            if text and len(text) > 20:  # Only meaningful content
                                description_parts.append(text)
                        else:
                            p_tag = group.find('p')
                            if p_tag:
                                text = p_tag.get_text(strip=True)
                                if text and len(text) > 20:
                                    description_parts.append(text)
                
                # If we found content, break (use first successful content area)
                if description_parts:
                    break
            
            # If no structured content found, try to get main body text
            if not description_parts:
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    # Remove navigation, header, footer elements
                    for tag in main_content.find_all(['nav', 'header', 'footer', 'script', 'style']):
                        tag.decompose()
                    
                    text = main_content.get_text(separator=' ', strip=True)
                    # Take a reasonable chunk of content
                    if len(text) > 100:
                        description_parts.append(text[:3000])
            
            # Combine all description parts
            if description_parts:
                detailed_info['description'] = ' '.join(description_parts)
                
        except Exception as e:
            logger.error(f"Error parsing detailed info from {conference_url}: {e}")
            
        return detailed_info
    
    async def process_conference_with_details(self, element: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Process a single conference with full details"""
        conference = self.extract_basic_info(element)
        
        if not conference.title or len(conference.title) <= 5:
            return None
            
        # Get detailed description from the conference link
        if conference.ssrn_link:
            detailed_info = await self.get_detailed_info(conference.ssrn_link)
            
            # Use detailed description if available, otherwise keep basic description
            if detailed_info['description'] and len(detailed_info['description']) > len(conference.description):
                conference.description = detailed_info['description']
        
        return {
            'title': conference.title,
            'conference_dates': conference.conference_dates,
            'location': conference.location,
            'description': conference.description,
            'ssrn_link': conference.ssrn_link
        }
    
    async def scrape_conferences(self, fetch_details: bool = True) -> List[Dict[str, str]]:
        """Main scraping method with concurrent processing"""
        logger.info("🚀 Starting conference scraping...")
        start_time = time.time()
        
        # Try to fetch main page with retries
        logger.info(f"📡 Fetching main conference page: {self.conference_url}")
        html_content = await self.fetch_page(self.conference_url, retry_count=5)
        if not html_content:
            logger.error("❌ Failed to fetch main conference page after all retry methods")
            logger.info("💡 All methods failed:")
            logger.info("   - Async aiohttp requests")
            logger.info("   - Selenium with Cloudflare handling")
            logger.info("   - Basic requests session")
            logger.error("🚫 Unable to proceed with automated scraping")
            return []
        
        conference_elements = self.parse_conference_list(html_content)
        logger.info(f"📋 Found {len(conference_elements)} conference elements")
        
        if not fetch_details:
            conferences = []
            for element in conference_elements:
                conference = self.extract_basic_info(element)
                if conference.title and len(conference.title) > 5:
                    conferences.append({
                        'title': conference.title,
                        'conference_dates': conference.conference_dates,
                        'location': conference.location,
                        'description': conference.description,
                        'ssrn_link': conference.ssrn_link
                    })
            return conferences
        
        # Reduce concurrency to be more respectful and avoid 403 errors
        effective_concurrent = min(self.max_concurrent, 3)
        logger.info(f"⚡ Processing with {effective_concurrent} concurrent connections...")
        
        semaphore = asyncio.Semaphore(effective_concurrent)
        
        async def process_with_semaphore(element):
            async with semaphore:
                # Add small delay between requests
                await asyncio.sleep(0.5)
                return await self.process_conference_with_details(element)
        
        tasks = [process_with_semaphore(element) for element in conference_elements]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        conferences = []
        for result in results:
            if isinstance(result, dict) and result:
                conferences.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Scraped {len(conferences)} conferences in {elapsed:.2f}s")
        logger.info(f"📊 Performance: {len(conferences)/elapsed:.2f} conferences/second")
        
        return conferences
    
    def save_to_csv(self, conferences: List[Dict[str, str]], filename: str = "ssrn.csv"):
        """Save conferences to CSV"""
        if not conferences:
            logger.warning("No conferences to save")
            return
            
        df = pd.DataFrame(conferences)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"💾 Saved {len(conferences)} conferences to {filename}")


async def main():
    """Main function for standalone usage"""
    async with ConferenceScraper(max_concurrent=3) as scraper:
        conferences = await scraper.scrape_conferences(fetch_details=True)
        scraper.save_to_csv(conferences)
        logger.info(f"🎉 Successfully scraped {len(conferences)} conferences")


if __name__ == "__main__":
    asyncio.run(main())