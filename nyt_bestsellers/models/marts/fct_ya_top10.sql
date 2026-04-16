with intermediate as (

    select * from {{ ref('int_bestsellers_by_category') }}

)

select
    pulled_date,
    rank,
    title,
    author,
    publisher,
    description,
    amazon_url,
    weeks_on_list,
    list_name_clean

from intermediate
where list_name = 'young-adult-hardcover'
and recency_rank = 1
order by rank