"""
nyt_pipeline_dag.py

Weekly Airflow DAG that runs the NYT Bestsellers data pipeline end to end:
  1. Ingest fresh data from the NYT Books API into BigQuery (raw_bestsellers)
  2. Transform via dbt models (staging -> intermediate -> marts) and run
     all schema.yml tests

Trigger: externally triggered, not on Airflow's own cron. A Windows Task
Scheduler job wakes the laptop ~11:45 PM every Wednesday, starts Docker +
this stack, and explicitly runs `airflow dags trigger` for this DAG (see
scripts/run_weekly_pipeline.py in the project root). `schedule=None` below
is deliberate: this DAG used to run on "0 0 * * 4" (Thursday 00:00 ET),
but with an external trigger also in play, Airflow's own cron would
sometimes fire its own separate run in the same window the external
trigger did — producing two DagRuns and two appends to raw_bestsellers.
Setting schedule=None makes the external trigger the single source of
truth for "when does this run."

CONTAINER LAYOUT (set up via airflow/docker-compose.yaml)
---------------------------------------------------------
The Airflow worker container has the following paths mounted:
  /opt/project                 -> the NYT_Bestsellers/ project root on the host
  /opt/project/nyt_bestsellers -> the dbt project folder
  /opt/gcp                     -> folder holding the GCP service-account key

And the following environment variables are set:
  GOOGLE_APPLICATION_CREDENTIALS -> /opt/gcp/<keyfile>
  DBT_PROFILES_DIR               -> /opt/project/nyt_bestsellers

These let the bash tasks below run ingest_nyt.py and `dbt build` directly,
authenticated against BigQuery via the service account.
"""

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task


# Default settings applied to every task in this DAG.
# Individual tasks can override these if they need to.
default_args = {
    "owner": "elena",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="nyt_bestsellers_pipeline",
    description="Weekly NYT Bestseller ingestion + dbt transformation (externally triggered)",
    # No internal cron — see the module docstring. Triggered only via
    # `airflow dags trigger` (by scripts/run_weekly_pipeline.py, or manually).
    schedule=None,
    start_date=pendulum.datetime(2026, 6, 11, tz="America/New_York"),
    catchup=False,          # don't backfill missed runs from before start_date
    max_active_runs=1,      # never run two instances of this DAG in parallel
    default_args=default_args,
    tags=["nyt", "bestsellers", "portfolio"],
)
def nyt_bestsellers_pipeline():
    """Pipeline definition. The returned DAG is auto-registered by Airflow."""

    @task.bash
    def ingest_from_nyt_api() -> str:
        """
        Fetch the current bestseller lists from the NYT Books API and append
        them to the raw_bestsellers BigQuery table.

        Runs ingest_nyt.py from /opt/project so load_dotenv() picks up the
        project's root .env file (which holds NYT_API_KEY, GCP_PROJECT, etc.).
        BigQuery authentication uses the service-account key referenced by
        GOOGLE_APPLICATION_CREDENTIALS.
        """
        return "cd /opt/project && python ingest_nyt.py"

    @task.bash
    def run_dbt_build() -> str:
        """
        Run the full dbt pipeline: stg_nyt_bestsellers -> int_bestsellers_by_category
        -> fct_bestsellers_summary, plus every not_null / accepted_values test
        defined in the schema.yml files at each layer.

        `dbt build` (vs `dbt run`) executes models AND tests in DAG order, so
        the run fails loudly if upstream data violates an expectation, instead
        of silently producing bad downstream rows.
        """
        return "cd /opt/project/nyt_bestsellers && dbt build"

    # Task dependency: ingest must finish before dbt starts.
    # In Airflow's TaskFlow API, `>>` means "upstream task, then downstream task."
    # If ingest fails, dbt is skipped automatically.
    ingest_from_nyt_api() >> run_dbt_build()


# Instantiate the DAG. Airflow's scheduler scans the dags/ folder and
# registers any DAG returned from a top-level function call like this.
nyt_bestsellers_pipeline()
