# Academic Finance Conferences

A comprehensive pipeline for scraping, processing, and enriching conference information from SSRN (Social Science Research Network) using AI-powered data extraction.

## 🚀 Overview

The pipeline consists of 4 main steps:
1. **Web Scraping**: Extract conference data from SSRN professional announcements using Selenium
2. **Data Comparison**: Identify new conferences not yet in the database
3. **AI Enhancement**: Use DeepSeek API to extract additional conference details
4. **Database Update**: Merge new data with existing conference database


## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+**
2. **Chrome Browser** installed
3. **ChromeDriver** installed and in PATH
4. **DeepSeek API Key**

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hulaizh/finance-conferences.git
   cd finance-conferences
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up DeepSeek API key**:
   ```bash
   echo "your_deepseek_api_key_here" > deepseek.txt
   ```

4. **Install ChromeDriver**:
   ```bash
   # macOS
   brew install chromedriver
   
   # Or download from: https://chromedriver.chromium.org/
   ```

### Basic Usage

```bash
# Run the complete pipeline (recommended)
python main.py

# Force re-scraping and re-processing
python main.py --force-scrape --force-deepseek
```

## 📖 Usage Guide

### 🎯 Complete Pipeline (Recommended)

The main pipeline orchestrates the entire process automatically:

```bash
python main.py
```

#### What it does:
1. **Scrapes SSRN** → Creates/updates `ssrn.csv` with all conference data
2. **Finds New Conferences** → Compares `ssrn.csv` with existing `conferences.csv`
3. **AI Enhancement** → Uses DeepSeek API to extract additional info for new conferences
4. **Updates Database** → Appends new data to `conferences.csv`

#### Pipeline Options:

```bash
# Force re-scraping even if ssrn.csv exists
python main.py --force-scrape

# Force re-processing all conferences with DeepSeek
python main.py --force-deepseek

# Both options
python main.py --force-scrape --force-deepseek
```

### 🔧 Individual Components

#### 1. SSRN Scraper Only
```bash
python src/scraper.py
```
- Scrapes all conferences from SSRN
- Saves to `ssrn.csv`
- Extracts: title, dates, location, description, links

#### 2. DeepSeek Processor Only
```bash
python src/deepseek.py
```
- Requires existing `ssrn.csv`
- Uses AI to extract: submission deadlines, fees, continent
- Saves to `conferences.csv`

### 📈 Example Workflow

```bash
# First run - processes all conferences
python main.py

# Later runs - only processes new conferences
python main.py

# Force complete refresh
python main.py --force-scrape --force-deepseek
```

## 📊 Output Files

- **`ssrn.csv`**: Raw scraped data from SSRN
- **`conferences.csv`**: Final enriched database with AI-extracted information
- **`conference_pipeline.log`**: Detailed processing logs

## 📊 Final Output Structure

The final `conferences.csv` contains:
- **Title**: Conference title
- **Conference Dates**: Conference dates
- **Location**: Conference location
- **Link**: SSRN announcement link
- **Submission Deadline**: AI-extracted deadline (e.g., "2025/08/17")
- **Submission Fee**: AI-extracted fee (e.g., "$50")
- **Registration Fee**: AI-extracted fee (e.g., "$400")
- **Continent**: AI-extracted continent (e.g., "North America")

## 🎯 Extracted Information

For each conference in `ssrn.csv`, the scraper extracts:

- **title**: Conference title and call for papers information
- **conference_dates**: Conference dates
- **location**: Conference location
- **description**: Detailed conference description from individual SSRN announcement pages
- **ssrn_link**: Direct link to the detailed SSRN announcement

## 📋 Command Line Options

### Main Pipeline
```bash
python main.py [OPTIONS]

Options:
  --force-scrape      Force re-scraping even if ssrn.csv exists
  --force-deepseek    Force re-processing all conferences with DeepSeek
```

### Individual Scraper
```bash
python src/scraper.py [OPTIONS]

Options:
  -h, --help            Show help message
  -o, --output OUTPUT   Output filename (CSV or Excel)
  --no-descriptions     Skip detailed descriptions (faster)
  --headless           Run Chrome in headless mode (default)
  --visible            Run Chrome in visible mode (for debugging)
```

## 📁 Project Structure

```
finance-conferences/
├── main.py                 # Main pipeline orchestrator
├── src/
│   ├── deepseek.py         # DeepSeek API processor
│   └── scraper.py     # Additional extraction utilities
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore file
├── README.md              # This documentation
├── deepseek.txt           # DeepSeek API key (not in repo)
├── ssrn.csv              # Raw scraped data (generated)
├── conferences.csv       # Final enriched database (generated)
└── conference_pipeline.log # Processing logs (generated)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.