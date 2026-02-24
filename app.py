from flask import Response
import requests
from flask import Flask, render_template, request, jsonify
from zameen_scraper import scrape_zameen_city as scrape_zameen
from property1_scraper import scrape_property1_city as scrape_property1
from olx_scraper import scrape_olx_city as scrape_olx 

app = Flask(__name__)

# Available cities for each source
ZAMEEN_CITIES = ['Lahore', 'Karachi', 'Rawalpindi', 'Islamabad']
PROPERTY1_CITIES = ['Islamabad', 'Rawalpindi', 'Lahore', 'Karachi']
OLX_CITIES = ['Lahore', 'Karachi', 'Islamabad', 'Rawalpindi'] 

@app.route('/')
def index():
    return render_template('index.html', 
                         zameen_cities=ZAMEEN_CITIES,
                         property1_cities=PROPERTY1_CITIES,
                         olx_cities=OLX_CITIES)  

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    source = data.get('source')
    city = data.get('city')
    pages = int(data.get('pages', 1))
    
    if not source or not city:
        return jsonify({'error': 'Missing source or city'}), 400
    
    try:
        if source == 'zameen':
            properties = scrape_zameen(city, pages)
        elif source == 'property1':
            properties = scrape_property1(city, pages)
        elif source == 'olx':  
            properties = scrape_olx(city, pages) 
        else:
            return jsonify({'error': 'Invalid source'}), 400
        
        return jsonify({
            'success': True,
            'source': source,
            'city': city,
            'total': len(properties),
            'properties': properties
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route("/image-proxy")
def image_proxy():
    image_url = request.args.get("url")

    if not image_url:
        return "No URL provided", 400

    try:
        # Determine referer based on domain
        referer = "https://www.google.com/"
        if "zameen.com" in image_url:
            referer = "https://www.zameen.com/"
        elif "property1.pk" in image_url:
            referer = "https://www.property1.pk/"
        elif "olx.com.pk" in image_url: 
            referer = "https://www.olx.com.pk/"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": referer,
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        r = requests.get(image_url, headers=headers, timeout=15, stream=True)

        if r.status_code == 200:
            return Response(
                r.content,
                content_type=r.headers.get("Content-Type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                    "Access-Control-Allow-Origin": "*"
                }
            )
        else:
            # Return a placeholder image if fetch fails
            return Response(
                status=404,
                response="Image not found"
            )

    except Exception as e:
        return str(e), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')