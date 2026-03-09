import logging
import os
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()

LIGHTSPEED_BASE_URL = os.getenv("LIGHTSPEED_BASE_URL", "https://api.webshopapp.com")
LIGHTSPEED_API_KEY = os.getenv("LIGHTSPEED_API_KEY")
LIGHTSPEED_API_SECRET = os.getenv("LIGHTSPEED_API_SECRET")

PICQER_BASE_URL = os.getenv("PICQER_BASE_URL")
PICQER_API_KEY = os.getenv("PICQER_API_KEY")

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
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sync")
