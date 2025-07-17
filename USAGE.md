# 📖 Conference Pipeline Usage Guide

## 🎯 Complete Pipeline (Recommended)

The main pipeline orchestrates the entire process automatically:

```bash
python main.py
```

### What it does:
1. **Scrapes SSRN** → Creates/updates `ssrn.csv` with all conference data
2. **Finds New Conferences** → Compares `ssrn.csv` with existing `conferences.csv`
3. **AI Enhancement** → Uses DeepSeek API to extract additional info for new conferences
4. **Updates Database** → Appends new data to `conferences.csv`

### Pipeline Options:

```bash
# Force re-scraping even if ssrn.csv exists
python main.py --force-scrape

# Force re-processing all conferences with DeepSeek
python main.py --force-deepseek

# Both options
python main.py --force-scrape --force-deepseek
```

## 🔧 Individual Components

### 1. SSRN Scraper Only
```bash
python src/scraper.py
```
- Scrapes all conferences from SSRN
- Saves to `ssrn.csv`
- Extracts: title, dates, location, description, links

### 2. DeepSeek Processor Only
```bash
python src/deepseek.py
```
- Requires existing `ssrn.csv`
- Uses AI to extract: submission deadlines, fees, continent
- Saves to `conferences.csv`

## 📊 Output Files

- **`ssrn.csv`**: Raw scraped data from SSRN
- **`conferences.csv`**: Final enriched database with AI-extracted information
- **`conference_pipeline.log`**: Detailed processing logs

## 🔑 Prerequisites

1. **Python 3.7+**
2. **Chrome Browser** installed
3. **DeepSeek API Key** in `deepseek.txt`
4. **Dependencies**: `pip install -r requirements.txt`

## 📈 Example Workflow

```bash
# First run - processes all conferences
python main.py

# Later runs - only processes new conferences
python main.py

# Force complete refresh
python main.py --force-scrape --force-deepseek
```

## 🎯 Final Output Structure

The final `conferences.csv` contains:
- **Title**: Conference title
- **Conference Dates**: Conference dates  
- **Location**: Conference location
- **Link**: SSRN announcement link
- **Submission Deadline**: AI-extracted deadline (e.g., "2025/08/17")
- **Submission Fee**: AI-extracted fee (e.g., "$50")
- **Registration Fee**: AI-extracted fee (e.g., "$400") 
- **Continent**: AI-extracted continent (e.g., "North America")
