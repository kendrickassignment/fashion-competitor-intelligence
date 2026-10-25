"""Consumer-ready CSV marts and conservative observation-to-observation changes."""

import pandas as pd

from src.errors import QualityError
from src.transform import validate_clean_data


def category_metrics(frame):
    try:
        validate_clean_data(frame)
        data = frame.assign(Category=frame["Title"].str.replace(r"\s+\d+$", "", regex=True))
        return data.groupby(["Category", "Gender"], as_index=False).agg(
            products=("Title", "count"), min_price_idr=("Price", "min"),
            median_price_idr=("Price", "median"), mean_price_idr=("Price", "mean"),
            max_price_idr=("Price", "max"), mean_rating=("Rating", "mean"),
        ).round(2)
    except Exception as exc:
        raise QualityError("Cannot generate category metrics") from exc


def detect_changes(previous, current):
    """Missing from a clean snapshot is an observation gap, not proven delisting."""
    try:
        validate_clean_data(current)
        if previous is None:
            return current.assign(change_type="first_observed", previous_price_idr=float("nan"),
                                  price_delta_idr=float("nan"))
        validate_clean_data(previous)
        joined = current.merge(previous[["Title", "Price"]], how="left", on="Title",
                               suffixes=("", "_previous"), validate="one_to_one")
        joined["change_type"] = "unchanged"
        joined.loc[joined["Price_previous"].isna(), "change_type"] = "first_observed"
        moved = joined["Price_previous"].notna() & joined["Price"].ne(joined["Price_previous"])
        joined.loc[moved, "change_type"] = "price_changed"
        joined["price_delta_idr"] = joined["Price"] - joined["Price_previous"]
        observed = joined.loc[joined["change_type"].ne("unchanged")].rename(
            columns={"Price_previous": "previous_price_idr"})
        gaps = previous.loc[~previous["Title"].isin(current["Title"])].assign(
            change_type="not_observed_clean", previous_price_idr=lambda d: d["Price"],
            price_delta_idr=float("nan"))
        return pd.concat([observed, gaps], ignore_index=True)
    except Exception as exc:
        raise QualityError("Cannot compare catalog observations") from exc
