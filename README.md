# Academic Finance Conferences

A pipeline for scraping conference information from SSRN and enriching it with AI-extracted details.

## Overview

This tool automatically:
1. **Scrapes** conference data from SSRN using Selenium
2. **Identifies** new conferences not in your database
3. **Enhances** data using DeepSeek API (deadlines, fees, continent)
4. **Updates** your conference database

## Quick Start

### Prerequisites
- Python 3.7+
- Chrome Browser
- DeepSeek API key

### Installation
```bash
git clone https://github.com/hulaizh/finance-conferences.git
cd finance-conferences
pip install -r requirements.txt
echo "your_deepseek_api_key" > deepseek.txt
```

### Usage
```bash
# Run complete pipeline
python main.py

# Force re-scraping and re-processing
python main.py --force-scrape --force-deepseek
```

## Output

The pipeline generates `conferences.csv` with:
- **Title**: Conference name
- **Conference Dates**: When it occurs
- **Location**: Where it's held
- **Link**: SSRN announcement URL
- **Submission Deadline**: Paper deadline (AI-extracted)
- **Submission Fee**: Cost to submit (AI-extracted)
- **Registration Fee**: Cost to attend (AI-extracted)
- **Continent**: Geographic region (AI-extracted)

## Individual Components

```bash
# Scrape SSRN only
python src/scraper.py

# Process with AI only (requires existing ssrn.csv)
python src/deepseek.py
```

## Project Structure
```
├── main.py              # Main pipeline
├── src/
│   ├── scraper.py       # SSRN scraper
│   └── deepseek.py      # AI processor
├── requirements.txt     # Dependencies
└── deepseek.txt         # API key (create this)
```

## Troubleshooting

**ChromeDriver issues:**
```bash
brew install chromedriver  # macOS
```

**API key issues:**
```bash
echo "your_api_key" > deepseek.txt
```

## License

MIT License - see [LICENSE](LICENSE) file.
