with staging as (

    select * from {{ ref('stg_nyt_bestsellers') }}

),

ranked as (

    select
        pulled_date,
        list_name,
        rank,
        title,
        author,
        publisher,
        description,
        amazon_url,
        weeks_on_list,

        -- clean up the list name for readability
        replace(list_name, '-', ' ') as list_name_clean,

        -- flag the most recent pull for each category
        rank() over (
            partition by list_name
            order by pulled_date desc
        ) as recency_rank

    from staging

)

select * from ranked