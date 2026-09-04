with source as (

    select * from {{ source('nyt_raw', 'raw_bestsellers') }}

),

renamed as (

    select
        pulled_at,
        list_name,
        rank,

        -- NYT API returns titles in ALL CAPS; convert to Title Case for display.
        -- INITCAP capitalizes the first letter of every word, not perfect English
        -- title-casing (it capitalizes "the", "for", etc.) but a major readability win.
        initcap(title) as title,

        -- NYT API returns authors as e.g. "by R.J. Palacio" or "by Aaron Reynolds.
        -- Illustrated by Peter Brown". Strip the leading "by " (case-insensitive) and
        -- the optional ". Illustrated by ..." trailing clause to keep just the
        -- primary author(s). Two REGEXP_REPLACEs: suffix first (so the prefix strip
        -- sees a clean "by Author" string), then prefix.
        trim(
            regexp_replace(
                regexp_replace(author, r'\.\s*[Ii]llustrated [Bb]y.*$', ''),
                r'^[Bb][Yy]\s+',
                ''
            )
        ) as author,

        publisher,
        description,
        amazon_url,
        cast(weeks_on_list as int64) as weeks_on_list,
        raw_json,

        -- derived columns
        date(pulled_at) as pulled_date

    from source

),

deduped as (

    -- Defense in depth against duplicate ingestion.
    --
    -- raw_bestsellers is append-only, so re-running the pipeline on the same
    -- day (a manual retry alongside a scheduled run, say) lands the same
    -- week's list twice under two different pulled_at timestamps. The model's
    -- true grain is one row per (pulled_date, list_name, rank), so keep only
    -- the most recent pull for each.
    --
    -- The ingestion script now uses an atomic load job, which makes this far
    -- less likely, but staging should not trust the source to be clean.

    select *
    from renamed
    qualify row_number() over (
        partition by pulled_date, list_name, rank
        order by pulled_at desc
    ) = 1

)

select
    *,

    -- Surrogate key for this model's grain. Tested `unique` in schema.yml,
    -- which is what turns the dedup above from "we think it works" into
    -- "the build fails if it doesn't."
    to_hex(md5(concat(
        cast(pulled_date as string), '|',
        list_name, '|',
        cast(rank as string)
    ))) as snapshot_row_key

from deduped