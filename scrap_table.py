import os
import csv
import logging
from urllib.parse import urljoin
from typing import List, Dict

from uuid import uuid4

from playwright.sync_api import sync_playwright
import boto3
from botocore.exceptions import ClientError

BASE_URL = "https://ultimosismo.igp.gob.pe"
TARGET_PATH = "/ultimo-sismo/sismos-reportados"
TARGET_URL = urljoin(BASE_URL, TARGET_PATH)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _ensure_envs():
    # Same envs used in containerized Lambda to keep Playwright happy
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/.cache")
    os.environ.setdefault("FONTCONFIG_PATH", "/tmp/.fontconfig")


def fetch_with_playwright(limit: int = 10) -> List[Dict]:
    """Use Playwright sync API to render and extract table rows.

    Returns a list of dicts with keys: referencia, reporte_url, fecha_hora, magnitud
    """
    _ensure_envs()
    results: List[Dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--disable-extensions",
                "--disable-background-networking",
            ],
        )
        context = browser.new_context()
        page = context.new_page()

        logger.info("Navigating to %s", TARGET_URL)
        page.goto(TARGET_URL, wait_until="networkidle")

        # Wait for table rows
        page.wait_for_selector("table.table tbody tr", timeout=10000)

        rows = page.query_selector_all("table.table tbody tr")
        logger.info("Found %d rows", len(rows))

        for row in rows[:limit]:
            try:
                cols = row.query_selector_all("td")
                referencia = cols[0].inner_text().strip() if len(cols) > 0 else ""
                fecha_hora = cols[2].inner_text().strip() if len(cols) > 2 else ""
                magnitud = cols[3].inner_text().strip() if len(cols) > 3 else ""

                a = row.query_selector("a[href]")
                href = a.get_attribute("href") if a else None
                reporte_url = urljoin(BASE_URL, href) if href else None

                referencia = " ".join([s.strip() for s in referencia.splitlines() if s.strip()])

                results.append(
                    {
                        "referencia": referencia,
                        "reporte_url": reporte_url,
                        "fecha_hora": fecha_hora,
                        "magnitud": magnitud,
                    }
                )
            except Exception as e:
                logger.exception("Error parsing row: %s", e)

        context.close()
        browser.close()

    return results


def _save_csv(items: List[Dict], path: str = "sismos_wsaws.csv") -> None:
    if not items:
        logger.info("No items to write to CSV")
        return

    keys = list(items[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for it in items:
            writer.writerow(it)

    logger.info("Wrote %d rows to %s", len(items), path)


def _save_dynamodb(items: List[Dict], table_name: str) -> bool:
    if not items:
        logger.info("No items to save into DynamoDB")
        return True

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    try:
        with table.batch_writer() as batch:
            for it in items:
                if "id" not in it:
                    it["id"] = str(uuid4())
                batch.put_item(Item=it)
        logger.info("Saved %d items to DynamoDB table %s", len(items), table_name)
        return True
    except ClientError as e:
        logger.exception("DynamoDB write error: %s", e)
        return False


def lambda_handler(event, context):
    """AWS Lambda handler compatible with awslambdaric used in the Docker image."""
    limit = int(os.environ.get("LIMIT", "10"))
    items = fetch_with_playwright(limit=limit)

    table_name = os.environ.get("DDB_TABLE")
    saved = False
    if table_name:
        saved = _save_dynamodb(items, table_name)

    if not table_name or not saved:
        csv_path = os.environ.get("CSV_PATH", "sismos_wsaws.csv")
        _save_csv(items, csv_path)

    return {"statusCode": 200, "body": items}
