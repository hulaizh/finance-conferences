# Finance Conference Scraper

A **high-performance** pipeline for scraping and processing finance conference data from SSRN using AI-powered data extraction.

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+**
2. **DeepSeek API Key**

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up DeepSeek API key
echo "your_deepseek_api_key_here" > deepseek.txt
```

### Basic Usage

```bash
# Run the complete pipeline (3-5 minutes)
python main.py

# Ultra-fast mode - basic info only (1-2 minutes)
python main.py --fast-mode

# Force complete refresh
python main.py --force-scrape --force-deepseek
```

**Note**: The scraper uses multiple automated fallback methods (async requests → Selenium → sync requests) to handle Cloudflare protection and ensure reliable data collection.

## 📖 Usage Guide

### Complete Pipeline

The pipeline automatically:
1. **Scrapes SSRN** → Creates/updates `ssrn.csv` with conference data
2. **Finds New Conferences** → Compares with existing `conferences.csv`
3. **AI Enhancement** → Uses DeepSeek API to extract additional info
4. **Updates Database** → Appends new data to `conferences.csv`

### Command Options

```bash
python main.py [OPTIONS]

Options:
  --force-scrape              Force re-scraping even if ssrn.csv exists
  --force-deepseek            Force re-processing all conferences
  --no-cache                  Disable caching for DeepSeek API calls
  --fast-mode                 Skip detailed scraping for ultra-fast processing
  --max-scrape-concurrent N   Max concurrent connections (default: 3)
  --max-api-concurrent N      Max concurrent API calls (default: 5)
```

### Individual Components

Run individual components if needed:

```bash
# Scraper only (with automatic fallback methods)
python scraper.py

# DeepSeek processor only  
python deepseek.py
```

## 📊 Output Files

- **`ssrn.csv`**: Raw scraped data from SSRN
- **`conferences.csv`**: Final enriched database with AI-extracted information
- **`pipeline.log`**: Detailed processing logs
- **`.deepseek_cache.pkl`**: API response cache (speeds up future runs)

## 📊 Final Output Structure

The `conferences.csv` contains:
- **Title**: Conference title
- **Conference Dates**: Conference dates  
- **Location**: Conference location
- **Link**: SSRN announcement link
- **Submission Deadline**: AI-extracted deadline (e.g., "2025/08/17")
- **Submission Fee**: AI-extracted fee (e.g., "$50")
- **Registration Fee**: AI-extracted fee (e.g., "$400")  
- **Continent**: AI-extracted continent (e.g., "North America")

## 📁 Project Structure

```
finance-conferences/
├── main.py              # Main pipeline orchestrator
├── scraper.py           # High-performance SSRN scraper with fallback methods
├── deepseek.py          # Fast DeepSeek API processor
├── requirements.txt     # Python dependencies
├── README.md           # This documentation
├── deepseek.txt        # DeepSeek API key (not in repo)
├── .deepseek_cache.pkl # API response cache (generated)
├── ssrn.csv           # Raw scraped data (generated)
├── conferences.csv    # Final enriched database (generated)
└── pipeline.log       # Processing logs (generated)
```

## 💡 Best Practices

### For Maximum Speed
- Use **caching** (default enabled)
- Run **incremental updates** (only processes new conferences)
- Use **fast-mode** for initial data collection
- Adjust **concurrency** based on your system capabilities

### For Reliability  
- Use **conservative concurrency** settings in production
- Enable **detailed logging** for debugging
- Monitor **rate limits** and adjust accordingly

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License