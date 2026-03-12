import logging
import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

LIGHTSPEED_BASE_URL = os.getenv("LIGHTSPEED_BASE_URL", "https://api.webshopapp.com")

PICQER_BASE_URL = os.getenv("PICQER_BASE_URL")
PICQER_API_KEY = os.getenv("PICQER_API_KEY")

LIGHTSPEED_SHOPS: List[Dict[str, str]] = [
    {
        "name": "2Cheap",
        "api_key": os.getenv("2CHEAP_LIGHTSPEED_API_KEY", ""),
        "api_secret": os.getenv("2CHEAP_LIGHTSPEED_API_SECRET", ""),
    },
    {
        "name": "Keukenmesjes",
        "api_key": os.getenv("KEUKENMESJES_LIGHTSPEED_API_KEY", ""),
        "api_secret": os.getenv("KEUKENMESJES_LIGHTSPEED_API_SECRET", ""),
    },
]

WEIGHT_SHIPPING_MAP: Dict[int, str] = {
    2: "Briefpost",
    25: "DHL Small",
    1001: "DPD",
    10000: "DHL XXL",
    50000: "Speciaal Transport",
}

SHIPPING_OPTIONS: List[str] = [
    "Briefpost",
    "DHL Small",
    "DHL XXL",
    "DPD",
    "Speciaal Transport",
    "VERZENDTYPE ONBEKEND",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("sync")
