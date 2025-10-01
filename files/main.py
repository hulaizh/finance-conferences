#!/usr/bin/env python3
"""
Finance Conferences Website Generator

Reads conference data from files/conferences.xlsx and generates complete website pages
with title case formatting, proper styling, and responsive design.

USAGE:
    python files/main.py

REQUIREMENTS:
    - files/conferences.xlsx must exist with conference data
    - style.css and script.js should be in the project root
    - pandas library must be installed (pip install pandas openpyxl)

OUTPUT:
    - index.html: Future conferences (upcoming deadlines)
    - past.html: Past conferences (expired deadlines)

The script automatically:
    - Filters conferences by deadline date (today's date)
    - Sorts future conferences by deadline (closest first)
    - Sorts past conferences by deadline (most recent first)
    - Applies title case formatting to all text
    - Generates responsive HTML with proper navigation
"""

import pandas as pd
from datetime import datetime
import re

# Common finance/academic acronyms that should remain uppercase
FINANCE_ACRONYMS = {
    # Finance organizations & journals
    'cuhk', 'rfs', 'ecgi', 'rcf', 'cepr', 'raps', 'rcfs', 'afa', 'sfs', 'fma',
    'jfe', 'jf', 'nber', 'ssrn', 'swfa', 'mfa', 'nyse', 'wfe', 'sgf',

    # Universities & institutions
    'nycu', 'nyu', 'mit', 'ucla', 'cmu', 'lsu', 'utah', 'vins',

    # Technology & topics
    'ai', 'cafm', 'gras', 'phd', 'mba', 'cfa', 'cpa', 'msc', 'bsc',

    # Geographic abbreviations
    'usa', 'uk', 'eu', 'us', 'ny', 'la', 'tx', 'nc', 'il', 'fl', 'ca', 'on',
    'vic', 'ut', 'nv', 'nh', 'pa', 'ma', 'dc', 'oh', 'mi', 'ga', 'va',

    # Additional common finance terms
    'ceo', 'cfo', 'ipo', 'etf', 'sec', 'fed', 'gdp', 'roi', 'esg', 'kyc',
    'aml', 'basel', 'ifrs', 'gaap', 'fasb', 'iasb', 'bis', 'imf', 'oecd'
}

# Small words that should be lowercase in title case (except when first or last word)
SMALL_WORDS = {
    'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 'of', 'on',
    'or', 'the', 'to', 'up', 'yet', 'so', 'nor', 'with', 'from', 'into', 'onto',
    'upon', 'over', 'under', 'above', 'below', 'through', 'between', 'among',
    'during', 'before', 'after', 'since', 'until', 'while', 'where', 'when'
}

def smart_title_case(text):
    """Apply title case while preserving common finance acronyms in uppercase."""
    if not text or text == 'N/A':
        return text

    words = text.split()
    result_words = []

    for i, word in enumerate(words):
        # Handle hyphenated words separately
        if '-' in word:
            parts = word.split('-')
            result_parts = []
            for j, part in enumerate(parts):
                clean_part = re.sub(r'[^\w]', '', part.lower())
                if clean_part in FINANCE_ACRONYMS:
                    # Make this part uppercase
                    upper_part = ''
                    for char in part:
                        if char.isalpha():
                            upper_part += char.upper()
                        else:
                            upper_part += char
                    result_parts.append(upper_part)
                elif clean_part in SMALL_WORDS and j > 0 and j < len(parts) - 1:
                    # Small words in middle of hyphenated compound stay lowercase
                    result_parts.append(part.lower())
                else:
                    result_parts.append(part.title())
            result_words.append('-'.join(result_parts))
            continue

        # Remove punctuation for comparison but keep it for the final word
        clean_word = re.sub(r'[^\w]', '', word.lower())

        # Check if it's an ordinal number (1st, 2nd, 3rd, 4th, etc.)
        ordinal_pattern = r'^\d+(st|nd|rd|th)$'
        if re.match(ordinal_pattern, clean_word):
            # Keep ordinals as lowercase except for numbers
            result_word = ''
            for char in word:
                if char.isdigit():
                    result_word += char
                elif char.isalpha():
                    result_word += char.lower()
                else:
                    result_word += char
            result_words.append(result_word)
        elif clean_word in FINANCE_ACRONYMS:
            # Preserve the original punctuation but make the letters uppercase
            result_word = ''
            for char in word:
                if char.isalpha():
                    result_word += char.upper()
                else:
                    result_word += char
            result_words.append(result_word)
        elif clean_word in SMALL_WORDS and i > 0 and i < len(words) - 1:
            # Small words in middle of title stay lowercase (preserve punctuation)
            result_word = ''
            for char in word:
                if char.isalpha():
                    result_word += char.lower()
                else:
                    result_word += char
            result_words.append(result_word)
        else:
            # Apply title case normally
            result_words.append(word.title())

    return ' '.join(result_words)

def read_conference_data():
    """Read conference data from Excel file."""
    try:
        df = pd.read_excel('files/conferences.xlsx')
        return df
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def parse_date(date_str):
    """Parse date string to datetime object."""
    if pd.isna(date_str) or not date_str:
        return None
    try:
        # Try parsing with timestamp first (YYYY-MM-DD HH:MM:SS)
        return datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
    except:
        try:
            # Fall back to date only format (YYYY-MM-DD)
            return datetime.strptime(str(date_str), '%Y-%m-%d')
        except:
            return None

def filter_conferences(df, future=True):
    """Filter conferences by deadline date."""
    today = datetime.now().date()

    # Convert DDL column to datetime
    df['ddl_date'] = df['DDL'].apply(parse_date)

    if future:
        # Future conferences: DDL >= today, sorted by deadline (closest first)
        filtered = df[df['ddl_date'].notna() & (df['ddl_date'].dt.date >= today)]
        return filtered.sort_values('ddl_date', ascending=True)
    else:
        # Past conferences: DDL < today, sorted by deadline reversed (most recent past first)
        filtered = df[df['ddl_date'].notna() & (df['ddl_date'].dt.date < today)]
        return filtered.sort_values('ddl_date', ascending=False)

def generate_table_html(df, table_id="conferencesTable"):
    """Generate HTML table from conference data."""
    if df.empty:
        return '<p class="paper-abstract">No conferences found.</p>'

    html = f'''

    <div class="table-container">
        <table id="{table_id}" class="conferences-table">
            <thead>
                <tr>
                    <th>Conference Name</th>
                    <th>Deadline</th>
                    <th>Conference Date</th>
                    <th>Continent</th>
                    <th>Location</th>
                </tr>
            </thead>
            <tbody>
    '''

    for _, row in df.iterrows():
        # Format conference name with link - apply smart title case
        conf_name = smart_title_case(str(row['name'])) if pd.notna(row['name']) else 'N/A'
        continent = smart_title_case(str(row['continent'])) if pd.notna(row['continent']) else 'N/A'
        location = smart_title_case(str(row['location'])) if pd.notna(row['location']) else 'N/A'
        conf_date = str(row['conferenceDate']) if pd.notna(row['conferenceDate']) else 'N/A'
        # Strip time component from DDL display
        ddl_str = str(row['DDL']) if pd.notna(row['DDL']) else 'N/A'
        ddl = ddl_str.split(' ')[0] if ' ' in ddl_str else ddl_str
        link = str(row['link']) if pd.notna(row['link']) else '#'

        # Create clickable conference name
        name_cell = f'<a href="{link}" target="_blank" rel="noopener" class="conference-link">{conf_name}</a>'

        html += f'''
                <tr data-continent="{continent}">
                    <td>{name_cell}</td>
                    <td>{ddl}</td>
                    <td>{conf_date}</td>
                    <td>{continent}</td>
                    <td title="{location}">{location}</td>
                </tr>
        '''

    html += '''
            </tbody>
        </table>
    </div>
    '''

    return html

def generate_html_page(conferences_html, title, page_type="future"):
    """Generate complete HTML page."""
    # Different descriptions based on page type
    if page_type == "future":
        description = "Upcoming academic finance conferences with submission deadlines."
        page_description = '<p class="page-description">Upcoming submission deadlines for academic finance conferences.</p>'
        nav_active = 'active'
        other_nav = ''
    else:
        description = "Past academic finance conferences with expired submission deadlines."
        page_description = '<p class="page-description">Past submission deadlines for academic finance conferences.</p>'
        nav_active = ''
        other_nav = 'active'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="author" content="Hulai Zhang">
<link rel="canonical" href="https://conf.hulaizh.com/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="files/icon.ico" sizes="any">
<script src="script.js" defer></script>
</head>
<body>
<nav class="navbar">
<div class="navbar-brand">
<a href="index.html" class="navbar-title">Finance Conferences</a>
</div>
<div class="navbar-nav">
<button class="mobile-menu-toggle" onclick="toggleMobileMenu()" aria-label="Toggle navigation menu">
<span class="hamburger-line"></span>
<span class="hamburger-line"></span>
<span class="hamburger-line"></span>
</button>
<div class="nav-links">
<a href="index.html" class="nav-link {nav_active}">Home</a><span class="nav-separator"> | </span><a href="past.html" class="nav-link {other_nav}">Past Conferences</a>
</div>
</div>
</nav>
<main class="main-content">
<div class="page-header">
<h1>{title}</h1>
{page_description}
</div>
{conferences_html}
<footer class="page-footer">
<p>Collected by <a href="https://hulaizh.com" target="_blank" rel="noopener" class="author-link">Hulai Zhang</a></p>
</footer>
</main>
</body>
</html>'''

    return html


def main():
    """Main function to generate complete website from Excel data."""
    print("🔄 Finance Conferences Website Generator")
    print("=" * 50)

    # Read conference data
    print("📊 Reading conference data from files/conferences.xlsx...")
    df = read_conference_data()

    if df is None:
        print("❌ Failed to read conference data. Exiting.")
        return

    print(f"✅ Loaded {len(df)} conferences")

    # Filter conferences by deadline
    today = datetime.now().date()
    future_conferences = filter_conferences(df, future=True)
    past_conferences = filter_conferences(df, future=False)

    print(f"📅 Future conferences (DDL >= {today}): {len(future_conferences)}")
    print(f"📚 Past conferences (DDL < {today}): {len(past_conferences)}")

    # Generate HTML content
    print("\n🔨 Generating HTML pages...")
    future_table = generate_table_html(future_conferences, "conferencesTable")
    past_table = generate_table_html(past_conferences, "pastConferencesTable")

    # Generate complete HTML pages with proper styling
    future_html = generate_html_page(future_table, "Academic Finance Conferences", "future")
    past_html = generate_html_page(past_table, "Past Finance Conferences", "past")

    # Write HTML files to project root
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(future_html)
    print("✅ Generated index.html")

    with open('past.html', 'w', encoding='utf-8') as f:
        f.write(past_html)
    print("✅ Generated past.html")

    print("\n🎉 Website generation complete!")
    print("📁 Files generated:")
    print("   - index.html: Upcoming submission deadlines")
    print("   - past.html: Past submission deadlines")
    print("\n💡 Open index.html in your browser to view the website")
    print("🔗 Make sure style.css and script.js are in the same directory")

if __name__ == "__main__":
    main()