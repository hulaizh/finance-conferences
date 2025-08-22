# Finance Conference Scraper

A **high-performance** pipeline for scraping and processing finance conference data from SSRN using Claude AI for intelligent data extraction.

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+**
2. **Claude API Access** (via proxy or direct)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure Claude API in config.json
# Edit config.json with your API endpoint and key
```

### Basic Usage

```bash
# Run the complete pipeline (3-5 minutes)
python main.py

# Ultra-fast mode - basic info only (1-2 minutes)
python main.py --fast-mode

# Force complete refresh
python main.py --force-scrape --force-claude
```

## 📖 Configuration

### Setup config.json

Create or edit `config.json` with your Claude API settings:

```json
{
  "claude_api": {
    "url": "http://your.claude.endpoint/api/v1/messages",
    "api_key": "your_claude_api_key_here",
    "model": "claude-3-5-sonnet-20241022"
  },
  "proxy": {
    "http": "",
    "https": ""
  },
  "scraper": {
    "max_concurrent": 8,
    "timeout": 30,
    "enable_selenium": false,
    "user_agent": "Mozilla/5.0 (compatible scraper)"
  },
  "processing": {
    "max_concurrent_api": 10,
    "cache_enabled": true
  }
}
```

## 📖 Usage Guide

### Complete Pipeline

The pipeline automatically:
1. **Scrapes SSRN** → Creates/updates `output/ssrn.csv` with conference data
2. **Finds New Conferences** → Compares with existing `output/conferences.csv`
3. **AI Enhancement** → Uses Claude API to extract additional information
4. **Updates Database** → Appends new data to `output/conferences.csv`

### Command Options

```bash
python main.py [OPTIONS]

Options:
  --force-scrape    Force re-scraping even if ssrn.csv exists
  --force-claude    Force re-processing all conferences with Claude
  --no-cache        Disable caching for Claude API calls
  --fast-mode       Skip detailed scraping for ultra-fast processing
  --config FILE     Specify custom config file (default: config.json)
```

### Individual Components

Run individual components if needed:

```bash
# Unified scraper only (includes Claude processing)
python -m src.scraper
```

## 📊 Output Files

- **`output/ssrn.csv`**: Raw scraped data from SSRN
- **`output/conferences.csv`**: Final enriched database with AI-extracted information
- **`pipeline.log`**: Detailed processing logs
- **`.claude_cache.pkl`**: Claude API response cache (speeds up future runs)

## 📊 Final Output Structure

The `output/conferences.csv` contains:
- **Title**: Conference title
- **Conference Dates**: Conference dates  
- **Location**: Conference location
- **Link**: SSRN announcement link
- **Submission Deadline**: AI-extracted deadline (e.g., "2025/08/17")
- **Submission Fees**: AI-extracted submission fee (e.g., "$50")
- **Registration Fees**: AI-extracted registration fee (e.g., "$400")  
- **Continent**: AI-extracted continent (e.g., "North America")

## 📁 Project Structure

```
finance-conferences/
├── main.py              # Main pipeline orchestrator
├── config.py            # Configuration management
├── config.json          # Claude API and proxy settings
├── src/                 # Source code
│   ├── __init__.py      # Package initialization
│   └── scraper.py       # Unified scraper with Claude AI processing
├── output/              # Generated data files
│   ├── ssrn.csv         # Raw scraped data (generated)
│   └── conferences.csv  # Final enriched database (generated)
├── requirements.txt     # Python dependencies
├── .claude_cache.pkl    # Claude API response cache (generated)
└── pipeline.log         # Processing logs (generated)
```

## 🔧 Features

### Performance Optimizations
- **Async processing** - 10x faster than traditional scraping
- **Concurrent Claude API calls** - Up to 10x faster AI processing
- **Smart caching** - Speeds up future runs significantly
- **Incremental updates** - Only processes new conferences
- **Optimized connection pooling** - High-performance HTTP requests

### Reliability Features
- **Better duplicate detection** - Normalized title matching with special character removal
- **Graceful error handling** - Comprehensive retry logic and fallback methods
- **Proxy support** - HTTP/HTTPS proxy configuration for corporate networks
- **Configurable timeouts** - Adjustable for different network conditions

## 💡 Best Practices

### For Maximum Speed
- Use **caching** (default enabled)
- Run **incremental updates** (only processes new conferences)
- Use **fast-mode** for initial data collection
- Adjust **concurrency** based on your system capabilities

### For Reliability  
- Configure **proxy settings** if behind corporate firewall
- Use **conservative concurrency** settings in production
- Enable **detailed logging** for debugging
- Monitor **rate limits** and adjust accordingly

## 🚀 Claude Code Integration

This project is optimized for Claude Code usage:
- JSON-based configuration for easy editing
- Modular architecture for clear understanding
- Comprehensive logging for debugging
- Performance optimizations for large-scale scraping

## 📄 License

MIT License