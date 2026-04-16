with source as (

    select * from {{ source('nyt_raw', 'raw_bestsellers') }}

),

renamed as (

    select
        pulled_at,
        list_name,
        rank,
        title,
        author,
        publisher,
        description,
        amazon_url,
        weeks_on_list,
        raw_json,

        -- derived columns
        date(pulled_at) as pulled_date

    from source

)

select * from renamed