#!/usr/bin/env python3
"""
Conference Processing Pipeline
============================

High-performance pipeline for scraping and processing conference data from SSRN.

Usage:
    python main.py [--force-scrape] [--force-claude] [--fast-mode]
    
Features:
- Unified async web scraping with configurable settings
- Claude API processing with proxy support
- Smart resume capability for interrupted runs
- Real-time progress tracking
- Configurable via config.json file
"""

import asyncio
import sys
import os
import pandas as pd
import argparse
import logging
import time
import json
from typing import Optional, Dict, Any

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper import UnifiedConferenceScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for Claude Code API and proxy settings"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file {self.config_file} not found. Using defaults.")
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            logger.info(f"📋 Loaded configuration from {self.config_file}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading config file {self.config_file}: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            "claude_api": {
                "url": "https://api.anthropic.com/v1/messages",
                "api_key": "",
                "model": "claude-3-5-sonnet-20241022"
            },
            "proxy": {
                "http": "",
                "https": ""
            },
            "scraper": {
                "max_concurrent": 8,
                "timeout": 30,
                "enable_selenium": False,
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "processing": {
                "max_concurrent_api": 10,
            }
        }
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'claude_api.url')"""
        keys = path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_claude_api_key(self) -> Optional[str]:
        """Get Claude API key"""
        api_key = self.get('claude_api.api_key')
        if not api_key:
            logger.warning("Claude API key not configured")
        return api_key
    
    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """Get proxy configuration for HTTP requests"""
        http_proxy = self.get('proxy.http')
        https_proxy = self.get('proxy.https')
        
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies['http'] = http_proxy
            if https_proxy:
                proxies['https'] = https_proxy
            return proxies
        
        return None
    
    def get_scraper_config(self) -> Dict[str, Any]:
        """Get scraper configuration"""
        default_config = self._get_default_config()['scraper']
        return {
            'max_concurrent': self.get('scraper.max_concurrent', default_config['max_concurrent']),
            'timeout': self.get('scraper.timeout', default_config['timeout']),
            'enable_selenium': self.get('scraper.enable_selenium', default_config['enable_selenium']),
            'user_agent': self.get('scraper.user_agent', default_config['user_agent']),
            'proxies': self.get_proxy_config()
        }
    
    def get_claude_config(self) -> Dict[str, Any]:
        """Get Claude API configuration"""
        default_claude = self._get_default_config()['claude_api']
        default_processing = self._get_default_config()['processing']
        return {
            'api_url': self.get('claude_api.url', default_claude['url']),
            'api_key': self.get_claude_api_key(),
            'model': self.get('claude_api.model', default_claude['model']),
            'max_concurrent': self.get('processing.max_concurrent_api', default_processing['max_concurrent_api']),
            'proxies': self.get_proxy_config()
        }


# Global configuration instance
config = Config()


class ConferencePipeline:
    """High-performance conference processing pipeline"""
    
    def __init__(self):
        self.ssrn_json = "output/ssrn.json"
        self.conferences_json = "output/conferences.json"
        self.conferences_csv = "output/conferences.csv"
        
    async def step1_scrape_ssrn(self, force_scrape: bool = False):
        """Step 1: Scraping - only for conferences on ssrn.com but not in ssrn.json"""
        logger.info("Step 1: Scraping conferences not already in ssrn.json...")
        
        if os.path.exists(self.ssrn_json) and not force_scrape:
            with open(self.ssrn_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            conferences = data.get('conferences', [])
            logger.info(f"Found {len(conferences)} conferences in {self.ssrn_json}")
            return True
        
        logger.info("Scraping conferences...")
        start_time = time.time()
        
        try:
            async with UnifiedConferenceScraper(config_obj=config) as scraper:
                # Always fetch full details - no fast mode
                conferences = scraper.scrape_conferences(fetch_details=True, existing_conferences_file=self.ssrn_json)
                
                if not conferences:
                    logger.info("ℹ️ No new valid conferences found to add")
                    # This is not an error - just means everything is up to date
                
                elapsed = time.time() - start_time
                logger.info(f"Scraped {len(conferences) if conferences else 0} new conferences in {elapsed:.2f}s")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Error during scraping: {e}")
            
            logger.error("SSRN scraping failed. Check internet connection.")
            return False
    
    def find_new_conferences_for_claude(self, force_reprocess: bool = False):
        """Find conferences in ssrn.json but not in conferences.json for Claude processing"""
        logger.info("Finding conferences for Claude processing...")
        
        try:
            if not os.path.exists(self.ssrn_json):
                logger.error(f"{self.ssrn_json} not found")
                return None
            
            # Load SSRN data
            with open(self.ssrn_json, 'r', encoding='utf-8') as f:
                ssrn_data = json.load(f)
            
            ssrn_conferences = ssrn_data.get('conferences', [])
            logger.info(f"Loaded {len(ssrn_conferences)} conferences from ssrn.json")
            
            # Load existing processed conferences (unless force reprocessing)
            existing_signatures = set()
            if not force_reprocess and os.path.exists(self.conferences_json):
                with open(self.conferences_json, 'r', encoding='utf-8') as f:
                    conferences_data = json.load(f)
                
                existing_conferences = conferences_data.get('conferences', [])
                logger.info(f"Found {len(existing_conferences)} existing processed conferences")
                
                # Create signatures for existing conferences
                for conf in existing_conferences:
                    signature = self._create_conference_signature({
                        'title': conf.get('Title', ''),
                        'location': conf.get('Location', ''),
                        'conference_dates': conf.get('Conference Date', '')
                    })
                    if signature:
                        existing_signatures.add(signature)
                        
                logger.info(f"Created {len(existing_signatures)} existing signatures")
            elif force_reprocess:
                logger.info("Force reprocessing enabled - will reprocess all conferences")
            else:
                logger.info("No existing conferences.json found")
            
            # Find new conferences that need Claude processing
            new_conferences = []
            for conf in ssrn_conferences:
                signature = self._create_conference_signature({
                    'title': conf.get('title', ''),
                    'location': conf.get('location', ''),
                    'conference_dates': conf.get('conference_dates', '')
                })
                
                if signature not in existing_signatures:
                    new_conferences.append(conf)
            
            logger.info(f"Found {len(new_conferences)} new conferences needing Claude processing")
            
            if not new_conferences:
                logger.info("No new conferences found")
                return pd.DataFrame()
            
            # Convert to DataFrame for processing
            new_conferences_df = pd.DataFrame(new_conferences)
            return new_conferences_df
            
        except Exception as e:
            logger.error(f"Error finding new conferences: {e}")
            return None
    
    def _create_conference_signature(self, conference_data: dict) -> str:
        """Create a unique signature for conference comparison"""
        def normalize_text(text):
            import re
            if not text:
                return ""
            # Convert to lowercase, remove special chars, normalize spaces
            normalized = re.sub(r'[^a-z0-9\s]', '', str(text).lower())
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            return normalized
        
        title = normalize_text(conference_data.get('title', ''))
        location = normalize_text(conference_data.get('location', ''))
        dates = normalize_text(conference_data.get('conference_dates', ''))
        return f"{title}|{location}|{dates}"
    
    async def step2_process_with_claude(self, new_conferences_df, force_claude: bool = False):
        """Step 2: Claude extraction - only for conferences in ssrn.json but not in conferences.json"""
        logger.info("Step 2: Claude AI processing for new conferences...")
        
        if new_conferences_df is None:
            logger.error("No conferences data provided")
            return None
        
        if len(new_conferences_df) == 0:
            logger.info("No new conferences to process")
            return pd.DataFrame()
        
        try:
            logger.info(f"Processing {len(new_conferences_df)} conferences...")
            start_time = time.time()
            
            async with UnifiedConferenceScraper(config_obj=config) as scraper:
                processed_df = await scraper.process_conferences_batch(new_conferences_df)
                
                elapsed = time.time() - start_time
                logger.info(f"Processed {len(processed_df)} conferences in {elapsed:.2f}s")
                
                return processed_df
                
        except Exception as e:
            logger.error(f"Error during Claude processing: {e}")
            return None
    
    def update_conferences_json(self, processed_new_conferences):
        """Update conferences.json with processed conferences (part of Step 2)"""
        logger.info("Adding processed conferences to conferences.json...")
        
        if processed_new_conferences is None:
            logger.error("No processed conferences data provided")
            return False
        
        if len(processed_new_conferences) == 0:
            logger.info("No new conferences to add")
            return True
        
        try:
            # No filtering here - save all processed conferences to JSON
            # Filtering will be applied only when generating CSV
            
            # Select only the required final columns
            final_columns = ['title', 'conference_dates', 'location', 'Submission Deadline', 'ssrn_link', 'Submission Fees', 'Registration Fees', 'Continent', 'posted_date']
            new_conferences_formatted = processed_new_conferences[final_columns].copy()
            
            # Clean up empty/nan values in Claude columns before saving
            claude_columns = ['Submission Deadline', 'Submission Fees', 'Registration Fees', 'Continent']
            for col in claude_columns:
                new_conferences_formatted[col] = new_conferences_formatted[col].fillna('').astype(str)
                new_conferences_formatted[col] = new_conferences_formatted[col].replace(['nan', 'None', 'null'], '')
            
            # Set final column names
            new_conferences_formatted.columns = [
                'Title', 'Conference Date', 'Location', 'Deadline', 'Link', 'Submission Fee', 'Registration Fee', 'Continent', 'Posted Date'
            ]
            
            # Convert to list of dictionaries for JSON storage
            new_conferences_list = new_conferences_formatted.to_dict('records')
            
            # Load existing conferences.json or create new structure
            if os.path.exists(self.conferences_json):
                with open(self.conferences_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📊 Loaded {len(data.get('conferences', []))} existing conferences")
            else:
                data = {
                    'metadata': {
                        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'total_conferences': 0,
                        'last_updated': None
                    },
                    'conferences': []
                }
                logger.info("📝 Creating new conferences.json")
            
            # Add new conferences
            data['conferences'].extend(new_conferences_list)
            data['metadata']['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')
            data['metadata']['total_conferences'] = len(data['conferences'])
            
            # Save to JSON
            with open(self.conferences_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"➕ Added {len(new_conferences_list)} new conferences to conferences.json")
            logger.info(f"📊 Total conferences in JSON: {len(data['conferences'])}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating conferences JSON: {e}")
            return False
    
    def _sort_conferences_final(self, df):
        """Sort conferences by Posted Date (newest first) and Title (alphabetically)"""
        try:
            import datetime
            
            def parse_posted_date(date_str):
                """Parse various posted date formats into datetime object"""
                if not date_str or pd.isna(date_str):
                    return datetime.datetime.min  # Put entries without dates at the end
                
                date_str = str(date_str).strip()
                if not date_str or date_str.lower() in ['nan', 'none', 'null']:
                    return datetime.datetime.min
                
                try:
                    # Try different date formats
                    formats = [
                        "%d %b %Y",      # "10 Aug 2025"
                        "%d %B %Y",      # "10 August 2025"
                        "%b %d %Y",      # "Aug 10 2025"
                        "%B %d, %Y",     # "August 10, 2025"
                        "%d-%m-%Y",      # "10-08-2025"
                        "%Y-%m-%d",      # "2025-08-10"
                        "%m/%d/%Y",      # "08/10/2025"
                    ]
                    
                    for fmt in formats:
                        try:
                            return datetime.datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                    
                    # If no format works, try to extract year at least
                    import re
                    year_match = re.search(r'(\d{4})', date_str)
                    if year_match:
                        year = int(year_match.group(1))
                        return datetime.datetime(year, 1, 1)  # Default to Jan 1st of that year
                        
                except Exception as e:
                    logger.debug(f"Failed to parse posted date '{date_str}': {e}")
                
                return datetime.datetime.min
            
            # Create a copy to avoid modifying original
            df_sorted = df.copy()
            
            # Sort by Posted Date (newest first), then by Title (alphabetically)
            if 'Posted Date' in df_sorted.columns:
                df_sorted['_sort_date'] = df_sorted['Posted Date'].apply(parse_posted_date)
                df_sorted = df_sorted.sort_values(
                    by=['_sort_date', 'Title'],
                    ascending=[False, True],  # Posted Date newest first, Title A-Z
                    na_position='last'
                )
                # Remove the temporary sorting column
                df_sorted = df_sorted.drop('_sort_date', axis=1)
            else:
                # If no Posted Date column, just sort by Title
                df_sorted = df_sorted.sort_values(by='Title', ascending=True, na_position='last')
            
            # Reset index after sorting
            df_sorted = df_sorted.reset_index(drop=True)
            
            logger.info(f"Sorted {len(df_sorted)} conferences")
            return df_sorted
            
        except Exception as e:
            logger.warning(f"Failed to sort conferences: {e}, returning original order")
            return df
    
    def _generate_csv_from_json(self):
        """Generate conferences.csv from conferences.json with proper sorting"""
        logger.info("Generating conferences.csv from conferences.json...")
        
        try:
            if not os.path.exists(self.conferences_json):
                logger.warning(f"{self.conferences_json} not found - no CSV to generate")
                return False
            
            # Load JSON data
            with open(self.conferences_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            conferences = data.get('conferences', [])
            if not conferences:
                logger.warning("No conferences found in JSON")
                return False
            
            logger.info(f"Loaded {len(conferences)} conferences from JSON")
            
            # Convert to DataFrame
            df = pd.DataFrame(conferences)
            
            # Apply filtering here - only for CSV export
            def contains_sample_keywords(row):
                """Check if any field contains sample/trial keywords"""
                keywords = ['samp', 'smp', 'trial']
                fields_to_check = ['Title', 'Location', 'Link']
                
                for field in fields_to_check:
                    if field in row and row[field] and isinstance(row[field], str):
                        field_lower = str(row[field]).lower()
                        if any(keyword in field_lower for keyword in keywords):
                            return True
                return False
            
            # Filter out rows containing sample keywords for CSV export
            mask = ~df.apply(contains_sample_keywords, axis=1)
            df_filtered = df[mask].copy()
            
            logger.info(f"Filtered {len(df) - len(df_filtered)} sample conferences for CSV export")
            logger.info(f"Exporting {len(df_filtered)} conferences to CSV")
            
            # Ensure we have the required columns in the right order
            required_columns = [
                'Title', 'Conference Date', 'Location', 'Deadline', 'Link',
                'Submission Fee', 'Registration Fee', 'Continent', 'Posted Date'
            ]
            
            # Select and reorder columns
            df_final = df_filtered[required_columns].copy()
            
            # Sort by Posted Date (newest first), then by Title (alphabetically)
            df_sorted = self._sort_conferences_final(df_final)
            
            # Save to CSV
            df_sorted.to_csv(self.conferences_csv, index=False, encoding='utf-8')
            logger.info(f"Generated {self.conferences_csv} with {len(df_sorted)} conferences")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating CSV from JSON: {e}")
            return False
    
    
    async def run_pipeline(self, force_scrape: bool = False, force_claude: bool = False, force_reprocess: bool = False):
        """Run the complete pipeline"""
        logger.info("Starting pipeline...")
        pipeline_start = time.time()
        
        # Step 1: Scraping - only for conferences not already in ssrn.json
        if not await self.step1_scrape_ssrn(force_scrape):
            logger.error("Pipeline failed at Step 1 (Scraping)")
            return False
        
        # Step 2: Claude processing - only for conferences in ssrn.json but not in conferences.json
        new_conferences = self.find_new_conferences_for_claude(force_reprocess=force_reprocess)
        if new_conferences is None:
            logger.error("Pipeline failed finding conferences for Claude processing")
            return False
        
        if len(new_conferences) > 0:
            processed_conferences = await self.step2_process_with_claude(new_conferences, force_claude)
            if processed_conferences is None:
                logger.error("Pipeline failed at Step 2 (Claude processing)")
                return False
            
            if not self.update_conferences_json(processed_conferences):
                logger.error("Pipeline failed updating conferences.json")
                return False
        else:
            logger.info("No new conferences found for Claude processing")
        
        # Always generate CSV from JSON at the end
        logger.info("Generating conferences.csv from conferences.json...")
        if not self._generate_csv_from_json():
            logger.error("Pipeline failed generating CSV")
            return False
        
        pipeline_elapsed = time.time() - pipeline_start
        logger.info(f"Pipeline completed in {pipeline_elapsed:.2f}s")
        return True


async def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Conference Processing Pipeline - Always fetches new conferences and processes with Claude API')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Configuration file path (default: config.json)')
    parser.add_argument('--force-reprocess', action='store_true',
                       help='Force reprocessing of all conferences to improve missing deadline/fee data')
    
    args = parser.parse_args()
    
    pipeline = ConferencePipeline()
    
    # Default behavior: always fetch new conferences and process with Claude
    success = await pipeline.run_pipeline(
        force_scrape=True,   # Always scrape for new conferences
        force_claude=False,   # Process only new conferences
        force_reprocess=args.force_reprocess  # Force reprocess all if requested
    )
    
    if success:
        print("Pipeline completed successfully!")
        print(f"Results: {pipeline.conferences_csv}")
    else:
        print("Pipeline failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())