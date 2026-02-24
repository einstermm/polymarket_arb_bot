import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root,123")
    MYSQL_DB = os.getenv("MYSQL_DB", "polymarket_arb")

    API_URL = "https://gamma-api.polymarket.com/markets"
    SCAN_INTERVAL = 60
