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
    """
    Pull the current top 10 for every category.

    Fails the whole run if ANY category could not be fetched. That is
    deliberate: a partial week is worse than no week. If only 4 of 5
    categories land, the mart still computes grand totals and share-of-voice
    percentages, but over incomplete data, which means silently wrong numbers
    in the dashboard. A failed task is visible and Airflow retries it; bad
    data is neither.
    """
    nyt = NYTAPI(NYT_API_KEY, parse_dates=True)
    pulled_at = datetime.now(timezone.utc).isoformat()
    rows = []
    failed = []

    for category in CATEGORIES:
        try:
            books = nyt.best_sellers_list(name=category)[:10]
            if not books:
                raise ValueError("API returned no books for this category")
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
            failed.append(f"{category} ({e})")

    if failed:
        raise RuntimeError(
            f"{len(failed)} of {len(CATEGORIES)} categories failed to fetch: "
            + "; ".join(failed)
        )

    if not rows:
        raise RuntimeError("No rows fetched from the NYT API, nothing to load.")

    return rows

# --- Load to BigQuery ---
def load_to_bigquery(rows):
    """
    Append rows to raw_bestsellers using a LOAD JOB rather than a streaming
    insert.

    Why not insert_rows_json (streaming)?
      1. Streamed rows sit in a write-optimized streaming buffer where
         UPDATE/DELETE/MERGE are blocked for up to ~90 minutes. That is why
         cleaning up the duplicate-ingestion incident meant waiting ~2 hours
         before the DELETE would even run.
      2. Load jobs are atomic. The batch either lands completely or not at
         all, and rows are immediately available to DML, so a bad run can be
         corrected right away.
      3. job.result() raises on failure, so a failed load fails the Airflow
         task instead of printing an error and exiting 0.

    No schema is passed: the destination table already exists, so BigQuery
    applies its schema. That is intentional, because autodetect on a live table
    risks silently inferring different types if the API payload shifts.
    """
    client = bigquery.Client(project=GCP_PROJECT)
    table_ref = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )

    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()  # blocks until done; raises GoogleAPICallError on failure

    print(f"Loaded {len(rows)} rows into {table_ref} (load job {job.job_id})")

# --- Main ---
if __name__ == "__main__":
    print(f"Starting NYT ingestion at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    rows = fetch_bestsellers()
    print(f"Total rows fetched: {len(rows)}")
    load_to_bigquery(rows)
    print("Done.")