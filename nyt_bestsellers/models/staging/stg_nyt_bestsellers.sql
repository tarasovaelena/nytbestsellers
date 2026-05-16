with source as (

    select * from {{ source('nyt_raw', 'raw_bestsellers') }}

),

renamed as (

    select
        pulled_at,
        list_name,
        rank,

        -- NYT API returns titles in ALL CAPS; convert to Title Case for display.
        -- INITCAP capitalizes the first letter of every word — not perfect English
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

)

select * from renamed