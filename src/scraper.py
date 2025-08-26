#!/usr/bin/env python3
"""
Unified High-Performance Conference Scraper and Processor
Combines SSRN scraping with Claude AI processing using configurable settings
"""

import asyncio
import aiohttp
import time
import re
import pandas as pd
import requests
import json
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dataclasses import dataclass
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import configuration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Config will be passed from main module

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ConferenceData:
    title: str = ''
    conference_dates: str = ''
    location: str = ''
    description: str = ''
    ssrn_link: str = ''
    posted_date: str = ''


@dataclass
class ConferenceResult:
    submission_deadline: str = ""
    submission_fees: str = ""
    registration_fees: str = ""
    continent: str = ""


class UnifiedConferenceScraper:
    """Unified scraper that handles both SSRN scraping and Claude AI processing"""
    
    def __init__(self, config_obj=None):
        # Load configuration
        if config_obj is None:
            # For backward compatibility, create a minimal default config
            self.scraper_config = {
                'max_concurrent': 8,
                'timeout': 30,
                'enable_selenium': True,
                'user_agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                'proxies': None
            }
            self.claude_config = {
                'api_url': "https://api.anthropic.com/v1/messages",
                'api_key': "",
                'model': "claude-3-5-sonnet-20241022",
                'max_concurrent': 10,
                'proxies': None
            }
        else:
            self.scraper_config = config_obj.get_scraper_config()
            self.claude_config = config_obj.get_claude_config()
        
        # SSRN scraping settings
        self.base_url = "https://www.ssrn.com"
        # SSRN has conferences on two main pages
        self.conference_urls = [
            "https://www.ssrn.com/index.cfm/en/janda/professional-announcements/?annsNet=203#AnnType_1"
        ]
        self.conference_url = self.conference_urls[0]  # Keep for backward compatibility
        self.max_concurrent = self.scraper_config['max_concurrent']
        # Increase timeout for better SSRN connectivity
        timeout_duration = max(self.scraper_config['timeout'], 60)  # Minimum 60 seconds
        self.timeout = aiohttp.ClientTimeout(total=timeout_duration, connect=30, sock_read=30)
        self.enable_selenium = self.scraper_config['enable_selenium']
        self.session = None
        
        # Claude AI processing settings
        self.max_concurrent_api = self.claude_config['max_concurrent']
        
        # Prompt template for Claude
        self.prompt_template = """Extract specific information. You MUST respond with ONLY valid JSON in this exact format:

{{
  "Submission Deadline": "",
  "Submission Fees": "",
  "Registration Fees": "",
  "Continent": ""
}}

DETAILED EXTRACTION RULES:

1. Submission Deadline: 
   - Search thoroughly in BOTH title and description for the deadline
   - Format as YYYY/MM/DD when possible, otherwise preserve original format
   - Use "" ONLY if absolutely no deadline information exists

2. Submission Fees or Registration Fees:
   - Search for ANY mention of fees related to paper/abstract submission or conference registration/attendance
   - Include full amount with currency like "$50", "€75", "¥5000", "CHF 60", "CAD $50", "Free", "No fee"
   - Use "" only if no fee information is mentioned anywhere

3. Continent:
   - Based on location, return exactly one of: Asia, Australia, Europe, North America, South America, Africa
   - Use geographical knowledge for countries/cities

Conference Information:
Title: {title}
Location: {location}
Full Description: {description}

CRITICAL INSTRUCTIONS:
- Return ONLY the JSON object with exactly four fields
- No explanations, no additional text, no markdown formatting"""
    
    def _clean_field(self, value: str) -> str:
        """Clean field values to handle nan, null, empty cases"""
        if not value or str(value).lower() in ['nan', 'null', 'none', 'n/a']:
            return ''
        return str(value).strip()
    
    def _normalize_for_comparison(self, text: str) -> str:
        """Normalize text for comparison by removing special characters and extra spaces"""
        import re
        if not text:
            return ""
        # Convert to lowercase, remove special chars, normalize spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', str(text).lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _create_conference_signature(self, conference_data: Dict[str, str]) -> str:
        """Create a unique signature for conference comparison"""
        title = self._normalize_for_comparison(conference_data.get('title', ''))
        location = self._normalize_for_comparison(conference_data.get('location', ''))
        dates = self._normalize_for_comparison(conference_data.get('conference_dates', ''))
        return f"{title}|{location}|{dates}"
    
    def _load_existing_conferences(self, file_path: str) -> set:
        """Load existing conferences from JSON and create signatures for comparison"""
        existing_signatures = set()
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                conferences = data.get('conferences', [])
                logger.info(f"Loaded {len(conferences)} existing conferences from {file_path}")
                
                for conf in conferences:
                    conference_data = {
                        'title': str(conf.get('title', '')),
                        'location': str(conf.get('location', '')),
                        'conference_dates': str(conf.get('conference_dates', ''))
                    }
                    signature = self._create_conference_signature(conference_data)
                    if signature:
                        existing_signatures.add(signature)
                        
                logger.info(f"Created {len(existing_signatures)} signatures from existing conferences")
            else:
                logger.info(f"No existing conference file found at {file_path}")
        except Exception as e:
            logger.warning(f"Failed to load existing conferences: {e}")
        
        return existing_signatures
    
    def _save_conferences_to_json(self, conferences: List[Dict[str, str]], file_path: str):
        """Save conferences to JSON with metadata"""
        try:
            # Load existing data if file exists
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {
                    'metadata': {
                        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'total_conferences': 0,
                        'last_updated': None
                    },
                    'conferences': []
                }
            
            # Add new conferences
            existing_signatures = set()
            for existing_conf in data['conferences']:
                signature = self._create_conference_signature(existing_conf)
                existing_signatures.add(signature)
            
            new_count = 0
            for conference in conferences:
                signature = self._create_conference_signature(conference)
                if signature not in existing_signatures:
                    data['conferences'].append(conference)
                    existing_signatures.add(signature)
                    new_count += 1
            
            # Update metadata
            data['metadata']['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
            data['metadata']['total_conferences'] = len(data['conferences'])
            
            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {new_count} new conferences to {file_path}")
            logger.info(f"Total conferences in JSON: {len(data['conferences'])}")
            
        except Exception as e:
            logger.error(f"Failed to save conferences to JSON: {e}")
    
    async def __aenter__(self):
        # Set up HTTP session with proxy support
        connector_kwargs = {
            'limit': 50,
            'limit_per_host': 15,
            'ttl_dns_cache': 300,
            'use_dns_cache': True,
        }
        
        connector = aiohttp.TCPConnector(**connector_kwargs)
        
        # Set up headers
        headers = {
            'User-Agent': self.scraper_config['user_agent'],
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
        
        session_kwargs = {
            'connector': connector,
            'timeout': self.timeout,
            'headers': headers
        }
        
        # Add proxy configuration if available
        proxies = self.scraper_config.get('proxies')
        if proxies:
            # For aiohttp, we need to handle proxies differently
            logger.info(f"Using proxy: {proxies}")
        
        self.session = aiohttp.ClientSession(**session_kwargs)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def fetch_page(self, url: str, retry_count: int = 2) -> Optional[str]:
        """Fetch page content using Selenium directly (faster and more reliable than async)"""
        logger.info(f"Fetching: {url}")
        
        # Try Selenium first (most reliable for SSRN)
        if self.enable_selenium:
            selenium_result = self.fetch_page_selenium(url)
            if selenium_result:
                return selenium_result
        
        # Fallback to sync requests if Selenium fails
        logger.info("Selenium failed, trying sync method...")
        return self.fetch_page_sync(url)
    
    def fetch_page_selenium(self, url: str) -> Optional[str]:
        """Selenium fallback method with enhanced stability"""
        driver = None
        try:
            logger.info("Initializing Selenium WebDriver...")
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f'--user-agent={self.scraper_config["user_agent"]}')
            
            # Add proxy support for Selenium if configured
            proxies = self.scraper_config.get('proxies')
            if proxies and proxies.get('http'):
                proxy_url = proxies['http']
                chrome_options.add_argument(f'--proxy-server={proxy_url}')
                logger.info(f"Using proxy: {proxy_url}")
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(90)  # Increase timeout
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info(f"Loading SSRN page: {url}")
            driver.get(url)
            
            logger.info("Waiting for page content...")
            try:
                # Wait for either content or challenge page
                WebDriverWait(driver, 20).until(
                    lambda d: (
                        len(d.find_elements(By.TAG_NAME, "li")) > 10 or
                        "Just a moment" in d.page_source or
                        "challenge" in d.page_source.lower() or
                        "cloudflare" in d.page_source.lower()
                    )
                )
                
                # Handle Cloudflare challenge
                if any(keyword in driver.page_source.lower() for keyword in ["just a moment", "challenge", "cloudflare"]):
                    logger.info("Cloudflare challenge detected...")
                    time.sleep(15)  # Give more time for challenge
                    
                    # Wait for the actual content
                    WebDriverWait(driver, 30).until(
                        lambda d: len(d.find_elements(By.TAG_NAME, "li")) > 10
                    )
                    logger.info("Challenge resolved")
                
            except Exception as e:
                logger.warning(f"Page load timeout: {e}")
                logger.info("Proceeding with available content...")
            
            page_source = driver.page_source
            
            # Enhanced content validation
            li_elements = driver.find_elements(By.TAG_NAME, "li")
            logger.info(f"Found {len(li_elements)} list items")
            
            if len(page_source) > 5000 and len(li_elements) > 5:
                logger.info(f"Fetched SSRN page ({len(page_source)} chars)")
                return page_source
            else:
                logger.warning(f"Page content incomplete: {len(page_source)} chars")
                logger.debug(f"Page preview: {page_source[:500]}...")
                return page_source if len(page_source) > 1000 else None
                
        except Exception as e:
            logger.error(f"Selenium failed: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("Selenium driver closed")
                except:
                    pass
    
    def fetch_page_sync(self, url: str) -> Optional[str]:
        """Fallback sync method using requests"""
        try:
            session = requests.Session()
            
            session.headers.update({
                'User-Agent': self.scraper_config['user_agent'],
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
            
            # Add proxy support
            proxies = self.scraper_config.get('proxies')
            if proxies:
                session.proxies.update(proxies)
            
            logger.info("Establishing session...")
            session.get('https://www.ssrn.com', timeout=30)
            time.sleep(2)
            
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                logger.info("Fetched page using fallback method")
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} from fallback method")
                return None
                
        except Exception as e:
            logger.error(f"Fallback method failed: {e}")
            return None
    
    def parse_conference_list(self, html_content: str) -> List[BeautifulSoup]:
        """Extract conference elements from main page with improved pattern matching"""
        soup = BeautifulSoup(html_content, 'html.parser')
        list_items = soup.find_all('li')
        conference_elements = []
        
        logger.info(f"Analyzing {len(list_items)} list items...")
        
        # Multiple patterns to detect conferences - more flexible approach
        conference_patterns = [
            # Original strict pattern
            lambda text, link: (
                link and len(text) > 50 and
                ('Conference Date' in text or 'Conference Dates' in text) and
                ('Location:' in text or 'Posted:' in text)
            ),
            # More flexible date patterns
            lambda text, link: (
                link and len(text) > 40 and
                any(date_word in text for date_word in ['Conference Date', 'Conference Dates', 'Date:', 'Dates:']) and
                any(loc_word in text for loc_word in ['Location:', 'Location', 'Posted:', 'Venue:'])
            ),
            # Conference keywords with link
            lambda text, link: (
                link and len(text) > 30 and
                any(conf_word in text.lower() for conf_word in ['conference', 'symposium', 'workshop', 'summit', 'meeting']) and
                any(info_word in text for info_word in ['Location', 'Date', 'Posted', 'Call for', 'Deadline'])
            ),
            # Financial/academic conference indicators
            lambda text, link: (
                link and len(text) > 30 and
                any(fin_word in text.lower() for fin_word in ['finance', 'economic', 'business', 'banking', 'accounting', 'management']) and
                any(date_pattern in text for date_pattern in ['2024', '2025', '2026', 'Date', 'Posted'])
            ),
            # Minimum viable conference (has link + reasonable length + some indicators)
            lambda text, link: (
                link and len(text) > 25 and
                ('http' in str(link.get('href', '')) or 'ssrn.com' in str(link.get('href', ''))) and
                any(indicator in text.lower() for indicator in ['call for papers', 'submission', 'conference', 'abstract', 'deadline'])
            )
        ]
        
        for li in list_items:
            text = li.get_text(strip=True)
            link = li.find('a', href=True)
            
            # Try each pattern
            for i, pattern in enumerate(conference_patterns):
                if pattern(text, link):
                    conference_elements.append(li)
                    logger.debug(f"✓ Pattern {i+1} matched: {text[:80]}...")
                    break
        
        # Remove duplicates while preserving order
        seen = set()
        unique_elements = []
        for element in conference_elements:
            element_text = element.get_text(strip=True)
            if element_text not in seen:
                seen.add(element_text)
                unique_elements.append(element)
        
        logger.info(f"Found {len(unique_elements)} unique conferences")
        
        
        return unique_elements
    
    def extract_basic_info(self, element: BeautifulSoup) -> ConferenceData:
        """Extract basic conference information from list element with enhanced patterns"""
        conference = ConferenceData()
        
        try:
            full_text = element.get_text(separator=' ', strip=True)
            
            # Extract title and link
            title_link = element.find('a', href=True)
            if title_link:
                conference.title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                if href:
                    conference.ssrn_link = href if href.startswith('http') else urljoin(self.base_url, href)
            else:
                # Fallback: try to extract title from beginning of text
                lines = full_text.split('\n')
                if lines:
                    potential_title = lines[0].strip()
                    if len(potential_title) > 10 and len(potential_title) < 200:
                        conference.title = potential_title
            
            # Enhanced date extraction patterns
            date_patterns = [
                # Standard SSRN patterns
                r'Conference Dates?:\s*([^LP\n]+?)(?=\s*Location:|Posted:|$)',
                r'Conference Date:\s*([^LP\n]+?)(?=\s*Location:|Posted:|$)',
                # Date range patterns
                r'(\d{1,2}\s+\w+\s+\d{4}\s*[-–]\s*\d{1,2}\s+\w+\s+\d{4})',
                r'(\w+\s+\d{1,2}\s*[-–]\s*\d{1,2},?\s+\d{4})',
                r'(\w+\s+\d{1,2},?\s+\d{4}\s*[-–]\s*\w+\s+\d{1,2},?\s+\d{4})',
                # Single date patterns
                r'(\d{1,2}\s+\w+\s+\d{4})',
                r'(\w+\s+\d{1,2},?\s+\d{4})',
                # Flexible date patterns
                r'Date[s]?:\s*([^L\n]+?)(?=\s*Location:|Posted:|$)',
                r'When:\s*([^L\n]+?)(?=\s*Location:|Posted:|$)',
                # ISO date patterns
                r'(\d{4}-\d{2}-\d{2}(?:\s*to\s*\d{4}-\d{2}-\d{2})?)',
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, full_text, re.IGNORECASE)
                if date_match:
                    date_str = date_match.group(1).strip()
                    # Clean up the date string
                    date_str = re.sub(r'\s*Location:.*$', '', date_str, flags=re.IGNORECASE)
                    date_str = re.sub(r'\s*Posted:.*$', '', date_str, flags=re.IGNORECASE)
                    date_str = date_str.strip()
                    if date_str and len(date_str) > 4:  # Must have some meaningful content
                        conference.conference_dates = date_str
                        break
            
            # Enhanced location extraction patterns
            location_patterns = [
                # Standard SSRN patterns
                r'Location:\s*([^P\n]+?)(?=\s*Posted:|$)',
                r'Location:\s*\*\*([^*]+)\*\*',
                r'Location:\s*([^,\n]+(?:,\s*[^,\n]+)*?)(?=\s*Posted:|$)',
                # Alternative location indicators
                r'Venue:\s*([^P\n]+?)(?=\s*Posted:|$)',
                r'Where:\s*([^P\n]+?)(?=\s*Posted:|$)',
                r'Place:\s*([^P\n]+?)(?=\s*Posted:|$)',
                # Extract locations from title patterns - many conferences have location in title
                r'\b(\w+(?:\s+\w+)*),\s+(\w+(?:\s+\w+)*),\s+(\d{2}-\d{2}\s+\w+\s+\d{4})',  # "City, Country, Date" 
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z][A-Z]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',  # "City, COUNTRY" or "City, Country"
                r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z][A-Z]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*))\s*[-–]',  # "in City, Country -"
                r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Conference\s+(?:Date|Dates)',  # "City Conference Date"
                # Country-specific patterns
                r'\b(Utah)\b',  # Utah
                r'\b(Venice)\b',  # Venice
                r'\b(Notre Dame)\b',  # Notre Dame (implies Indiana, USA)
                r'(VILNIUS,\s*LITHUANIA)',  # Vilnius, Lithuania
                r'(Seoul,\s*Korea)',  # Seoul, Korea
                r'(Moscow(?:\s+and\s+Online)?)',  # Moscow
                r'(East\s+Lansing,\s*MI)',  # East Lansing, MI
                r'(Dubai)',  # Dubai
                # University-based patterns
                r'University\s+of\s+([^,\n]+?)(?=\s*Posted:|Conference|$)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+University)(?=\s*Conference|Posted|$)',
                # City, Country patterns
                r',\s*([A-Za-z\s]+(?:,\s*[A-Za-z\s]+)*)\s*(?:Posted:|$)',
                # Generic city/country patterns at end of line
                r'([A-Za-z\s]+,\s*[A-Za-z\s]+)\s*(?:Posted:|$)',
            ]
            
            # Expand known abbreviated locations (define once, use in multiple places)
            location_expansions = {
                'Utah': 'Utah, USA',
                'Notre Dame': 'Notre Dame, IN, USA',
                'Venice': 'Venice, Italy',
                'Dubai': 'Dubai, UAE',
                'Moscow': 'Moscow, Russia'
            }
            
            for pattern in location_patterns:
                location_match = re.search(pattern, full_text, re.IGNORECASE)
                if location_match:
                    # Handle patterns that might have multiple groups
                    if len(location_match.groups()) > 1:
                        # For patterns like "City, Country" - combine groups
                        location_str = ', '.join([g for g in location_match.groups() if g]).strip()
                    else:
                        location_str = location_match.group(1).strip()
                    
                    # Clean up the location string
                    location_str = re.sub(r'\s*Posted:.*$', '', location_str, flags=re.IGNORECASE)
                    location_str = re.sub(r'\s*Conference.*$', '', location_str, flags=re.IGNORECASE)
                    location_str = re.sub(r'\s*Date[s]?:.*$', '', location_str, flags=re.IGNORECASE)
                    location_str = location_str.strip()
                    
                    if location_str in location_expansions:
                        location_str = location_expansions[location_str]
                    
                    if location_str and len(location_str) > 2 and len(location_str) < 100:
                        conference.location = location_str
                        logger.debug(f"Extracted location: '{location_str}' using pattern: {pattern}")
                        break
            
            # If still no location, try extracting from title itself
            if not conference.location or conference.location == 'nan':
                title_location_patterns = [
                    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s+([A-Z]{2,}|[A-Z][a-z]+)\b',  # "City, COUNTRY"
                    r'\b(Utah)\s+Winter\s+Finance',  # Utah Winter Finance
                    r'Conference\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "Conference in City"
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Conference',  # "City Conference"
                    r'\b(VILNIUS,\s*LITHUANIA)',  # Special case for Vilnius
                ]
                
                for pattern in title_location_patterns:
                    title_match = re.search(pattern, conference.title, re.IGNORECASE)
                    if title_match:
                        if len(title_match.groups()) > 1:
                            location_str = ', '.join([g for g in title_match.groups() if g]).strip()
                        else:
                            location_str = title_match.group(1).strip()
                        
                        # Apply expansions
                        if location_str in location_expansions:
                            location_str = location_expansions[location_str]
                        
                        if location_str and len(location_str) > 2:
                            conference.location = location_str
                            logger.debug(f"Extracted location from title: '{location_str}'")
                            break
            
            # Extract posted date
            posted_patterns = [
                r'Posted:\s*(\d{1,2}\s+\w+\s+\d{4})',
                r'Posted:\s*(\d{1,2}-\d{1,2}-\d{4})',
                r'Posted:\s*(\d{4}-\d{2}-\d{2})',
                r'Posted:\s*(\w+\s+\d{1,2},?\s+\d{4})'
            ]
            
            for pattern in posted_patterns:
                posted_match = re.search(pattern, full_text, re.IGNORECASE)
                if posted_match:
                    conference.posted_date = posted_match.group(1).strip()
                    break
            
            # Extract meaningful description from the main listing
            # Look for content after the posted date that contains useful information
            desc_parts = []
            
            # Try to extract call for papers info, deadlines, etc.
            useful_patterns = [
                r'Call for [Pp]apers[:\s]+([^\.]{20,200})',
                r'[Aa]bstract[s]?\s+[Dd]eadline[:\s]+([^\.]{10,100})',
                r'[Ss]ubmission[s]?\s+[Dd]eadline[:\s]+([^\.]{10,100})',
                r'[Pp]aper[s]?\s+[Dd]ue[:\s]+([^\.]{10,100})',
                r'[Rr]egistration[:\s]+([^\.]{10,100})',
                r'[Ff]ee[s]?[:\s]+([^\.]{5,50})',
                r'[Tt]opic[s]?[:\s]+([^\.]{20,150})',
                r'[Cc]onference\s+[Ff]ee[:\s]+([^\.]{5,50})'
            ]
            
            for pattern in useful_patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    desc_part = match.group(1).strip()
                    if len(desc_part) > 10 and desc_part not in desc_parts:
                        desc_parts.append(desc_part)
            
            # If we found useful parts, combine them
            if desc_parts:
                conference.description = '. '.join(desc_parts[:3])  # Limit to 3 parts
                if len(conference.description) > 500:
                    conference.description = conference.description[:500] + "..."
            else:
                # Fallback to cleaned up version of full text
                clean_text = re.sub(r'Posted:\s*\d+\s+\w+\s+\d{4}', '', full_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                conference.description = clean_text[:300] + "..." if len(clean_text) > 300 else clean_text
            
            # Log extraction results for debugging
            logger.debug(f"Extracted - Title: '{conference.title}', Dates: '{conference.conference_dates}', Location: '{conference.location}', Posted: '{conference.posted_date}'")
                
        except Exception as e:
            logger.error(f"Error extracting basic info: {e}")
            logger.debug(f"Problem text: {full_text[:200]}...")
            
        return conference
    
    def get_detailed_info(self, conference_url: str) -> Dict[str, str]:
        """Fetch detailed description from conference page"""
        detailed_info = {'description': ''}
        
        html_content = self.fetch_page(conference_url)
        if not html_content:
            return detailed_info
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
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
                    
                form_groups = content_area.find_all('div', class_='form-group')
                
                for group in form_groups:
                    h3 = group.find('h3')
                    if not h3:
                        continue
                        
                    h3_text = h3.get_text(strip=True).lower()
                    
                    if any(keyword in h3_text for keyword in ['description', 'overview', 'call for papers', 
                                                             'topics', 'scope', 'about', 'details',
                                                             'submission', 'conference', 'additional']):
                        
                        content_div = group.find('div')
                        if content_div:
                            text = content_div.get_text(separator=' ', strip=True)
                            if text and len(text) > 20:
                                description_parts.append(text)
                        else:
                            p_tag = group.find('p')
                            if p_tag:
                                text = p_tag.get_text(strip=True)
                                if text and len(text) > 20:
                                    description_parts.append(text)
                
                if description_parts:
                    break
            
            if not description_parts:
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    for tag in main_content.find_all(['nav', 'header', 'footer', 'script', 'style']):
                        tag.decompose()
                    
                    text = main_content.get_text(separator=' ', strip=True)
                    if len(text) > 100:
                        description_parts.append(text[:3000])
            
            if description_parts:
                detailed_info['description'] = ' '.join(description_parts)
                
        except Exception as e:
            logger.error(f"Error parsing detailed info from {conference_url}: {e}")
            
        return detailed_info
    
    async def call_claude_api(self, title: str, location: str, description: str, 
                              retry_count: int = 3) -> ConferenceResult:
        """Call Claude API with retry logic"""
        
        prompt = self.prompt_template.format(
            title=title,
            location=location,
            description=description[:2000]
        )
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.claude_config['api_key'],
            'anthropic-version': '2023-06-01'
        }
        
        payload = {
            "model": self.claude_config['model'],
            "max_tokens": 500,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        for attempt in range(retry_count):
            try:
                # Use synchronous requests to avoid aiohttp header conflicts
                import requests
                
                request_kwargs = {
                    'headers': headers,
                    'json': payload,
                    'timeout': 30
                }
                
                # Add proxy support
                proxies = self.claude_config.get('proxies')
                if proxies:
                    request_kwargs['proxies'] = proxies
                
                response = requests.post(self.claude_config['api_url'], **request_kwargs)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['content'][0]['text'].strip()
                    
                    parsed_result = self._parse_json_response(content)
                    return parsed_result
                
                elif response.status_code == 429:
                    wait_time = min(2 ** attempt, 16)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                else:
                    logger.error(f"Claude API error {response.status_code}: {response.text}")
                    
            except requests.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Claude API call failed on attempt {attempt + 1}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"Failed to process conference after {retry_count} attempts")
        return ConferenceResult()
    
    def _parse_json_response(self, content: str) -> ConferenceResult:
        """Parse JSON response with robust fallback handling"""
        content = content.strip()
        
        if content.startswith('```') and content.endswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1])
        elif content.startswith('```json') and content.endswith('```'):
            content = content[7:-3].strip()
        
        try:
            data = json.loads(content)
            return ConferenceResult(
                submission_deadline=self._clean_field(data.get('Submission Deadline', '')),
                submission_fees=self._clean_field(data.get('Submission Fees', '')),
                registration_fees=self._clean_field(data.get('Registration Fees', '')),
                continent=self._clean_field(data.get('Continent', ''))
            )
        except json.JSONDecodeError:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != 0:
                try:
                    json_str = content[start:end]
                    data = json.loads(json_str)
                    return ConferenceResult(
                        submission_deadline=self._clean_field(data.get('Submission Deadline', '')),
                        submission_fees=self._clean_field(data.get('Submission Fees', '')),
                        registration_fees=self._clean_field(data.get('Registration Fees', '')),
                        continent=self._clean_field(data.get('Continent', ''))
                    )
                except json.JSONDecodeError:
                    pass
            
            try:
                result = ConferenceResult()
                
                deadline_match = re.search(r'"Submission Deadline":\s*"([^"]*)"', content)
                if deadline_match:
                    result.submission_deadline = self._clean_field(deadline_match.group(1))
                
                sub_fee_match = re.search(r'"Submission Fees":\s*"([^"]*)"', content)
                if sub_fee_match:
                    result.submission_fees = self._clean_field(sub_fee_match.group(1))
                
                reg_fee_match = re.search(r'"Registration Fees":\s*"([^"]*)"', content)
                if reg_fee_match:
                    result.registration_fees = self._clean_field(reg_fee_match.group(1))
                
                continent_match = re.search(r'"Continent":\s*"([^"]*)"', content)
                if continent_match:
                    result.continent = self._clean_field(continent_match.group(1))
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to parse with regex fallback: {e}")
            
            logger.warning(f"Failed to parse JSON response: {content[:200]}...")
            return ConferenceResult()
    
    def process_conference_with_details(self, element: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Process a single conference with detailed description fetching for better Claude API results"""
        conference = self.extract_basic_info(element)
        
        if not conference.title or len(conference.title) <= 5:
            return None
        
        # Filter out conferences without dates as requested
        if not conference.conference_dates or conference.conference_dates.strip() == '' or conference.conference_dates == 'nan':
            logger.info(f"Filtering out conference without dates: {conference.title[:60]}...")
            return None
        
        # Fetch detailed description from individual conference page
        # This is crucial for Claude API to find deadline and fee information
        detailed_description = conference.description  # Fallback to basic description
        
        if conference.ssrn_link:
            try:
                logger.info(f"Fetching detailed description for: {conference.title[:50]}...")
                detailed_info = self.get_detailed_info(conference.ssrn_link)
                if detailed_info.get('description'):
                    detailed_description = detailed_info['description']
                    logger.info(f"Fetched detailed description ({len(detailed_description)} chars)")
                else:
                    logger.warning(f"No detailed description found, using basic description")
            except Exception as e:
                logger.warning(f"Failed to fetch detailed description: {e}, using basic description")
        
        return {
            'title': conference.title,
            'conference_dates': conference.conference_dates,
            'location': conference.location,
            'description': detailed_description,
            'ssrn_link': conference.ssrn_link,
            'posted_date': conference.posted_date
        }
    
    def get_all_conference_pages(self) -> tuple[List[str], Dict[str, str]]:
        """Get both SSRN conference page URLs and fetch their content"""
        # Start with the two main conference pages
        urls = self.conference_urls.copy()
        page_contents = {}
        
        logger.info(f"SSRN has conferences on {len(urls)} main pages")
        for i, url in enumerate(urls):
            logger.info(f"   Page {i+1}: {url}")
        
        # Fetch content from both main pages
        for i, url in enumerate(urls):
            try:
                logger.info(f"Fetching page {i+1}/{len(urls)}")
                html_content = self.fetch_page(url)
                if html_content:
                    page_contents[url] = html_content
                    logger.info(f"Fetched page {i+1} ({len(html_content)} chars)")
                    
                    # Check for additional pagination within each page
                    soup = BeautifulSoup(html_content, 'html.parser')
                    pagination_selectors = [
                        'a[href*="page="]',  # ?page=2, ?page=3, etc.
                        'a[href*="offset="]',  # ?offset=20, ?offset=40, etc.
                        'a[href*="start="]',  # ?start=20, ?start=40, etc.
                        '.pagination a',
                        '.pager a'
                    ]
                    
                    pagination_links = set()
                    for selector in pagination_selectors:
                        try:
                            links = soup.select(selector)
                            for link in links:
                                if link.get('href'):
                                    pagination_links.add(link.get('href'))
                        except Exception as e:
                            logger.debug(f"Error with selector {selector}: {e}")
                    
                    # Add pagination URLs if found
                    for link in pagination_links:
                        if link.startswith('http'):
                            full_url = link
                        else:
                            full_url = urljoin(self.base_url, link)
                        
                        if ('professional-announcements' in full_url or 'announcement' in full_url) and full_url not in urls:
                            urls.append(full_url)
                            logger.info(f"Found additional page: {full_url}")
                else:
                    logger.warning(f"Failed to fetch page {i+1}: {url}")
                    
            except Exception as e:
                logger.error(f"Error fetching page {i+1}: {e}")
        
        if len(page_contents) == 0:
            logger.error("Failed to fetch any conference pages")
            return urls, {}
        
        logger.info(f"Fetched {len(page_contents)}/{len(urls)} pages")
        return urls, page_contents

    def scrape_conferences(self, fetch_details: bool = True, existing_conferences_file: str = "output/ssrn.json") -> List[Dict[str, str]]:
        """Optimized scraping method - first compare at list level, then fetch details only for new conferences"""
        logger.info("Starting optimized conference scraping...")
        start_time = time.time()
        
        # Load existing conferences for comparison
        existing_signatures = self._load_existing_conferences(existing_conferences_file)
        
        # Get basic info from SSRN pages (fast)
        logger.info("Extracting basic conference info from SSRN pages...")
        all_urls, page_contents = self.get_all_conference_pages()
        
        all_conference_elements = []
        
        # Process all pre-fetched pages to get basic info
        for i, (url, content) in enumerate(page_contents.items(), 1):
            logger.info(f"Processing page {i}/{len(page_contents)}")
            page_elements = self.parse_conference_list(content)
            logger.info(f"Found {len(page_elements)} elements on page {i}")
            all_conference_elements.extend(page_elements)
        
        # Process any additional pages
        remaining_urls = [url for url in all_urls if url not in page_contents]
        for i, url in enumerate(remaining_urls):
            page_num = len(page_contents) + i + 1
            logger.info(f"📡 Fetching additional page {page_num}/{len(all_urls)}: {url}")
            html_content = self.fetch_page(url)
            if not html_content:
                logger.warning(f"Failed to fetch page {page_num}")
                continue
            
            page_elements = self.parse_conference_list(html_content)
            logger.info(f"Found {len(page_elements)} elements on page {page_num}")
            all_conference_elements.extend(page_elements)
        
        if not all_conference_elements:
            logger.error("No conference elements found")
            return []
        
        # Extract basic info and filter for new conferences only
        logger.info("Comparing with existing conferences...")
        new_elements = []
        existing_count = 0
        
        for element in all_conference_elements:
            conference = self.extract_basic_info(element)
            if not conference.title or len(conference.title) <= 5:
                continue
                
            # Create signature for comparison
            conference_data = {
                'title': conference.title,
                'location': conference.location,
                'conference_dates': conference.conference_dates
            }
            signature = self._create_conference_signature(conference_data)
            
            if signature in existing_signatures:
                existing_count += 1
                logger.debug(f"Existing conference: {conference.title[:50]}...")
            else:
                new_elements.append(element)
                logger.debug(f"New conference: {conference.title[:50]}...")
        
        logger.info(f"Found {existing_count} existing conferences")
        logger.info(f"Found {len(new_elements)} NEW conferences to process")
        
        # If no details needed, return basic info for new conferences
        if not fetch_details:
            conferences = []
            for element in new_elements:
                conference = self.extract_basic_info(element)
                conferences.append({
                    'title': conference.title,
                    'conference_dates': conference.conference_dates,
                    'location': conference.location,
                    'description': conference.description,
                    'ssrn_link': conference.ssrn_link,
                    'posted_date': conference.posted_date
                })
            
            return conferences
        
        # Fetch detailed descriptions only for new conferences (slow step)
        if len(new_elements) > 0:
            logger.info(f"Fetching detailed descriptions for {len(new_elements)} new conferences...")
        else:
            logger.info("No new conferences found - all are already in ssrn.json")
            return []
        
        conferences = []
        skipped_count = 0
        
        for i, element in enumerate(new_elements):
            try:
                logger.info(f"Processing new conference {i+1}/{len(new_elements)}")
                result = self.process_conference_with_details(element)
                if result:
                    conferences.append(result)
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to process conference {i+1}: {e}")
                skipped_count += 1
        
        elapsed = time.time() - start_time
        logger.info(f"Processed {len(conferences)} new conferences in {elapsed:.2f}s")
        if len(conferences) > 0:
            logger.info(f"Performance: {len(conferences)/elapsed:.2f} conferences/second")
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} invalid items")
        
        # Save conferences to JSON for tracking
        if conferences:
            self._save_conferences_to_json(conferences, existing_conferences_file)
        
        return conferences
    
    async def process_conferences_batch(self, conferences_df: pd.DataFrame) -> pd.DataFrame:
        """Process conferences with Claude AI"""
        if len(conferences_df) == 0:
            logger.info("No conferences to process")
            return conferences_df
        
        # Check if Claude API key is configured
        if not self.claude_config['api_key'] or self.claude_config['api_key'] == 'your_claude_api_key_here':
            logger.warning("Claude API key not configured. Skipping AI processing.")
            # Return dataframe with empty AI fields
            result_df = conferences_df.copy()
            result_df['Submission Deadline'] = ''
            result_df['Submission Fees'] = ''
            result_df['Registration Fees'] = ''
            result_df['Continent'] = ''
            return result_df
        
        logger.info(f"Processing {len(conferences_df)} conferences with Claude API...")
        start_time = time.time()
        
        result_df = conferences_df.copy()
        result_df['Submission Deadline'] = ''
        result_df['Submission Fees'] = ''
        result_df['Registration Fees'] = ''
        result_df['Continent'] = ''
        
        semaphore = asyncio.Semaphore(self.max_concurrent_api)
        
        async def process_single_conference(index, row):
            async with semaphore:
                try:
                    result = await self.call_claude_api(
                        title=row['title'],
                        location=row['location'],
                        description=str(row['description'])[:2000]
                    )
                    
                    return index, result
                except Exception as e:
                    logger.error(f"Error processing conference {index}: {e}")
                    return index, ConferenceResult()
        
        tasks = [
            process_single_conference(index, row) 
            for index, row in conferences_df.iterrows()
        ]
        
        chunk_size = 10
        processed_count = 0
        
        for i in range(0, len(tasks), chunk_size):
            chunk_tasks = tasks[i:i + chunk_size]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            for result in chunk_results:
                if isinstance(result, tuple):
                    index, conference_result = result
                    result_df.at[index, 'Submission Deadline'] = conference_result.submission_deadline
                    result_df.at[index, 'Submission Fees'] = conference_result.submission_fees
                    result_df.at[index, 'Registration Fees'] = conference_result.registration_fees
                    result_df.at[index, 'Continent'] = conference_result.continent
                    processed_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"Task failed: {result}")
            
            progress = min(i + chunk_size, len(tasks))
            logger.info(f"Progress: {progress}/{len(tasks)} ({progress/len(tasks)*100:.1f}%)")
            
            if i + chunk_size < len(tasks):
                await asyncio.sleep(0.5)
        
        elapsed = time.time() - start_time
        logger.info(f"Processed {processed_count} conferences in {elapsed:.2f}s")
        if elapsed > 0:
            logger.info(f"Performance: {processed_count/elapsed:.2f} conferences/second")
        
        return result_df


async def main():
    """Main function for standalone usage"""
    async with UnifiedConferenceScraper() as scraper:
        conferences = await scraper.scrape_conferences(fetch_details=True)
        
        if conferences:
            # Save directly to JSON for tracking (no CSV needed)
            scraper._save_conferences_to_json(conferences, "output/ssrn.json")
            logger.info(f"💾 Saved {len(conferences)} conferences to output/ssrn.json")
            
            # Process with Claude AI
            df = pd.DataFrame(conferences)
            processed_df = await scraper.process_conferences_batch(df)
            
            final_columns = [
                'title', 'conference_dates', 'location', 'Submission Deadline', 'ssrn_link',
                'Submission Fees', 'Registration Fees', 'Continent', 'posted_date'
            ]
            
            final_df = processed_df[final_columns].copy()
            final_df.columns = [
                'Title', 'Conference Date', 'Location', 'Deadline', 'Link',
                'Submission Fee', 'Registration Fee', 'Continent', 'Posted Date'
            ]
            
            final_df.to_csv("output/conferences.csv", index=False, encoding='utf-8')
            logger.info(f"💾 Saved {len(final_df)} processed conferences to output/conferences.csv")
        
        logger.info("🎉 Successfully completed scraping and processing")


if __name__ == "__main__":
    asyncio.run(main())