# Custom Airflow image for the NYT Bestsellers pipeline.
#
# Why this exists
# ---------------
# Apache Airflow's docker-compose.yaml supports two ways to add dependencies:
#
#   1. Set `_PIP_ADDITIONAL_REQUIREMENTS` to install packages at container
#      startup (the "quick" approach used during early development).
#   2. Build a custom image that bakes dependencies in at image-build time
#      (this file, the "production-correct" approach).
#
# Approach #1 has a startup race condition: services come up before pip
# install finishes, so anything that runs in the first ~60 seconds may not
# find packages it needs. Approach #2 eliminates that race entirely because
# the image is fully ready before any container starts.
#
# Reference: https://airflow.apache.org/docs/docker-stack/build.html

FROM apache/airflow:2.10.4

# Switch to root to install system packages.
USER root

# Install git so dbt can run `dbt deps` (clone packages from remote repos).
# Currently this project has no dbt packages, but installing git is cheap
# and future-proofs against adding any.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch back to the airflow user before installing Python packages so they
# land in the right site-packages and have the right ownership.
USER airflow

# Install the Python dependencies the pipeline needs:
#   - pynytimes               -> NYT Books API client for ingest_nyt.py
#   - google-cloud-bigquery   -> BigQuery client used by ingest_nyt.py
#   - dbt-bigquery            -> dbt adapter that lets dbt build against BigQuery
RUN pip install --no-cache-dir \
        pynytimes \
        google-cloud-bigquery \
        dbt-bigquery
