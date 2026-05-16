{{ config(materialized='table') }}

-- ============================================================================
-- fct_bestsellers_summary
--
-- One model, six rollup grains, per-snapshot history.
--
-- Uses GROUPING SETS to compute concentration (book counts, distinct titles)
-- and longevity (weeks on list, new vs returning entries) metrics at multiple
-- grains, KEEPING every snapshot so dashboards can show period-over-period
-- comparisons. The is_latest_snapshot flag lets consumers default to current
-- without hard-coding a date.
--
-- Grain levels produced (per snapshot, filterable via the grain_level column):
--   1. category_x_publisher  -- e.g. how many Penguin books are in Fiction?
--   2. category_x_author     -- e.g. how many books does Colleen Hoover have in Fiction?
--   3. category_total        -- per-category rollup
--   4. publisher_total       -- per-publisher rollup
--   5. author_total          -- per-author rollup
--   6. grand_total           -- one row per snapshot, everything combined
--
-- Why GROUPING SETS instead of UNION ALL?
--   - One scan of the source instead of six (lower BigQuery slot-time + bytes billed)
--   - Less code to maintain, no risk of metric drift between sub-queries
--   - The optimizer can share aggregation work across grains
--
-- Why keep all snapshots instead of filtering to recency_rank = 1?
--   - Enables week-over-week comparison in Looker Studio scorecards
--   - Enables trend charts (run length over time, share of voice over time)
--   - Dashboard defaults to is_latest_snapshot = true so the "current state"
--     view is unchanged for existing consumers
--
-- Production scaling notes (interview-ready):
--   - Source table `raw_bestsellers` should be PARTITIONED BY DATE(pulled_at)
--     and CLUSTERED BY list_name so date predicates prune partitions.
--   - This mart grows by ~180 rows per weekly snapshot. ~52 weeks/year => ~9K
--     rows/year, still trivial. If it ever got large, switch to incremental
--     with snapshot_date as the watermark.
-- ============================================================================

with snapshot as (

    -- keep every weekly pull, not just the latest
    select *
    from {{ ref('int_bestsellers_by_category') }}

),

aggregated as (

    select
        pulled_date                                           as snapshot_date,
        list_name_clean                                       as category,
        publisher,
        author,

        -- GROUPING() returns 1 when the column is rolled up, 0 when it's a real value.
        -- snapshot_date is in every grouping set, so it's never rolled up.
        grouping(list_name_clean)                             as is_category_rollup,
        grouping(publisher)                                   as is_publisher_rollup,
        grouping(author)                                      as is_author_rollup,

        -- concentration metrics
        count(*)                                              as book_appearances,
        count(distinct title)                                 as distinct_titles,

        -- longevity metrics
        round(avg(weeks_on_list), 1)                          as avg_run_length_weeks,
        -- median is more robust than avg when a single long-running outlier
        -- (e.g. Wonder at 541 weeks) skews a small group's average.
        -- APPROX_QUANTILES(value, 2) returns 3 boundaries [min, median, max];
        -- OFFSET(1) picks the median.
        approx_quantiles(weeks_on_list, 2)[offset(1)]         as median_run_length_weeks,
        max(weeks_on_list)                                    as max_run_length_weeks,
        sum(case when weeks_on_list <= 1 then 1 else 0 end)   as new_entries,
        sum(case when weeks_on_list >  1 then 1 else 0 end)   as returning_entries,

        -- string aggregations: useful for tables that need to show "which
        -- categories/titles does this author or publisher appear in?".
        -- At the author_total grain, categories_list answers "what genres
        -- does this author write in?". At lower grains it's still computed
        -- but rarely displayed.
        string_agg(distinct list_name_clean, ', ' order by list_name_clean) as categories_list,
        string_agg(distinct title,           '; ' order by title)           as titles_list

    from snapshot
    group by grouping sets (
        (pulled_date, list_name_clean, publisher),  -- category_x_publisher per snapshot
        (pulled_date, list_name_clean, author),     -- category_x_author per snapshot
        (pulled_date, list_name_clean),             -- category_total per snapshot
        (pulled_date, publisher),                   -- publisher_total per snapshot
        (pulled_date, author),                      -- author_total per snapshot
        (pulled_date)                               -- grand_total per snapshot
    )

),

labeled as (

    select
        -- derive grain_level from the GROUPING() flags
        case
            when is_category_rollup  = 0
             and is_publisher_rollup = 0
             and is_author_rollup    = 1 then 'category_x_publisher'
            when is_category_rollup  = 0
             and is_publisher_rollup = 1
             and is_author_rollup    = 0 then 'category_x_author'
            when is_category_rollup  = 0
             and is_publisher_rollup = 1
             and is_author_rollup    = 1 then 'category_total'
            when is_category_rollup  = 1
             and is_publisher_rollup = 0
             and is_author_rollup    = 1 then 'publisher_total'
            when is_category_rollup  = 1
             and is_publisher_rollup = 1
             and is_author_rollup    = 0 then 'author_total'
            when is_category_rollup  = 1
             and is_publisher_rollup = 1
             and is_author_rollup    = 1 then 'grand_total'
        end                                                   as grain_level,

        snapshot_date,

        -- flag the most recent snapshot in the dataset so dashboards can
        -- default to "current state" without hard-coding a date
        case
            when snapshot_date = max(snapshot_date) over () then true
            else false
        end                                                   as is_latest_snapshot,

        coalesce(category,  'ALL CATEGORIES')                 as category_label,
        coalesce(publisher, 'ALL PUBLISHERS')                 as publisher_label,
        coalesce(author,    'ALL AUTHORS')                    as author_label,

        book_appearances,
        distinct_titles,
        avg_run_length_weeks,
        median_run_length_weeks,
        max_run_length_weeks,
        new_entries,
        returning_entries,
        categories_list,
        titles_list,

        -- per-snapshot share, expressed in 0-100 scale (NOT 0-1 decimal).
        -- Stored as 8.0 not 0.08 so Looker Studio's Percent type renders
        -- it as "8.0%" without needing a multiplier at the BI layer.
        round(
            safe_divide(
                book_appearances,
                sum(case when is_category_rollup = 1
                          and is_publisher_rollup = 1
                          and is_author_rollup    = 1
                         then book_appearances end) over (partition by snapshot_date)
            ) * 100,
            1
        )                                                     as pct_of_grand_total

    from aggregated

)

select *
from labeled
-- ORDER BY intentionally omitted: Looker Studio sorts client-side, and a
-- trailing ORDER BY adds an unnecessary shuffle step.
