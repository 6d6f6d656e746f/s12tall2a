import argparse
import logging
from pprint import pprint
from scraper import handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="wsAWS simple runner for scraping quakes")
    parser.add_argument("--limit", type=int, default=5, help="Number of rows to fetch")
    parser.add_argument("--print", action="store_true", help="Print parsed items to console")
    args = parser.parse_args()

    items = handler(limit=args.limit)
    logger.info("Scraper returned %d items", len(items))

    if args.print:
        pprint(items)


if __name__ == "__main__":
    main()
