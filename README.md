🏡 Real Estate Scraper Flask App

A Flask-based web application that scrapes real estate listings from multiple Pakistani property websites:

Zameen.com

Property1.pk

OLX.com.pk

The app allows users to select a city and source, scrape property listings, and even fetch images using a proxy to bypass hotlinking restrictions.

🚀 Features

✅ Multi-source property scraping (Zameen, Property1, OLX)

✅ Supports multiple pages per city

✅ Returns JSON results via API

✅ Image proxy for displaying property images without cross-origin issues

✅ Simple web interface with city selection

✅ Error handling for 404 and 500

📂 Project Structure
project/
│── app.py
│── zameen_scraper.py
│── property1_scraper.py
│── olx_scraper.py
│── templates/
│   └── index.html
│── static/
│── requirements.txt
│── .gitignore

⚙️ Installation

1️⃣ Clone the repository

git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

2️⃣ Create a virtual environment

python -m venv venv

Activate it:

Windows:

venv\Scripts\activate

Mac/Linux:

source venv/bin/activate

3️⃣ Install dependencies


Make sure you have a requirements.txt file with at least:

Flask
requests

Then install:

pip install -r requirements.txt

4️⃣ Run the app locally

python app.py

Open in your browser:

http://127.0.0.1:5000

⚠️ Disclaimer

This project is for educational purposes only.
Web scraping should comply with each platform's Terms of Service.
