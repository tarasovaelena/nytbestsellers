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

        -- map raw NYT category slugs to display-ready labels
        case list_name
            when 'hardcover-fiction'                then 'Hardcover Fiction'
            when 'hardcover-nonfiction'             then 'Hardcover Nonfiction'
            when 'trade-fiction-paperback'          then 'Trade Paperback'
            when 'young-adult-hardcover'            then 'Young Adult'
            when 'childrens-middle-grade-hardcover' then "Children's Middle Grade"
        end as list_name_clean,

        -- flag the most recent pull for each category
        rank() over (
            partition by list_name
            order by pulled_date desc
        ) as recency_rank

    from staging

)

select * from ranked