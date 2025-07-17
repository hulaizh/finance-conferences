#!/usr/bin/env python3
"""
SSRN Conference Scraper with Selenium
Extracts: title, conference_dates, location, description, ssrn_link
"""

import time
import re
import pandas as pd
from typing import List, Dict
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging

# Silent logging
logging.basicConfig(level=logging.ERROR)


class SSRNConferenceScraper:
    """Simple SSRN Conference Scraper using Selenium"""
    
    def __init__(self):
        self.base_url = "https://www.ssrn.com"
        self.conference_url = "https://www.ssrn.com/index.cfm/en/janda/professional-announcements/?annsNet=203#AnnType_1"
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Set up silent Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def _cleanup(self):
        if self.driver:
            self.driver.quit()
    
    def __del__(self):
        self._cleanup()

    def get_page_content(self, url: str) -> str:
        """Fetch page content using Selenium"""
        self.driver.get(url)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(("tag name", "body"))
        )
        time.sleep(3)
        return self.driver.page_source

    def find_conference_elements(self, soup):
        """Find conference elements in the page"""
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

    def extract_basic_conference_info(self, conference_element) -> Dict[str, str]:
        """Extract basic information from a conference element"""
        conference_data = {
            'title': '',
            'conference_dates': '',
            'location': '',
            'description': '',
            'ssrn_link': ''
        }

        try:
            full_text = conference_element.get_text(separator=' ', strip=True)
            conference_data['description'] = full_text

            title_link = conference_element.find('a', href=True)
            if title_link:
                conference_data['title'] = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                if href:
                    if href.startswith('http'):
                        conference_data['ssrn_link'] = href
                    else:
                        conference_data['ssrn_link'] = urljoin(self.base_url, href)

            date_patterns = [
                r'Conference Dates?:\s*\*\*([^*]+)\*\*',
                r'Conference Date:\s*\*\*([^*]+)\*\*',
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, full_text)
                if date_match:
                    conference_data['conference_dates'] = date_match.group(1).strip()
                    break

            location_match = re.search(r'Location:\s*\*\*([^*]+)\*\*', full_text)
            if location_match:
                conference_data['location'] = location_match.group(1).strip()

        except Exception:
            pass

        return conference_data

    def get_detailed_conference_info(self, conference_url: str) -> Dict[str, str]:
        """Fetch detailed information from individual conference page"""
        detailed_info = {
            'conference_dates': '',
            'location': '',
            'description': ''
        }

        try:
            html_content = self.get_page_content(conference_url)
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the article element containing conference details
            article = soup.find('article')
            if not article:
                return detailed_info

            # Find all form-group divs that contain h3 headers
            form_groups = article.find_all('div', class_='form-group')

            for group in form_groups:
                h3 = group.find('h3')
                if not h3:
                    continue

                h3_text = h3.get_text(strip=True).lower()

                # Extract conference dates
                if 'conference date' in h3_text:
                    p_tag = group.find('p')
                    if p_tag:
                        detailed_info['conference_dates'] = p_tag.get_text(strip=True)

                # Extract location
                elif 'location' in h3_text:
                    p_tag = group.find('p')
                    if p_tag:
                        detailed_info['location'] = p_tag.get_text(strip=True)

                # Extract description
                elif 'description' in h3_text:
                    # Get content from div or p tags after h3
                    content_div = group.find('div')
                    if content_div:
                        detailed_info['description'] = content_div.get_text(separator=' ', strip=True)
                    else:
                        p_tag = group.find('p')
                        if p_tag:
                            detailed_info['description'] = p_tag.get_text(strip=True)

                # Extract additional information and append to description
                elif 'additional information' in h3_text:
                    content_div = group.find('div')
                    if content_div:
                        additional_info = content_div.get_text(separator=' ', strip=True)
                        if detailed_info['description']:
                            detailed_info['description'] += ' ' + additional_info
                        else:
                            detailed_info['description'] = additional_info

            time.sleep(2)

        except Exception:
            pass

        return detailed_info

    def scrape_conferences(self, fetch_details: bool = True) -> List[Dict[str, str]]:
        """Scrape all conferences"""
        try:
            html_content = self.get_page_content(self.conference_url)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            conference_elements = self.find_conference_elements(soup)
            conferences = []

            for element in conference_elements:
                conference_info = self.extract_basic_conference_info(element)
                
                if conference_info['title'] and len(conference_info['title']) > 5:
                    if fetch_details and conference_info['ssrn_link']:
                        detailed_info = self.get_detailed_conference_info(conference_info['ssrn_link'])
                        
                        if detailed_info['conference_dates']:
                            conference_info['conference_dates'] = detailed_info['conference_dates']
                        if detailed_info['location']:
                            conference_info['location'] = detailed_info['location']
                        if detailed_info['description']:
                            conference_info['description'] = detailed_info['description']
                    
                    conferences.append(conference_info)

            return conferences

        except Exception:
            return []

    def save_to_csv(self, conferences: List[Dict[str, str]], filename: str = "./ssrn.csv"):
        """Save conferences to CSV"""
        df = pd.DataFrame(conferences)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Saved {len(conferences)} conferences to {filename}")


def main():
    """Main function"""
    scraper = SSRNConferenceScraper()
    try:
        conferences = scraper.scrape_conferences(fetch_details=True)
        scraper.save_to_csv(conferences)
        print(f"Successfully scraped {len(conferences)} conferences")
    finally:
        scraper._cleanup()


if __name__ == "__main__":
    main()
