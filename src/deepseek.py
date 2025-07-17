#!/usr/bin/env python3
"""
DeepSeek Conference Information Extractor
Processes SSRN conference data and extracts additional information using DeepSeek API
"""

import pandas as pd
import json
import time
import requests
from typing import Dict, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeepSeekConferenceProcessor:
    def __init__(self, api_key_file: str = "deepseek.txt"):
        """Initialize with DeepSeek API key"""
        try:
            with open(api_key_file, 'r') as f:
                self.api_key = f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"API key file {api_key_file} not found")

        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self.prompt_template = """You return me a json below for the conference as {{
  "Submission Deadline": "",
  "Submission Fee": "",
  "Registration Fee": "",
  "Continent": ""
}}.
The deadline should be in date format like 2025/12/31. Fees are in numbers with currency symbol. No fees or Not mentioned should be left empty. Continent should be among Asia, Australia, Europe, North America, South America, Africa.

Conference Information:
Title: {title}
Location: {location}
Description: {description}

Return only the JSON, no other text."""

    def call_deepseek_api(self, title: str, location: str, description: str) -> Dict:
        """Call DeepSeek API to extract conference information"""
        prompt = self.prompt_template.format(
            title=title,
            location=location,
            description=description[:2000]  # Limit description length
        )

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }

        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()

            result = response.json()
            content = result['choices'][0]['message']['content'].strip()

            # Parse JSON response
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it contains extra text
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != 0:
                    return json.loads(content[start:end])
                else:
                    logger.error(f"Failed to parse JSON: {content}")
                    return self._get_empty_result()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return self._get_empty_result()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return self._get_empty_result()

    def _get_empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            "Submission Deadline": "",
            "Submission Fee": "",
            "Registration Fee": "",
            "Continent": ""
        }

    def process_conferences(self, input_csv: str = "ssrn.csv", output_csv: str = "conferences.csv") -> None:
        """Process all conferences from CSV and extract additional information"""
        logger.info(f"Reading conferences from {input_csv}")

        # Read the CSV file
        try:
            df = pd.read_csv(input_csv)
            logger.info(f"Found {len(df)} conferences to process")
        except FileNotFoundError:
            logger.error(f"Input file {input_csv} not found")
            return
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return

        # Initialize new columns
        df['Submission Deadline'] = ""
        df['Submission Fee'] = ""
        df['Registration Fee'] = ""
        df['Continent'] = ""

        # Process each conference
        for index, row in df.iterrows():
            logger.info(f"Processing conference {index + 1}/{len(df)}: {row['title'][:50]}...")

            try:
                # Call DeepSeek API
                result = self.call_deepseek_api(
                    title=row['title'],
                    location=row['location'],
                    description=row['description'][:2000]  # Limit description length
                )

                # Update dataframe with results
                df.at[index, 'Submission Deadline'] = result.get('Submission Deadline', '')
                df.at[index, 'Submission Fee'] = result.get('Submission Fee', '')
                df.at[index, 'Registration Fee'] = result.get('Registration Fee', '')
                df.at[index, 'Continent'] = result.get('Continent', '')

                logger.info(f"  ✓ Extracted: Deadline={result.get('Submission Deadline', 'N/A')}, "
                           f"Sub Fee={result.get('Submission Fee', 'N/A')}, "
                           f"Reg Fee={result.get('Registration Fee', 'N/A')}, "
                           f"Continent={result.get('Continent', 'N/A')}")

                # Add delay to respect API rate limits
                time.sleep(2)

                # Save progress every 10 conferences
                if (index + 1) % 10 == 0:
                    logger.info(f"💾 Saving progress after {index + 1} conferences...")
                    temp_columns = [
                        'title', 'conference_dates', 'location', 'ssrn_link',
                        'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
                    ]
                    temp_df = df[temp_columns].copy()
                    temp_df.columns = [
                        'Title', 'Conference Dates', 'Location', 'Link',
                        'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
                    ]
                    temp_df.to_csv(f"conferences_progress_{index + 1}.csv", index=False, encoding='utf-8')

            except Exception as e:
                logger.error(f"Error processing conference {index + 1}: {e}")
                continue

        # Reorder columns as requested: Title, Conference Dates, Location, Link, Submission Deadline, Submission Fee, Registration Fee, Continent
        final_columns = [
            'title', 'conference_dates', 'location', 'ssrn_link',
            'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
        ]

        # Rename columns to match requested format
        df_final = df[final_columns].copy()
        df_final.columns = [
            'Title', 'Conference Dates', 'Location', 'Link',
            'Submission Deadline', 'Submission Fee', 'Registration Fee', 'Continent'
        ]

        # Save the final CSV
        try:
            df_final.to_csv(output_csv, index=False, encoding='utf-8')
            logger.info(f"✅ Successfully saved {len(df_final)} conferences to {output_csv}")
            logger.info(f"Final columns: {list(df_final.columns)}")
        except Exception as e:
            logger.error(f"Error saving output file: {e}")


def main():
    """Main function"""
    processor = DeepSeekConferenceProcessor()
    processor.process_conferences()


if __name__ == "__main__":
    main()


