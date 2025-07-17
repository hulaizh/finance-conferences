#!/usr/bin/env python3
"""
Main Conference Processing Pipeline
==================================

This script orchestrates the complete conference data processing pipeline:
1. Web scrape all conferences from SSRN and save to ssrn.csv
2. Compare conference titles in ssrn.csv and conferences.csv to find new conferences
3. Run DeepSeek API to extract additional information for new conferences
4. Append new conference information to conferences.csv and generate updated file

Usage:
    python main.py [--force-scrape] [--force-deepseek]
    
Options:
    --force-scrape: Force re-scraping even if ssrn.csv exists
    --force-deepseek: Force re-processing all conferences with DeepSeek
"""

import sys
import os
import pandas as pd
import argparse
import logging
from pathlib import Path

# Add src directory to path for imports
sys.path.append('src')

from scraper import SSRNConferenceScraper
from deepseek import DeepSeekConferenceProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('conference_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ConferencePipeline:
    """Main pipeline orchestrator for conference data processing"""
    
    def __init__(self):
        self.ssrn_csv = "ssrn.csv"
        self.conferences_csv = "conferences.csv"
        self.temp_new_conferences_csv = "new_conferences_temp.csv"
        
    def step1_scrape_ssrn(self, force_scrape=False):
        """Step 1: Web scrape all conferences from SSRN and save to ssrn.csv"""
        logger.info("=" * 60)
        logger.info("STEP 1: Scraping SSRN Conferences")
        logger.info("=" * 60)
        
        if os.path.exists(self.ssrn_csv) and not force_scrape:
            logger.info(f"✓ {self.ssrn_csv} already exists. Use --force-scrape to re-scrape.")
            df = pd.read_csv(self.ssrn_csv)
            logger.info(f"✓ Found {len(df)} existing conferences in {self.ssrn_csv}")
            return True
        
        logger.info("🕷️  Starting SSRN web scraping...")
        
        try:
            scraper = SSRNConferenceScraper()
            conferences = scraper.scrape_conferences(fetch_details=True)
            
            if not conferences:
                logger.error("❌ No conferences scraped. Check scraper functionality.")
                return False
            
            # Save to CSV
            df = pd.DataFrame(conferences)
            df.to_csv(self.ssrn_csv, index=False, encoding='utf-8')
            
            logger.info(f"✅ Successfully scraped {len(conferences)} conferences to {self.ssrn_csv}")
            logger.info(f"   Columns: {list(df.columns)}")
            
            scraper._cleanup()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during SSRN scraping: {e}")
            return False
    
    def step2_find_new_conferences(self):
        """Step 2: Compare titles and find conferences in ssrn.csv but not in conferences.csv"""
        logger.info("=" * 60)
        logger.info("STEP 2: Finding New Conferences")
        logger.info("=" * 60)
        
        try:
            # Load SSRN data
            if not os.path.exists(self.ssrn_csv):
                logger.error(f"❌ {self.ssrn_csv} not found. Run step 1 first.")
                return None
            
            ssrn_df = pd.read_csv(self.ssrn_csv)
            logger.info(f"📊 Loaded {len(ssrn_df)} conferences from {self.ssrn_csv}")
            
            # Load existing conferences data (if exists)
            if os.path.exists(self.conferences_csv):
                conferences_df = pd.read_csv(self.conferences_csv)
                logger.info(f"📊 Loaded {len(conferences_df)} existing conferences from {self.conferences_csv}")
                
                # Find new conferences by comparing titles
                existing_titles = set(conferences_df['Title'].str.strip().str.lower())
                ssrn_titles = ssrn_df['title'].str.strip().str.lower()
                
                # Filter for new conferences
                new_mask = ~ssrn_titles.isin(existing_titles)
                new_conferences = ssrn_df[new_mask].copy()
                
                logger.info(f"🔍 Found {len(new_conferences)} new conferences to process")
                
                if len(new_conferences) == 0:
                    logger.info("✅ No new conferences found. Database is up to date.")
                    return pd.DataFrame()  # Return empty DataFrame
                
            else:
                logger.info(f"📝 {self.conferences_csv} not found. All conferences are new.")
                new_conferences = ssrn_df.copy()
                logger.info(f"🔍 Processing all {len(new_conferences)} conferences as new")
            
            # Save new conferences for processing
            new_conferences.to_csv(self.temp_new_conferences_csv, index=False, encoding='utf-8')
            logger.info(f"💾 Saved {len(new_conferences)} new conferences to {self.temp_new_conferences_csv}")
            
            # Show sample of new conferences
            if len(new_conferences) > 0:
                logger.info("📋 Sample of new conferences:")
                for i, row in new_conferences.head(3).iterrows():
                    logger.info(f"   {i+1}. {row['title'][:60]}...")
            
            return new_conferences
            
        except Exception as e:
            logger.error(f"❌ Error finding new conferences: {e}")
            return None
    
    def step3_process_with_deepseek(self, new_conferences_df, force_deepseek=False):
        """Step 3: Run DeepSeek API to extract information for new conferences"""
        logger.info("=" * 60)
        logger.info("STEP 3: Processing with DeepSeek API")
        logger.info("=" * 60)
        
        if new_conferences_df is None:
            logger.error("❌ No new conferences data provided")
            return None
        
        if len(new_conferences_df) == 0:
            logger.info("✅ No new conferences to process with DeepSeek")
            return pd.DataFrame()
        
        try:
            logger.info(f"🤖 Processing {len(new_conferences_df)} conferences with DeepSeek API...")
            
            # Initialize DeepSeek processor
            processor = DeepSeekConferenceProcessor()
            
            # Initialize new columns for DeepSeek data
            new_conferences_df['Submission Deadline'] = ''
            new_conferences_df['Submission Fee'] = ''
            new_conferences_df['Registration Fee'] = ''
            new_conferences_df['Continent'] = ''
            
            # Process each new conference
            for index, row in new_conferences_df.iterrows():
                logger.info(f"🔄 Processing {index + 1}/{len(new_conferences_df)}: {row['title'][:50]}...")
                
                try:
                    result = processor.call_deepseek_api(
                        title=row['title'],
                        location=row['location'],
                        description=row['description'][:2000]
                    )
                    
                    # Update dataframe with results
                    new_conferences_df.at[index, 'Submission Deadline'] = result.get('Submission Deadline', '')
                    new_conferences_df.at[index, 'Submission Fee'] = result.get('Submission Fee', '')
                    new_conferences_df.at[index, 'Registration Fee'] = result.get('Registration Fee', '')
                    new_conferences_df.at[index, 'Continent'] = result.get('Continent', '')
                    
                    logger.info(f"   ✓ Deadline: {result.get('Submission Deadline', 'N/A')}, "
                               f"Sub Fee: {result.get('Submission Fee', 'N/A')}, "
                               f"Reg Fee: {result.get('Registration Fee', 'N/A')}, "
                               f"Continent: {result.get('Continent', 'N/A')}")
                    
                    # Respect API rate limits
                    import time
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"   ❌ Error processing conference {index + 1}: {e}")
                    continue
            
            logger.info(f"✅ Completed DeepSeek processing for {len(new_conferences_df)} conferences")
            return new_conferences_df
            
        except Exception as e:
            logger.error(f"❌ Error during DeepSeek processing: {e}")
            return None
    
    def step4_update_conferences_csv(self, processed_new_conferences):
        """Step 4: Append new conference information to conferences.csv"""
        logger.info("=" * 60)
        logger.info("STEP 4: Updating Conferences Database")
        logger.info("=" * 60)
        
        if processed_new_conferences is None:
            logger.error("❌ No processed conferences data provided")
            return False
        
        if len(processed_new_conferences) == 0:
            logger.info("✅ No new conferences to add to database")
            return True
        
        try:
            # Prepare new conferences in the correct format
            new_conferences_formatted = processed_new_conferences[[
                'title', 'conference_dates', 'location', 'ssrn_link',
                'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
            ]].copy()
            
            new_conferences_formatted.columns = [
                'Title', 'Conference Dates', 'Location', 'Link',
                'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
            ]
            
            # Load existing conferences or create new DataFrame
            if os.path.exists(self.conferences_csv):
                existing_df = pd.read_csv(self.conferences_csv)
                logger.info(f"📊 Loaded {len(existing_df)} existing conferences")
                
                # Append new conferences
                updated_df = pd.concat([existing_df, new_conferences_formatted], ignore_index=True)
                logger.info(f"➕ Added {len(new_conferences_formatted)} new conferences")
                
            else:
                updated_df = new_conferences_formatted
                logger.info(f"📝 Created new conferences database with {len(updated_df)} conferences")
            
            # Save updated conferences
            updated_df.to_csv(self.conferences_csv, index=False, encoding='utf-8')
            logger.info(f"✅ Successfully updated {self.conferences_csv} with {len(updated_df)} total conferences")
            
            # Clean up temporary file
            if os.path.exists(self.temp_new_conferences_csv):
                os.remove(self.temp_new_conferences_csv)
                logger.info("🧹 Cleaned up temporary files")
            
            # Show final statistics
            logger.info("📈 Final Database Statistics:")
            logger.info(f"   Total Conferences: {len(updated_df)}")
            logger.info(f"   Columns: {list(updated_df.columns)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating conferences database: {e}")
            return False
    
    def run_pipeline(self, force_scrape=False, force_deepseek=False):
        """Run the complete pipeline"""
        logger.info("🚀 Starting Conference Processing Pipeline")
        logger.info("=" * 80)
        
        # Step 1: Scrape SSRN
        if not self.step1_scrape_ssrn(force_scrape):
            logger.error("❌ Pipeline failed at Step 1")
            return False
        
        # Step 2: Find new conferences
        new_conferences = self.step2_find_new_conferences()
        if new_conferences is None:
            logger.error("❌ Pipeline failed at Step 2")
            return False
        
        # Step 3: Process with DeepSeek
        processed_conferences = self.step3_process_with_deepseek(new_conferences, force_deepseek)
        if processed_conferences is None:
            logger.error("❌ Pipeline failed at Step 3")
            return False
        
        # Step 4: Update conferences.csv
        if not self.step4_update_conferences_csv(processed_conferences):
            logger.error("❌ Pipeline failed at Step 4")
            return False
        
        logger.info("=" * 80)
        logger.info("🎉 Conference Processing Pipeline Completed Successfully!")
        logger.info("=" * 80)
        return True


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='Conference Processing Pipeline')
    parser.add_argument('--force-scrape', action='store_true', 
                       help='Force re-scraping even if ssrn.csv exists')
    parser.add_argument('--force-deepseek', action='store_true',
                       help='Force re-processing all conferences with DeepSeek')
    
    args = parser.parse_args()
    
    # Run the pipeline
    pipeline = ConferencePipeline()
    success = pipeline.run_pipeline(
        force_scrape=args.force_scrape,
        force_deepseek=args.force_deepseek
    )
    
    if success:
        print("\n✅ Pipeline completed successfully!")
        print(f"📁 Check {pipeline.conferences_csv} for the final results")
    else:
        print("\n❌ Pipeline failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
