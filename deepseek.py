#!/usr/bin/env python3
"""
High-Performance DeepSeek Conference Processor
Fast async processing with caching and retry logic
"""

import asyncio
import aiohttp
import json
import time
import pandas as pd
from typing import Dict, List, Optional
import logging
from pathlib import Path
import hashlib
from dataclasses import dataclass
import pickle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ConferenceResult:
    submission_deadline: str = ""
    submission_fee: str = ""
    registration_fee: str = ""
    continent: str = ""


class DeepSeekProcessor:
    """High-performance async DeepSeek API processor with caching"""
    
    def __init__(self, api_key_file: str = "deepseek.txt", max_concurrent: int = 5, 
                 cache_file: str = ".deepseek_cache.pkl", enable_cache: bool = True):
        self.api_key = self._load_api_key(api_key_file)
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.max_concurrent = max_concurrent
        self.cache_file = cache_file
        self.enable_cache = enable_cache
        self.cache = self._load_cache() if enable_cache else {}
        self.session = None
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.prompt_template = """You are a JSON data extractor. Analyze the conference description and extract information. You MUST respond with ONLY valid JSON in this exact format:

{{
  "Submission Deadline": "",
  "Submission Fee": "",
  "Registration Fee": "",
  "Continent": ""
}}

EXTRACTION RULES:
1. Submission Deadline: Find submission/paper deadlines. Format as YYYY/MM/DD (e.g., 2025/12/31). Use "" if not found.

2. Submission Fee: Find submission/application fees. Include currency and amount (e.g., "$50", "€75"). Use "" if not mentioned or free.

3. Registration Fee: Find conference/registration fees. Include currency and amount (e.g., "$400", "€300"). Use "" if not mentioned.

4. Continent: Based on location, return exactly one of: Asia, Australia, Europe, North America, South America, Africa. Use geographical knowledge.

Conference Data:
Title: {title}
Location: {location}
Description: {description}

CRITICAL: Return ONLY the JSON object with the four fields above. No explanations, no additional text, no markdown formatting."""
    
    def _load_api_key(self, api_key_file: str) -> str:
        """Load API key from file"""
        try:
            with open(api_key_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"API key file {api_key_file} not found")
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        try:
            if Path(self.cache_file).exists():
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    logger.info(f"📦 Loaded {len(cache)} cached results")
                    return cache
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        if not self.enable_cache:
            return
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _get_cache_key(self, title: str, location: str, description: str) -> str:
        """Generate cache key for conference data"""
        content = f"{title}|{location}|{description[:500]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=10,
            ttl_dns_cache=300,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        self._save_cache()
    
    async def call_deepseek_api(self, title: str, location: str, description: str, 
                               retry_count: int = 3) -> ConferenceResult:
        """Call DeepSeek API with retry logic and caching"""
        if self.enable_cache:
            cache_key = self._get_cache_key(title, location, description)
            if cache_key in self.cache:
                cached_result = self.cache[cache_key]
                return ConferenceResult(**cached_result)
        
        prompt = self.prompt_template.format(
            title=title,
            location=location,
            description=description[:2000]
        )
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        for attempt in range(retry_count):
            try:
                async with self.session.post(self.api_url, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result['choices'][0]['message']['content'].strip()
                        
                        parsed_result = self._parse_json_response(content)
                        
                        if self.enable_cache and parsed_result:
                            self.cache[cache_key] = {
                                'submission_deadline': parsed_result.submission_deadline,
                                'submission_fee': parsed_result.submission_fee,
                                'registration_fee': parsed_result.registration_fee,
                                'continent': parsed_result.continent
                            }
                        
                        return parsed_result
                    
                    elif response.status == 429:
                        wait_time = min(2 ** attempt, 16)
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    else:
                        logger.error(f"API error {response.status}: {await response.text()}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"API call failed on attempt {attempt + 1}: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"Failed to process conference after {retry_count} attempts")
        return ConferenceResult()
    
    def _parse_json_response(self, content: str) -> ConferenceResult:
        """Parse JSON response with robust fallback handling"""
        # First clean the content
        content = content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```') and content.endswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1])
        elif content.startswith('```json') and content.endswith('```'):
            content = content[7:-3].strip()
        
        try:
            data = json.loads(content)
            return ConferenceResult(
                submission_deadline=data.get('Submission Deadline', ''),
                submission_fee=data.get('Submission Fee', ''),
                registration_fee=data.get('Registration Fee', ''),
                continent=data.get('Continent', '')
            )
        except json.JSONDecodeError:
            # Try to extract JSON from within the text
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != 0:
                try:
                    json_str = content[start:end]
                    data = json.loads(json_str)
                    return ConferenceResult(
                        submission_deadline=data.get('Submission Deadline', ''),
                        submission_fee=data.get('Submission Fee', ''),
                        registration_fee=data.get('Registration Fee', ''),
                        continent=data.get('Continent', '')
                    )
                except json.JSONDecodeError:
                    pass
            
            # Try to find key-value pairs using regex as final fallback
            try:
                result = ConferenceResult()
                
                # Extract using regex patterns
                deadline_match = re.search(r'"Submission Deadline":\s*"([^"]*)"', content)
                if deadline_match:
                    result.submission_deadline = deadline_match.group(1)
                
                sub_fee_match = re.search(r'"Submission Fee":\s*"([^"]*)"', content)
                if sub_fee_match:
                    result.submission_fee = sub_fee_match.group(1)
                
                reg_fee_match = re.search(r'"Registration Fee":\s*"([^"]*)"', content)
                if reg_fee_match:
                    result.registration_fee = reg_fee_match.group(1)
                
                continent_match = re.search(r'"Continent":\s*"([^"]*)"', content)
                if continent_match:
                    result.continent = continent_match.group(1)
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to parse with regex fallback: {e}")
            
            logger.warning(f"Failed to parse JSON response: {content[:200]}...")
            return ConferenceResult()
    
    async def process_conferences_batch(self, conferences_df: pd.DataFrame) -> pd.DataFrame:
        """Process conferences in batches with concurrent API calls"""
        if len(conferences_df) == 0:
            logger.info("✅ No conferences to process")
            return conferences_df
        
        logger.info(f"🤖 Processing {len(conferences_df)} conferences with DeepSeek API...")
        start_time = time.time()
        
        result_df = conferences_df.copy()
        result_df['Submission Deadline'] = ''
        result_df['Submission Fee'] = ''
        result_df['Registration Fee'] = ''
        result_df['Continent'] = ''
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_single_conference(index, row):
            async with semaphore:
                try:
                    result = await self.call_deepseek_api(
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
        
        chunk_size = 20
        processed_count = 0
        
        for i in range(0, len(tasks), chunk_size):
            chunk_tasks = tasks[i:i + chunk_size]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            for result in chunk_results:
                if isinstance(result, tuple):
                    index, conference_result = result
                    result_df.at[index, 'Submission Deadline'] = conference_result.submission_deadline
                    result_df.at[index, 'Submission Fee'] = conference_result.submission_fee
                    result_df.at[index, 'Registration Fee'] = conference_result.registration_fee
                    result_df.at[index, 'Continent'] = conference_result.continent
                    processed_count += 1
                elif isinstance(result, Exception):
                    logger.error(f"Task failed: {result}")
            
            progress = min(i + chunk_size, len(tasks))
            logger.info(f"📊 Progress: {progress}/{len(tasks)} ({progress/len(tasks)*100:.1f}%)")
            
            if i + chunk_size < len(tasks):
                await asyncio.sleep(1)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Processed {processed_count} conferences in {elapsed:.2f}s")
        if elapsed > 0:
            logger.info(f"📊 Performance: {processed_count/elapsed:.2f} conferences/second")
        
        return result_df
    
    async def process_from_csv(self, input_csv: str = "ssrn.csv", output_csv: str = "conferences.csv"):
        """Process conferences from CSV file"""
        try:
            df = pd.read_csv(input_csv)
            logger.info(f"📊 Loaded {len(df)} conferences from {input_csv}")
        except FileNotFoundError:
            logger.error(f"Input file {input_csv} not found")
            return
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return
        
        result_df = await self.process_conferences_batch(df)
        
        final_columns = [
            'title', 'conference_dates', 'location', 'description', 'ssrn_link',
            'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
        ]
        
        final_df = result_df[final_columns].copy()
        final_df.columns = [
            'Title', 'Conference Dates', 'Location', 'Description', 'Link',
            'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
        ]
        
        try:
            final_df.to_csv(output_csv, index=False, encoding='utf-8')
            logger.info(f"💾 Saved {len(final_df)} conferences to {output_csv}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")


async def main():
    """Main function for standalone usage"""
    async with DeepSeekProcessor(max_concurrent=5, enable_cache=True) as processor:
        await processor.process_from_csv()


if __name__ == "__main__":
    asyncio.run(main())