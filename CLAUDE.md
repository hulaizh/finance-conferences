# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a high-performance finance conference scraper that extracts conference data from SSRN (Social Science Research Network) and enriches it using DeepSeek AI API. The system uses async processing, caching, and fallback methods to ensure reliable data collection.

## Architecture

The pipeline consists of 4 main components:

1. **main.py** - Pipeline orchestrator that coordinates all steps
2. **src/scraper.py** - Async web scraper with fallback methods (async requests → Selenium → sync requests)
3. **src/deepseek.py** - AI processor for extracting structured data from conference descriptions
4. **Data flow**: SSRN scraping → new conference detection → AI enrichment → database update

## Project Structure

```
finance-conferences/
├── main.py              # Main pipeline orchestrator
├── src/                 # Source code modules
│   ├── __init__.py      # Package initialization
│   ├── scraper.py       # High-performance SSRN scraper
│   └── deepseek.py      # DeepSeek AI processor
├── output/              # Generated data files
│   ├── ssrn.csv         # Raw scraped data (generated)
│   ├── conferences.csv  # Final enriched database (generated)
│   └── *.csv           # Other temporary CSV files
├── requirements.txt     # Python dependencies
├── deepseek.txt        # DeepSeek API key (not in repo, must be created)
├── .deepseek_cache.pkl # API response cache (generated)
└── pipeline.log       # Processing logs (generated)
```

## Common Commands

### Setup
```bash
pip install -r requirements.txt
echo "your_deepseek_api_key_here" > deepseek.txt
```

### Running the Pipeline
```bash
# Complete pipeline (3-5 minutes)
python main.py

# Ultra-fast mode (1-2 minutes) 
python main.py --fast-mode

# Force complete refresh
python main.py --force-scrape --force-deepseek

# Individual components
python -m src.scraper      # Scraper only
python -m src.deepseek     # AI processor only
```

### Command Line Options
- `--force-scrape` - Force re-scraping even if ssrn.csv exists
- `--force-deepseek` - Force re-processing all conferences
- `--no-cache` - Disable caching for DeepSeek API calls
- `--fast-mode` - Skip detailed scraping for speed
- `--max-scrape-concurrent N` - Max concurrent connections (default: 3)
- `--max-api-concurrent N` - Max concurrent API calls (default: 5)

## Key Dependencies

- **selenium>=4.15.0** - Web scraping with fallback support
- **aiohttp>=3.9.0** - Async HTTP requests
- **pandas>=2.0.0** - Data processing
- **openai>=1.0.0** - DeepSeek API client
- **beautifulsoup4>=4.12.0** - HTML parsing

## Data Files

- **output/ssrn.csv** - Raw scraped data from SSRN
- **output/conferences.csv** - Final enriched database (main output)
- **pipeline.log** - Processing logs
- **.deepseek_cache.pkl** - API response cache
- **deepseek.txt** - DeepSeek API key (not in repo, must be created)

## Performance Features

- **Async processing** - 10x faster than traditional scraping
- **Concurrent API calls** - 5x faster DeepSeek processing
- **Smart caching** - Speeds up future runs significantly
- **Incremental updates** - Only processes new conferences
- **Fallback methods** - Handles Cloudflare protection automatically

## Pipeline Logic

The system maintains state between runs:
1. Compares new SSRN data with existing output/conferences.csv
2. Only processes conferences not already in the database
3. Uses title matching (case-insensitive) to detect duplicates
4. Caches DeepSeek API responses to avoid re-processing

## Error Handling

The scraper includes multiple fallback methods:
1. Primary: Async aiohttp requests
2. Fallback: Selenium WebDriver (handles JavaScript/Cloudflare)
3. Final: Synchronous requests

All components include comprehensive error logging to pipeline.log.