import os
import csv
import logging
from urllib.parse import urljoin
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
import boto3
from botocore.exceptions import ClientError
from uuid import uuid4

# Target page (same site as original project)
BASE_URL = "https://ultimosismo.igp.gob.pe"
TARGET_URL = urljoin(BASE_URL, "/ultimo-sismo/sismos-reportados")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_latest_quakes(limit: int = 10, timeout: int = 10) -> List[Dict]:
    """Fetch the latest quakes by scraping the target page with requests + BeautifulSoup.

    Returns a list of dicts: referencia, reporte_url, fecha_hora, magnitud
    """
    items: List[Dict] = []

    try:
        logger.info("GET %s", TARGET_URL)
        resp = requests.get(TARGET_URL, timeout=timeout, headers={"User-Agent": "wsAWS-scraper/1.0"})
        resp.raise_for_status()
    except Exception as e:
        logger.exception("Error fetching page: %s", e)
        return items

    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="table")
    if not table:
        logger.warning("No table found on page")
        return items

    tbody = table.find("tbody")
    if not tbody:
        logger.warning("No tbody found inside table")
        return items

    rows = tbody.find_all("tr")
    logger.info("Found %d rows in table", len(rows))

    for row in rows[:limit]:
        try:
            tds = row.find_all("td")
            referencia = tds[0].get_text(strip=True) if len(tds) > 0 else ""
            fecha_hora = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            magnitud = tds[3].get_text(strip=True) if len(tds) > 3 else ""

            a = row.find("a", href=True)
            href = a["href"] if a else None
            reporte_url = urljoin(BASE_URL, href) if href else None

            # Normalize referencia
            referencia = " ".join([s.strip() for s in referencia.splitlines() if s.strip()])

            item = {
                "referencia": referencia,
                "reporte_url": reporte_url,
                "fecha_hora": fecha_hora,
                "magnitud": magnitud,
            }
            items.append(item)
        except Exception as e:
            logger.exception("Error parsing row: %s", e)

    return items


def save_to_csv(items: List[Dict], path: str = "quakes.csv") -> None:
    if not items:
        logger.info("No items to save to CSV")
        return

    keys = list(items[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for it in items:
            writer.writerow(it)

    logger.info("Saved %d records to %s", len(items), path)


def save_to_dynamodb(items: List[Dict], table_name: str) -> bool:
    if not items:
        logger.info("No items to save to DynamoDB")
        return True

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    try:
        with table.batch_writer() as batch:
            for it in items:
                if "id" not in it:
                    it["id"] = str(uuid4())
                batch.put_item(Item=it)
        logger.info("Saved %d records to DynamoDB table %s", len(items), table_name)
        return True
    except ClientError as e:
        logger.exception("DynamoDB error: %s", e)
        return False


def handler(limit: Optional[int] = None) -> List[Dict]:
    """Main entrypoint for the wsAWS scraper.

    Reads env vars:
    - LIMIT: max rows to fetch
    - DDB_TABLE: optional DynamoDB table name to save results
    - CSV_PATH: fallback CSV path
    """
    if limit is None:
        try:
            limit = int(os.environ.get("LIMIT", "10"))
        except ValueError:
            limit = 10

    items = fetch_latest_quakes(limit=limit)

    table_name = os.environ.get("DDB_TABLE")
    saved = False

    if table_name:
        saved = save_to_dynamodb(items, table_name)

    if not table_name or not saved:
        csv_path = os.environ.get("CSV_PATH", "quakes.csv")
        save_to_csv(items, csv_path)

    return items


if __name__ == "__main__":
    items = handler()
    print(f"Obtained {len(items)} records")
