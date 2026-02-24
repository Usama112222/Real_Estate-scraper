import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin
import json
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)

adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

# Rotating User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
]

CITIES = {
    'Lahore': 'https://www.zameen.com/Homes/Lahore-1-1.html',
    'Karachi': 'https://www.zameen.com/Homes/Karachi-2-1.html',
    'Rawalpindi': 'https://www.zameen.com/Homes/Rawalpindi-41-1.html',
    'Islamabad': 'https://www.zameen.com/Homes/Islamabad-3-1.html'
}

def clean_text(text):
    """Clean extracted text"""
    if text:
        return ' '.join(text.split())
    return 'N/A'

def extract_price_from_text(text):
    """Extract price using regex patterns"""
    if not text:
        return 'N/A'
    
    patterns = [
        r'(?:PKR|Rs\.?)\s*([\d,]+(?:\.\d+)?)\s*(Crore|Lakh|Million|Arab)?',
        r'([\d,]+(?:\.\d+)?)\s*(Crore|Lakh|Million|Arab)\s*(?:PKR|Rs\.?)?',
        r'([\d,]+(?:\.\d+)?)\s*(?:Crore|Lakh|Million|Arab)',
        r'(?:PKR|Rs\.?)\s*([\d,]+(?:\.\d+)?)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                return f"{groups[0]} {groups[1]}"
            elif groups[0]:
                return f"PKR {groups[0]}"
    
    return 'N/A'

def extract_area_from_text(text):
    """Extract area with unit"""
    if not text:
        return 'N/A'
    
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(Marla|Kanal|Square\s*Feet|Sq\.?\s*Ft\.?|sqft|marla|kanal)',
        r'(\d+)\s*-\s*(\d+)\s*(Marla|Kanal)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return f"{groups[0]}-{groups[1]} {groups[2]}"
            elif len(groups) == 2:
                return f"{groups[0]} {groups[1]}"
    
    return 'N/A'

def extract_property_data(card, city_name):
    """Extract property data from a card"""
    try:
        card_html = str(card)
        card_text = card.get_text(separator=' ', strip=True)
        
        # Extract TITLE
        title = 'N/A'
        title_selectors = ['h2', 'h3', 'span[aria-label="Title"]', 'div[class*="title"]', 'a[class*="title"]']
        
        for selector in title_selectors:
            if '[' in selector:
                elem = card.select_one(selector)
            else:
                elem = card.find(selector)
            if elem:
                title = clean_text(elem.get_text())
                if title and len(title) > 10:
                    break
        
        if title == 'N/A' or len(title) < 10:
            sentences = card_text.split('.')
            for sent in sentences:
                if any(word in sent.lower() for word in ['house', 'flat', 'apartment', 'plot', 'property']):
                    title = clean_text(sent)
                    break
        
        # Extract PRICE
        price = 'N/A'
        price_selectors = [
            'span[class*="price"]', 'div[class*="price"]', 'span[aria-label="Price"]',
            'span[class*="amount"]', 'div[class*="Payment"]'
        ]
        
        for selector in price_selectors:
            elem = card.select_one(selector)
            if elem:
                price_text = clean_text(elem.get_text())
                if price_text and any(x in price_text.lower() for x in ['pk', 'rs', 'crore', 'lakh']):
                    price = price_text
                    break
        
        if price == 'N/A':
            price = extract_price_from_text(card_html)
        if price == 'N/A':
            price = extract_price_from_text(card_text)
        
        # Extract LOCATION
        location = 'N/A'
        location_selectors = [
            'div[class*="location"]', 'span[class*="location"]', 'div[class*="address"]',
            'span[aria-label="Location"]'
        ]
        
        for selector in location_selectors:
            elem = card.select_one(selector)
            if elem:
                location_text = clean_text(elem.get_text())
                if location_text and len(location_text) > 5:
                    location = location_text
                    break
        
        if location == 'N/A':
            location_patterns = [
                r'([A-Za-z\s]+(?:Phase|Sector|Block|Town|City)[\s\d,]+[A-Za-z\s]*)',
                r'(?:Location|Address)[:\s]*([^,]+(?:,[^,]+){0,2})',
            ]
            for pattern in location_patterns:
                match = re.search(pattern, card_text, re.IGNORECASE)
                if match:
                    location = clean_text(match.group(1))
                    break
        
        # Extract AREA
        area = 'N/A'
        area_selectors = [
            'div[class*="area"]', 'span[class*="area"]', 'div[class*="size"]',
            'span[aria-label="Area"]'
        ]
        
        for selector in area_selectors:
            elem = card.select_one(selector)
            if elem:
                area_text = clean_text(elem.get_text())
                if area_text and any(x in area_text.lower() for x in ['marla', 'kanal', 'sq', 'yard']):
                    area = area_text
                    break
        
        if area == 'N/A':
            area = extract_area_from_text(card_text)
        if area == 'N/A':
            area = extract_area_from_text(title)
        
        # Extract IMAGE
        image = None
        img = card.find('img')
        if img:
            image = img.get('src') or img.get('data-src')
            if image:
                if image.startswith('//'):
                    image = 'https:' + image
                elif image.startswith('/'):
                    image = urljoin('https://www.zameen.com', image)
        
        # Extract URL
        url = None
        link_elem = card.find('a', href=True)
        if link_elem:
            href = link_elem['href']
            if '/property/' in href.lower() or '/homes/' in href.lower():
                url = urljoin('https://www.zameen.com', href)
        
        # Clean up
        if location and re.match(r'^[\d\s,]+$', location):
            location = 'N/A'
        
        return {
            'title': title if title and len(title) > 5 else 'N/A',
            'price': price,
            'location': location,
            'area': area,
            'image': image,
            'url': url,
            'city': city_name
        }
        
    except Exception as e:
        print(f"Error extracting property: {e}")
        return None

def scrape_zameen_city(city_name, pages=1, delay=2):
    """Main function to scrape Zameen.com for a specific city"""
    if city_name not in CITIES:
        print(f"City {city_name} not found in CITIES dictionary")
        return []
    
    base_url = CITIES[city_name]
    all_properties = []
    
    # Rotate user agent
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for page in range(1, pages + 1):
        if page == 1:
            page_url = base_url
        else:
            page_url = re.sub(r'-\d+\.html$', f'-{page}.html', base_url)
        
        try:
            print(f"🌐 Scraping {city_name} - Page {page}: {page_url}")
            
            response = requests.get(page_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find property cards
            cards = []
            card_selectors = [
                'li[role="article"]',
                'article[class*="card"]',
                'div[class*="property-card"]',
                'div[class*="listing-card"]',
                'div[class*="card"]',
            ]
            
            for selector in card_selectors:
                found_cards = soup.select(selector)
                if found_cards:
                    cards = found_cards
                    print(f"  Found {len(cards)} cards with selector: {selector}")
                    break
            
            if not cards:
                all_divs = soup.find_all('div', recursive=True)
                potential_cards = []
                for div in all_divs:
                    div_text = div.get_text().lower()
                    if all(keyword in div_text for keyword in ['pk', 'crore', 'marla', 'kanal']):
                        if len(div.get_text()) > 50:
                            potential_cards.append(div)
                if potential_cards:
                    cards = potential_cards[:20]
                    print(f"  Found {len(cards)} potential property divs")
            
            # Process cards
            for i, card in enumerate(cards[:20]):
                prop = extract_property_data(card, city_name)
                if prop and prop['title'] != 'N/A' and prop['price'] != 'N/A':
                    all_properties.append(prop)
                    print(f"  ✓ Property {i+1}: {prop['title'][:50]}... | {prop['price']}")
            
            print(f"  ✅ Extracted {len([p for p in cards[:20] if p])} properties from page {page}")
            time.sleep(delay)
            
        except Exception as e:
            print(f"❌ Error scraping page {page}: {e}")
            continue
    
    return all_properties

def scrape_multiple_cities(cities_to_scrape=None, pages_per_city=2):
    """Scrape multiple cities"""
    if cities_to_scrape is None:
        cities_to_scrape = list(CITIES.keys())
    
    all_results = {}
    
    for city in cities_to_scrape:
        print(f"\n{'='*60}")
        print(f"🚀 Starting scrape for {city}")
        print('='*60)
        
        properties = scrape_zameen_city(city, pages=pages_per_city)
        all_results[city] = properties
        
        print(f"\n✅ Completed {city}: Found {len(properties)} properties")
        time.sleep(3)
    
    return all_results

def save_to_json(data, filename='zameen_properties.json'):
    """Save scraped data to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Data saved to {filename}")

def display_results(properties):
    """Display scraped properties"""
    if not properties:
        print("No properties found")
        return
    
    for i, prop in enumerate(properties, 1):
        print(f"\n{'='*80}")
        print(f"Property #{i} - {prop['city']}")
        print(f"{'='*80}")
        print(f"🏠 Title: {prop['title']}")
        print(f"💰 Price: {prop['price']}")
        print(f"📍 Location: {prop['location']}")
        print(f"📐 Area: {prop['area']}")
        if prop['url']:
            print(f"🔗 URL: {prop['url']}")

# If run directly
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        city = sys.argv[1]
        pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    else:
        print("Available cities: Lahore, Karachi, Rawalpindi, Islamabad")
        city = input("Enter city name: ").strip()
        pages = int(input("Enter number of pages (default 2): ") or "2")
    
    properties = scrape_zameen_city(city, pages=pages)
    display_results(properties)
    
    if properties:
        save = input("\nSave to JSON? (y/n): ").lower()
        if save == 'y':
            filename = f"zameen_{city.lower()}_{time.strftime('%Y%m%d_%H%M%S')}.json"
            save_to_json(properties, filename)