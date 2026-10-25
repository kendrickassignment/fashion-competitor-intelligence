-- All prices are IDR at the fixed educational rate of USD 1 = IDR 16,000.
SELECT regexp_replace("Title", '\s+\d+$', '') AS category,
       "Gender", count(*) AS products,
       round(avg("Price")::numeric, 2) AS average_price_idr,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY "Price") AS median_price_idr,
       round(avg("Rating")::numeric, 2) AS average_rating
FROM fashion_products
GROUP BY 1, 2
ORDER BY 1, 2;

-- Observation history supports price trends without duplicating a replayed observation.
WITH observations AS (
  SELECT "Title", "timestamp", "Price",
         lag("Price") OVER (PARTITION BY "Title" ORDER BY "timestamp") AS previous_price
  FROM fashion_observations
)
SELECT *, "Price" - previous_price AS price_delta_idr
FROM observations
WHERE previous_price IS NOT NULL AND "Price" <> previous_price
ORDER BY "timestamp" DESC;
