import os
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_ARTICLE_AGE_DAYS = 3
SEND_DAY = "Friday"
SEND_TIME_EAT = "07:00"   # 04:00 UTC
WORKBOOK_PATH = "data/TFN_Export_Intelligence.xlsx"
LOG_DIR = "logs"
CREDENTIALS_PATH = "credentials/gmail_credentials.json"

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

RECIPIENTS = [r for r in [
    os.getenv("RECIPIENT_1"),
    os.getenv("RECIPIENT_2"),
    os.getenv("RECIPIENT_3"),
] if r]

SECTOR_SOURCES = {
    "Tea": {
        "sources": [
            {"name": "Tea Board of Kenya", "url": "https://www.teaboard.or.ke", "type": "html"},
            {"name": "EATTA", "url": "https://www.eatta.com", "type": "html"},
            {"name": "Business Daily Tea", "url": "https://www.businessdailyafrica.com/bd/economy/tea", "type": "html"},
        ],
        "search_terms": ["kenya tea", "mombasa tea", "tea auction", "tea export", "tea prices"],
    },
    "Coffee": {
        "sources": [
            {"name": "Coffee Directorate", "url": "https://www.coffeeboard.co.ke", "type": "html"},
            {"name": "Business Daily Coffee", "url": "https://www.businessdailyafrica.com/bd/economy/coffee", "type": "html"},
        ],
        "search_terms": ["kenya coffee", "eudr coffee", "coffee export", "coffee prices", "nairobi coffee"],
    },
    "Flowers": {
        "sources": [
            {"name": "Kenya Flower Council", "url": "https://kenyaflowercouncil.org", "type": "html"},
            {"name": "Floral Daily", "url": "https://www.floraldaily.com/rss", "type": "rss"},
            {"name": "FreshPlaza", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["kenya flower", "flower export", "flower freight", "cut flower", "naivasha flower"],
    },
    "Avocado": {
        "sources": [
            {"name": "AFA Horticulture", "url": "https://www.horticulture.or.ke", "type": "html"},
            {"name": "FreshPlaza Avocado", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["kenya avocado", "avocado export", "avocado china", "hass avocado kenya"],
    },
    "Apparel & Textiles": {
        "sources": [
            {"name": "EPZA Kenya", "url": "https://www.epzakenya.com", "type": "html"},
            {"name": "Fibre2Fashion", "url": "https://www.fibre2fashion.com/rss-feed.asp", "type": "rss"},
        ],
        "search_terms": ["kenya apparel", "agoa kenya", "kenya textile", "epz kenya", "kenya garment"],
    },
    "Macadamia Nuts": {
        "sources": [
            {"name": "AFA Nuts", "url": "https://www.afa.go.ke", "type": "html"},
            {"name": "Business Daily Agriculture", "url": "https://www.businessdailyafrica.com/bd/economy/agriculture", "type": "html"},
        ],
        "search_terms": ["kenya macadamia", "macadamia export", "macadamia prices", "macadamia nuts kenya"],
    },
    "French Beans & Snow Peas": {
        "sources": [
            {"name": "KEPHIS", "url": "https://www.kephis.org", "type": "html"},
            {"name": "FreshPlaza Veg", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["kenya french beans", "snow peas kenya", "fine beans kenya", "eu pesticide kenya"],
    },
    "Mangoes": {
        "sources": [
            {"name": "KEPHIS Fruit", "url": "https://www.kephis.org", "type": "html"},
            {"name": "AFA Horticulture", "url": "https://www.horticulture.or.ke", "type": "html"},
        ],
        "search_terms": ["kenya mango", "mango export kenya", "mango fruit fly", "kent mango kenya"],
    },
    "Leather & Leather Products": {
        "sources": [
            {"name": "Kenya Leather Development Council", "url": "https://www.kldc.go.ke", "type": "html"},
            {"name": "Business Daily Trade", "url": "https://www.businessdailyafrica.com", "type": "html"},
        ],
        "search_terms": ["kenya leather", "kenya footwear", "leather export kenya", "kldc kenya"],
    },
    "Transport & Logistics": {
        "sources": [
            {"name": "Kenya Ports Authority", "url": "https://www.kpa.co.ke", "type": "html"},
            {"name": "The East African Logistics", "url": "https://www.theeastafrican.co.ke/tea/business/logistics", "type": "html"},
        ],
        "search_terms": ["mombasa port", "kra customs", "kenya freight", "sgr cargo", "kenya logistics", "port congestion"],
    },
}

SECTORS = list(SECTOR_SOURCES.keys())
