import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.property1.pk/',
}

CITIES = {
    'Islamabad': 'https://www.property1.pk/all-properties/?s=&filters%5Bad_type%5D=&rtcl_location=islamabad',
    'Rawalpindi': 'https://www.property1.pk/all-properties/?s=&filters%5Bad_type%5D=&rtcl_location=rawalpindi',
    'Lahore': 'https://www.property1.pk/all-properties/?s=&filters%5Bad_type%5D=&rtcl_location=lahore',
    'Karachi': 'https://www.property1.pk/all-properties/?s=&filters%5Bad_type%5D=&rtcl_location=karachi'
}

def get_page_url(base_url, page_num):
    """Generate URL for specific page number"""
    if page_num == 1:
        return base_url
    if '/page/' in base_url:
        return re.sub(r'/page/\d+', f'/page/{page_num}', base_url)
    else:
        if '?' in base_url:
            return base_url.replace('?', f'/page/{page_num}/?')
        else:
            return f"{base_url}/page/{page_num}/"

def extract_image_from_style(element):
    """Extract image URL from style attribute"""
    style = element.get('style', '')
    if style:
        # Look for background-image: url('...')
        bg_match = re.search(r'background-image:\s*url\([\'"]?([^\'"]+)[\'"]?\)', style, re.I)
        if bg_match:
            return bg_match.group(1)
        
        # Look for background: url('...')
        bg_match = re.search(r'background:\s*url\([\'"]?([^\'"]+)[\'"]?\)', style, re.I)
        if bg_match:
            return bg_match.group(1)
    return None

def extract_property_data(card, city_name):
    """Extract property data from a card on Property1.pk"""
    try:
        # --- TITLE ---
        title_elem = card.find('h3') or card.find('h2') or card.find('div', class_=re.compile('title', re.I))
        title = title_elem.get_text(strip=True) if title_elem else 'N/A'
        
        # --- PRICE ---
        price = 'N/A'
        price_selectors = [
            card.find('span', class_=re.compile('price|amount', re.I)),
            card.find('div', class_=re.compile('price|amount', re.I)),
            card.find('li', class_=re.compile('price', re.I)),
            card.find('span', {'itemprop': 'price'})
        ]
        
        for selector in price_selectors:
            if selector:
                price_text = selector.get_text(strip=True)
                if price_text and re.search(r'[\d,]+|PKR|Rs', price_text):
                    price = price_text
                    break
        
        if price == 'N/A':
            card_text = card.get_text()
            price_match = re.search(r'(PKR|Rs\.?)\s*([\d,]+(?:\.\d+)?\s*(?:Crore|Lakh|Million)?)', card_text, re.I)
            if price_match:
                price = price_match.group(0)
        
        # --- LOCATION ---
        location = 'N/A'
        location_selectors = [
            card.find('div', class_=re.compile('location|address', re.I)),
            card.find('span', class_=re.compile('location|address', re.I)),
            card.find('li', class_=re.compile('location', re.I)),
            card.find('div', {'itemprop': 'address'})
        ]
        
        for selector in location_selectors:
            if selector:
                loc_text = selector.get_text(strip=True)
                if loc_text and len(loc_text) > 3:
                    location = loc_text
                    break
        
        # --- AREA / SIZE ---
        area = 'N/A'
        card_text = card.get_text()
        
        area_patterns = [
            r'(\d+[\.,]?\d*)\s*(Marla|marla)',
            r'(\d+[\.,]?\d*)\s*(Kanal|kanal)',
            r'(\d+[\.,]?\d*)\s*(sq\.?\s*ft|sqft)',
            r'(\d+[\.,]?\d*)\s*(Square\s*(Feet|Meter|Yards))'
        ]
        
        for pattern in area_patterns:
            area_match = re.search(pattern, card_text, re.I)
            if area_match:
                area = f"{area_match.group(1)} {area_match.group(2)}"
                break
        
        if area == 'N/A':
            title_match = re.search(r'(\d+)\s*(Marla|Kanal)', title, re.I)
            if title_match:
                area = f"{title_match.group(1)} {title_match.group(2)}"
        
        # --- ENHANCED IMAGE EXTRACTION ---
        image = None
        
        # METHOD 1: Find all images and check all possible attributes
        all_images = card.find_all('img')
        for img in all_images:
            # List of all possible image URL attributes
            img_attrs = [
                'src', 'data-src', 'data-lazy-src', 'data-original', 
                'data-url', 'data-image', 'data-img', 'data-srcset',
                'srcset', 'data-default', 'data-lazy', 'data-echo'
            ]
            
            for attr in img_attrs:
                img_url = img.get(attr)
                if img_url:
                    # Handle srcset specially
                    if attr == 'srcset' or attr == 'data-srcset':
                        # Extract first URL from srcset
                        if ',' in img_url:
                            first_part = img_url.split(',')[0].strip()
                            img_url = first_part.split(' ')[0].strip()
                    
                    # Clean up URL
                    if img_url:
                        if img_url.startswith('//'):
                            img_url = 'https:' + img_url
                        elif img_url.startswith('/') and not img_url.startswith('//'):
                            img_url = 'https://www.property1.pk' + img_url
                        
                        # Check if it's a valid image
                        if re.search(r'\.(jpg|jpeg|png|webp|gif|bmp|avif)', img_url.lower()):
                            # Filter out icons and placeholders
                            if not any(x in img_url.lower() for x in ['icon', 'logo', 'placeholder', 'svg', 'blank']):
                                image = img_url
                                break
            if image:
                break
        
        # METHOD 2: Look for divs with background-image style
        if not image:
            # Find elements with style containing background-image
            styled_elements = card.find_all(lambda tag: tag.get('style') and 'background' in tag.get('style').lower())
            for elem in styled_elements:
                img_url = extract_image_from_style(elem)
                if img_url:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = 'https://www.property1.pk' + img_url
                    
                    if re.search(r'\.(jpg|jpeg|png|webp|gif)', img_url.lower()):
                        image = img_url
                        break
        
        # METHOD 3: Look for meta tags with image
        if not image:
            meta_image = card.find('meta', {'property': 'og:image'}) or card.find('meta', {'itemprop': 'image'})
            if meta_image and meta_image.get('content'):
                img_url = meta_image.get('content')
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                image = img_url
        
        # METHOD 4: Look for any link ending with image extensions
        if not image:
            img_links = card.find_all('a', href=re.compile(r'\.(jpg|jpeg|png|webp|gif)', re.I))
            for link in img_links:
                img_url = link.get('href')
                if img_url:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = 'https://www.property1.pk' + img_url
                    image = img_url
                    break
        
        # METHOD 5: Look for data attributes that might contain image URLs
        if not image:
            for elem in card.find_all(True):
                for attr, value in elem.attrs.items():
                    if isinstance(value, str) and re.search(r'\.(jpg|jpeg|png|webp|gif)', value.lower()):
                        if 'src' in attr or 'img' in attr or 'image' in attr or 'data' in attr:
                            img_url = value
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = 'https://www.property1.pk' + img_url
                            image = img_url
                            break
                if image:
                    break
        
        # METHOD 6: Try to construct image URL from property ID (if available)
        if not image:
            # Look for property ID
            prop_id_match = re.search(r'property[_-]?id[=:]"?(\d+)"?', str(card), re.I)
            if prop_id_match:
                prop_id = prop_id_match.group(1)
                # Common image URL patterns
                possible_urls = [
                    f'https://www.property1.pk/wp-content/uploads/{prop_id}.jpg',
                    f'https://www.property1.pk/storage/properties/{prop_id}.jpg',
                    f'https://www.property1.pk/images/properties/{prop_id}.jpg'
                ]
                # We can't verify these without making additional requests, but we can try the first one
                image = possible_urls[0]
        
        # --- LINK ---
        link = None
        link_elem = card.find('a', href=True)
        if link_elem:
            href = link_elem.get('href')
            if href:
                link = urljoin('https://www.property1.pk', href)
        
        return {
            'title': title[:120] + '...' if len(title) > 120 else title,
            'price': price,
            'location': location,
            'area': area,
            'image': image,
            'url': link,
            'city': city_name,
            'source': 'Property1.pk'
        }
        
    except Exception as e:
        print(f"Error extracting property: {e}")
        return None

def find_property_cards(soup):
    """Find all property cards on the page"""
    selectors = [
        ('div', {'class': re.compile(r'listing-item|property-item|rtcl-listing-item', re.I)}),
        ('div', {'class': re.compile(r'col.*?property', re.I)}),
        ('article', {'class': re.compile(r'listing|property', re.I)}),
        ('div', {'class': re.compile(r'item', re.I)}),
        ('li', {'class': re.compile(r'listing', re.I)}),
        ('div', {'class': re.compile(r'property-box', re.I)}),
        ('div', {'data-rtcl': re.compile(r'listing', re.I)})
    ]
    
    cards = []
    for tag, attrs in selectors:
        found = soup.find_all(tag, attrs)
        if found:
            cards.extend(found)
    
    # Remove duplicates while preserving order
    unique_cards = []
    seen = set()
    for card in cards:
        # Create a unique identifier for the card
        card_html = str(card)[:200]  # First 200 chars as identifier
        if card_html not in seen:
            seen.add(card_html)
            unique_cards.append(card)
    
    return unique_cards

def scrape_property1_city(city_name, pages=1):
    """Scrape Property1.pk for a specific city"""
    url = CITIES[city_name]
    all_properties = []
    
    print(f"\nScraping {city_name} from Property1.pk")
    
    for page in range(1, pages + 1):
        page_url = get_page_url(url, page)
        print(f"  Page {page}: {page_url}")
        
        try:
            # Add a longer delay for Property1
            time.sleep(3)
            
            response = requests.get(page_url, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find property cards
            cards = find_property_cards(soup)
            
            if not cards:
                print(f"  No cards found on page {page}")
                continue
            
            print(f"  Found {len(cards)} cards")
            
            # Extract data from each card
            page_properties = []
            for card in cards[:20]:
                prop = extract_property_data(card, city_name)
                if prop and prop['title'] != 'N/A':
                    page_properties.append(prop)
                    all_properties.append(prop)
            
            print(f"  Extracted {len(page_properties)} properties")
            
            # Count properties with images
            images_found = sum(1 for p in page_properties if p.get('image'))
            print(f"  Images found: {images_found}/{len(page_properties)}")
            
            # If no images, print debug info for first property
            if images_found == 0 and page_properties:
                print(f"  Debug - First property card HTML preview: {str(cards[0])[:500]}")
            
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            continue
    
    return all_properties