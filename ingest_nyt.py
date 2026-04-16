# ingest_nyt.py
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pynytimes import NYTAPI
from google.cloud import bigquery

load_dotenv()

# --- Config ---
NYT_API_KEY = os.getenv("NYT_API_KEY")
GCP_PROJECT  = os.getenv("GCP_PROJECT")
BQ_DATASET   = os.getenv("BQ_DATASET")   # e.g. "nyt_raw"
BQ_TABLE     = os.getenv("BQ_TABLE")     # e.g. "raw_bestsellers"

CATEGORIES = [
    "hardcover-fiction",
    "hardcover-nonfiction",
    "trade-fiction-paperback",
    "young-adult-hardcover",
    "childrens-middle-grade-hardcover",
]

# --- Fetch ---
def fetch_bestsellers():
    nyt = NYTAPI(NYT_API_KEY, parse_dates=True)
    pulled_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for category in CATEGORIES:
        try:
            books = nyt.best_sellers_list(name=category)[:10]
            for rank, book in enumerate(books, start=1):
                rows.append({
                    "pulled_at":     pulled_at,
                    "list_name":     category,
                    "rank":          rank,
                    "title":         book.get("title", ""),
                    "author":        book.get("contributor", ""),
                    "publisher":     book.get("publisher", ""),
                    "description":   book.get("description", ""),
                    "amazon_url":    book.get("amazon_product_url", ""),
                    "weeks_on_list": book.get("weeks_on_list", 0),
                    "raw_json":      json.dumps(book),
                })
            print(f"  Fetched {category}: {len(books)} books")
        except Exception as e:
            print(f"  ERROR fetching {category}: {e}")
            continue

    return rows

# --- Load to BigQuery ---
def load_to_bigquery(rows):
    client = bigquery.Client(project=GCP_PROJECT)
    table_ref = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"BigQuery insert errors: {errors}")
    else:
        print(f"Loaded {len(rows)} rows into {table_ref}")

# --- Main ---
if __name__ == "__main__":
    print(f"Starting NYT ingestion at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    rows = fetch_bestsellers()
    print(f"Total rows fetched: {len(rows)}")
    load_to_bigquery(rows)
    print("Done.")