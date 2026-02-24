import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, quote
import json
import random

# Rotating User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# CORRECT OLX Pakistan URLs
CITIES = {
    'Lahore': 'https://www.olx.com.pk/lahore/',
    'Karachi': 'https://www.olx.com.pk/karachi/',
    'Islamabad': 'https://www.olx.com.pk/islamabad/',
    'Rawalpindi': 'https://www.olx.com.pk/rawalpindi/'
}

# Correct property categories for OLX
PROPERTY_CATEGORIES = [
    'property-for-sale',  # Changed from properties-for-sale
    'houses',  # Changed from houses-for-sale
    'apartments',  # Changed from apartments-for-sale
    'land-plots',  # Changed from plots-for-sale
]

def get_headers():
    """Get headers with random user agent"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.google.com/',
        'DNT': '1',
    }

def get_property_image(property_url):
    """Fetch property image from OLX property page"""
    try:
        response = requests.get(property_url, headers=get_headers(), timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Method 1: Look for image in gallery/slider
        image_selectors = [
            'div[class*="swiper"] img',
            'div[class*="gallery"] img',
            'div[class*="slider"] img',
            'img[class*="image"]',
            'img[class*="photo"]',
            'meta[property="og:image"]',
        ]
        
        for selector in image_selectors:
            if selector.startswith('meta'):
                meta = soup.find('meta', property='og:image')
                if meta and meta.get('content'):
                    return meta['content']
            else:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    src = img['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    return src
        
        # Method 2: Any image that's not an icon
        images = soup.find_all('img')
        for img in images[:10]:
            src = img.get('src') or img.get('data-src')
            if src and not any(x in src.lower() for x in ['icon', 'logo', 'avatar', 'placeholder', 'pixel']):
                if src.startswith('//'):
                    src = 'https:' + src
                return src
                
    except Exception as e:
        print(f"    ⚠️ Image fetch error: {e}")
    
    return None

def extract_price(text):
    """Extract price from text"""
    patterns = [
        r'(?:PKR|Rs\.?)\s*([\d,]+(?:\.\d+)?)\s*(?:Crore|Lakh|Million)?',
        r'([\d,]+(?:\.\d+)?)\s*(?:Crore|Lakh|Million)',
        r'([\d,]+)\s*(?:Rs|PKR)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            groups = match.groups()
            if len(groups) > 1 and groups[1]:
                return f"PKR {groups[0]} {groups[1]}"
            elif groups[0]:
                return f"PKR {groups[0]}"
    return "Price on Request"

def extract_area(text):
    """Extract area from text"""
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(Marla|Kanal|sqft|sq\.?\s*ft|m²|sqm)',
        r'(\d+)\s*-\s*(\d+)\s*(Marla|Kanal)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return f"{groups[0]}-{groups[1]} {groups[2]}"
            elif len(groups) == 2:
                return f"{match.group(1)} {match.group(2)}"
    return "N/A"

def extract_bed_bath(text):
    """Extract bedrooms and bathrooms from text"""
    beds = "N/A"
    baths = "N/A"
    
    # Bedrooms
    bed_match = re.search(r'(\d+)\s*(?:bed|Bed|bedroom|Bedroom|BR|br)', text)
    if bed_match:
        bed_count = bed_match.group(1)
        beds = f"{bed_count} {'Bed' if bed_count == '1' else 'Beds'}"
    
    # Bathrooms
    bath_match = re.search(r'(\d+)\s*(?:bath|Bath|bathroom|Bathroom|BA|ba)', text)
    if bath_match:
        bath_count = bath_match.group(1)
        baths = f"{bath_count} {'Bath' if bath_count == '1' else 'Baths'}"
    
    return beds, baths

def extract_location(card, default_city):
    """Extract location from card"""
    location_selectors = [
        'span[class*="location"]',
        'span[class*="address"]',
        'div[class*="location"]',
        '[data-testid="location"]',
    ]
    
    for selector in location_selectors:
        elem = card.select_one(selector)
        if elem:
            loc_text = elem.get_text(strip=True)
            if loc_text and len(loc_text) > 3:
                return loc_text
    
    # Try to find in text
    card_text = card.get_text()
    patterns = [
        r'(?:in|at|location)\s+([A-Za-z\s,]+(?:Phase|Sector|Block|Town)?[A-Za-z\s,]*)',
        r'([A-Za-z\s]+(?:Phase|Sector|Block|Town)[\s\d]*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, card_text, re.I)
        if match:
            loc = match.group(1).strip()
            if loc and len(loc) > 3 and loc != default_city:
                return loc
    
    return default_city

def scrape_olx_city(city_name, pages=2):
    """Scrape property listings from OLX Pakistan"""
    
    if city_name not in CITIES:
        print(f"❌ City '{city_name}' not found")
        return []
    
    base_url = CITIES[city_name]
    all_properties = []
    seen_urls = set()
    
    print(f"\n{'='*60}")
    print(f"🚀 Scraping {city_name} from OLX.pk")
    print(f"{'='*60}")

    for page in range(1, pages + 1):
        properties_found = False
        
        for category in PROPERTY_CATEGORIES:
            # Construct OLX search URL - updated format
            if page == 1:
                page_url = f"{base_url}q-{category}/"
            else:
                page_url = f"{base_url}q-{category}/?page={page}"
            
            try:
                print(f"\n📄 Trying: {page_url}")
                
                # Random delay
                time.sleep(random.uniform(3, 5))
                
                response = requests.get(page_url, headers=get_headers(), timeout=25)
                
                if response.status_code != 200:
                    print(f"  ❌ HTTP {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find property listings - updated OLX selectors
                listings = []
                
                listing_selectors = [
                    'div[class*="_1t0I4"]',  # OLX listing card class
                    'div[class*="a38b8"]',
                    'li[class*="_2U8HN"]',
                    'div[class*="ads__item"]',
                    'div[class*="listing-card"]',
                ]
                
                for selector in listing_selectors:
                    found = soup.select(selector)
                    if found:
                        listings = found
                        print(f"  ✅ Found {len(listings)} listings with selector: {selector}")
                        properties_found = True
                        break
                
                # If no listings found with selectors, try finding by structure
                if not listings:
                    # Look for divs containing price and area
                    all_divs = soup.find_all('div', recursive=True)
                    for div in all_divs:
                        div_text = div.get_text().lower()
                        if ('pk' in div_text or 'rs' in div_text) and any(x in div_text for x in ['marla', 'kanal']):
                            if 100 < len(div.get_text()) < 1000:
                                listings.append(div)
                                if len(listings) >= 20:
                                    break
                    
                    if listings:
                        print(f"  ✅ Found {len(listings)} potential listings")
                        properties_found = True
                
                if listings:
                    print(f"  Processing {min(len(listings), 20)} listings...")
                    page_properties = []
                    
                    for i, listing in enumerate(listings[:20]):
                        try:
                            # Get listing text
                            listing_text = listing.get_text(" ", strip=True)
                            
                            # Skip if no price
                            if not re.search(r'(PKR|Rs|Crore|Lakh)', listing_text, re.I):
                                continue
                            
                            # Extract title
                            title = "N/A"
                            title_selectors = [
                                ('h2', None),
                                ('h3', None),
                                ('a', re.compile(r'title|heading', re.I)),
                                ('div', re.compile(r'title|heading', re.I)),
                            ]
                            
                            for tag, class_pattern in title_selectors:
                                if class_pattern:
                                    elem = listing.find(tag, class_=class_pattern)
                                else:
                                    elem = listing.find(tag)
                                
                                if elem:
                                    title_text = elem.get_text(strip=True)
                                    if title_text and len(title_text) > 10:
                                        title = title_text
                                        break
                            
                            # Extract price
                            price = extract_price(listing_text)
                            
                            # Extract area
                            area = extract_area(listing_text)
                            
                            # Extract bedrooms/bathrooms
                            beds, baths = extract_bed_bath(listing_text)
                            
                            # Extract location
                            location = extract_location(listing, city_name)
                            
                            # Extract link
                            link_elem = listing.find('a', href=True)
                            link = None
                            if link_elem:
                                href = link_elem['href']
                                if href.startswith('/'):
                                    link = urljoin('https://www.olx.com.pk', href)
                                elif href.startswith('http'):
                                    link = href
                            
                            if not link or link in seen_urls:
                                continue
                            
                            seen_urls.add(link)
                            
                            # Get image
                            print(f"    📸 Listing {i+1}: Getting image...")
                            image = get_property_image(link)
                            
                            # Create property dictionary
                            prop = {
                                "title": title[:150] + "..." if len(title) > 150 else title,
                                "price": price,
                                "location": location,
                                "area": area,
                                "beds": beds,
                                "baths": baths,
                                "image": image,
                                "url": link,
                                "city": city_name,
                                "source": "OLX.pk"
                            }
                            
                            page_properties.append(prop)
                            print(f"    ✓ Added: {title[:40]}... | {price}")
                            
                            # Small delay
                            time.sleep(random.uniform(1, 2))
                            
                        except Exception as e:
                            print(f"    ⚠️ Error processing listing {i+1}: {e}")
                            continue
                    
                    all_properties.extend(page_properties)
                    print(f"\n  ✅ Page {page}: Extracted {len(page_properties)} properties")
                    
                    # If we found properties in this category, move to next page
                    if page_properties:
                        break
                
            except Exception as e:
                print(f"  ⚠️ Error with {category}: {e}")
                continue
        
        if not properties_found:
            print(f"  ⚠️ No properties found on page {page}")
    
    # Statistics
    with_images = sum(1 for p in all_properties if p['image'])
    print(f"\n{'='*60}")
    print(f"✅ Total: {len(all_properties)} properties scraped from {city_name}")
    if all_properties:
        print(f"📸 Properties with images: {with_images}/{len(all_properties)} ({with_images/len(all_properties)*100:.1f}%)")
    print(f"{'='*60}")
    
    return all_properties

def scrape_olx_multiple_cities(cities=None, pages_per_city=1):
    """Scrape multiple cities"""
    if cities is None:
        cities = list(CITIES.keys())
    
    all_results = {}
    
    for city in cities:
        print(f"\n{'*'*60}")
        print(f"🔄 Switching to {city}")
        print(f"{'*'*60}")
        
        properties = scrape_olx_city(city, pages=pages_per_city)
        all_results[city] = properties
        
        # Delay between cities
        if city != cities[-1]:
            print(f"\n⏳ Waiting before next city...")
            time.sleep(5)
    
    return all_results

def save_to_json(data, filename):
    """Save scraped data to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Data saved to {filename}")

def display_properties(properties, limit=5):
    """Display scraped properties"""
    if not properties:
        print("No properties to display")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 Sample Properties (showing first {limit})")
    print(f"{'='*80}")
    
    for i, prop in enumerate(properties[:limit], 1):
        print(f"\n{i}. {prop['title']}")
        print(f"   💰 Price: {prop['price']}")
        print(f"   📍 Location: {prop['location']}")
        print(f"   📐 Area: {prop['area']}")
        print(f"   🛏️  {prop['beds']} | 🚽 {prop['baths']}")
        if prop['image']:
            print(f"   📸 Image: {prop['image'][:80]}...")
        else:
            print(f"   📸 No image")
        print(f"   🔗 URL: {prop['url'][:60]}...")

# ---------------- TEST ----------------
if __name__ == "__main__":
    print("🚀 Starting OLX.pk Property Scraper")
    print("="*60)
    
    # Test with Lahore
    results = scrape_olx_city("Lahore", pages=1)
    
    # Display results
    display_properties(results)
    
    # Save to file
    if results:
        filename = f"olx_lahore_{time.strftime('%Y%m%d_%H%M%S')}.json"
        save_to_json(results, filename)