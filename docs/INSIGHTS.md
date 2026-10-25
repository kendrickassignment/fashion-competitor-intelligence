# Reading the catalog as a pricing analyst

This analysis describes the clean fictional snapshot in `docs/evidence/clean.csv`. Prices use the assignment's fixed 16,000 IDR/USD conversion. They are not current market exchange-rate estimates.

## Price and assortment snapshot

The 867 valid product observations have a median price of **IDR 4,776,800** and a mean price of approximately **IDR 4,804,335**. Prices range from IDR 805,600 to IDR 8,794,880.

| Category | Valid products | Median price, IDR |
|---|---:|---:|
| Crewneck | 133 | 5,321,280 |
| Hoodie | 134 | 4,537,120 |
| Jacket | 166 | 5,030,000 |
| Outerwear | 133 | 4,472,000 |
| Pants | 134 | 4,707,840 |
| T-shirt | 167 | 4,840,480 |

Category labels are derived by removing the numeric suffix from a title. The automatically generated `category_metrics.csv` further separates these aggregates by gender.

An analyst can use these distributions to identify comparison bands for a hypothetical retailer's products. The data does not contain fabric, brand positioning, sales, costs, inventory, or promotion history, so these numbers alone cannot establish profitable prices, consumer demand, or promotion effectiveness.

## Quality affects apparent assortment

13.3% of raw cards are excluded from the clean snapshot. A lower valid count in a category can reflect source quality rather than a smaller assortment. Invalid-title cards cannot be reliably assigned to categories. Interpret the table as the **valid observed assortment**, not the complete commercial assortment.

The pipeline records invalid cards in quarantine rather than imputing prices or ratings. This keeps unsupported assumptions out of downstream modeling. Before a real price-matching exercise, analysts should establish comparable product/variant IDs and investigate missing observations.

## Changes require observations over time

This source is a static educational catalog. The included successive successful observations showed no clean product-price changes. The project therefore supplies a change detector and real persistence tests without fabricating a promotional campaign or a price-movement story.

For a changing source, query `fashion_observations` with the SQL window-function example in `sql/analysis.sql`. Treat `not_observed_clean` events as investigation signals: a missing clean row can mean an invalid source card, not necessarily a delisted product.
