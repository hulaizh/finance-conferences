# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a high-performance finance conference scraper that extracts conference data from SSRN (Social Science Research Network) and enriches it using Claude AI via configurable API endpoints. The system uses async processing, caching, proxy support, and optimized scraping methods for fast and reliable data collection.

## Architecture

The pipeline consists of 4 main components:

1. **main.py** - Pipeline orchestrator that coordinates all steps
2. **src/scraper.py** - Unified high-performance scraper with Claude AI processing
3. **config.py** - Configuration management for API endpoints and proxy settings
4. **config.json** - JSON configuration file with API keys and settings
5. **Data flow**: SSRN scraping → new conference detection → AI enrichment → database update

## Project Structure

```
finance-conferences/
├── main.py              # Main pipeline orchestrator
├── config.py            # Configuration management
├── config.json          # JSON configuration file (API keys, proxy, settings)
├── src/                 # Source code modules
│   └── scraper.py       # Unified scraper with Claude AI processing
├── output/              # Generated data files
│   ├── ssrn.csv         # Raw scraped data (generated)
│   └── conferences.csv  # Final enriched database (generated)
├── requirements.txt     # Python dependencies
├── .claude_cache.pkl   # Claude API response cache (generated)
└── pipeline.log       # Processing logs (generated)
```

## Common Commands

### Setup
```bash
pip install -r requirements.txt

# Configure your Claude API endpoint and key in config.json:
# Edit config.json with your settings (see example below)
```

### Running the Pipeline
```bash
# Complete pipeline - always fetches new conferences and processes with Claude API
python main.py

# Using sample data for testing/demo only
python main.py --use-sample-data
```

### Command Line Options
- `--no-cache` - Disable caching for Claude API calls
- `--use-sample-data` - Skip SSRN scraping and use sample data (for testing/demo only)
- `--config FILE` - Specify configuration file path (default: config.json)

## Key Dependencies

- **aiohttp>=3.9.0** - Async HTTP requests with proxy support
- **pandas>=2.0.0** - Data processing
- **beautifulsoup4>=4.12.0** - HTML parsing
- **selenium>=4.15.0** - Optional fallback for protected sites
- **requests>=2.31.0** - Sync HTTP requests for fallback
- **Claude API** - AI processing via configurable API endpoint

## Data Files

- **output/ssrn.csv** - Raw scraped data from SSRN
- **output/conferences.csv** - Final enriched database (main output)
- **pipeline.log** - Processing logs
- **.claude_cache.pkl** - Claude API response cache

## Performance Features

- **Unified architecture** - Single script handles both scraping and AI processing
- **Configurable endpoints** - Support for custom Claude API servers
- **Proxy support** - HTTP/HTTPS proxy configuration for corporate networks
- **Async processing** - 10x faster than traditional scraping
- **Concurrent API calls** - Up to 10x faster Claude processing
- **Smart caching** - Speeds up future runs significantly
- **Incremental updates** - Only processes new conferences
- **Optimized scraping** - High-performance connection pooling
- **Better duplicate detection** - Normalized title matching with special character removal

## Pipeline Logic

The system maintains state between runs:
1. Compares new SSRN data with existing output/conferences.csv
2. Only processes conferences not already in the database
3. Uses normalized title matching with special character removal to detect duplicates
4. Caches Claude API responses to avoid re-processing

## Configuration

The system uses `config.json` for all configuration:

```json
{
  "claude_api": {
    "url": "http://your.claude.server:3000/claude/",
    "api_key": "your_api_key_here",
    "model": "claude-3-5-sonnet-20241022"
  },
  "proxy": {
    "http": "http://proxy.company.com:8080",
    "https": "https://proxy.company.com:8080"
  },
  "scraper": {
    "max_concurrent": 8,
    "timeout": 30,
    "enable_selenium": false,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
  },
  "processing": {
    "max_concurrent_api": 10,
    "cache_enabled": true
  }
}```

## Error Handling

The unified scraper uses optimized async HTTP requests with:
1. High-performance connection pooling with proxy support
2. Automatic retry logic with exponential backoff
3. Optional Selenium fallback (configurable via ENABLE_SELENIUM)
4. Graceful degradation when Claude API is unavailable

All components include comprehensive error logging to pipeline.log.