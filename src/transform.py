"""Typed contract, auditable rejection reasons, timestamp-independent deduplication."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.errors import QualityError
from src.extract import FIELDS

COLUMNS = FIELDS + ["timestamp"]
USD_TO_IDR = 16_000
SIZES = {"XS", "S", "M", "L", "XL", "XXL", "XXXL", "3XL"}
GENDERS = {"Men", "Women", "Unisex"}


@dataclass
class TransformResult:
    clean: pd.DataFrame
    rejected: pd.DataFrame
    metrics: dict


def transform_main(raw):
    """Preserve raw rows; each rejected row receives one primary reason."""
    try:
        if not isinstance(raw, pd.DataFrame) or raw.empty or not set(COLUMNS) <= set(raw.columns):
            raise ValueError("Nonempty raw data with all seven fields is required")
        data = raw.reset_index(drop=True).copy(deep=True)
        clean = data[COLUMNS].copy()
        for column in FIELDS:
            clean[column] = clean[column].astype("string").str.strip()
        clean["Price"] = pd.to_numeric(clean["Price"].str.extract(
            r"^\$(\d+(?:\.\d{1,2})?)$", expand=False), errors="coerce") * USD_TO_IDR
        clean["Rating"] = pd.to_numeric(clean["Rating"].str.extract(
            r"^Rating:\s*(?:⭐\s*)?(\d+(?:\.\d+)?)\s*/\s*5$", expand=False), errors="coerce")
        clean["Colors"] = pd.to_numeric(clean["Colors"].str.extract(
            r"^(\d+)\s+Colors?$", expand=False), errors="coerce")
        clean["Size"] = clean["Size"].str.replace(r"^Size:\s*", "", regex=True)
        clean["Gender"] = clean["Gender"].str.replace(r"^Gender:\s*", "", regex=True)
        parsed_time = pd.to_datetime(clean["timestamp"], utc=True, errors="coerce", format="mixed")
        clean["timestamp"] = parsed_time.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        checks = {
            "invalid_title": clean["Title"].notna() & clean["Title"].ne("")
            & ~clean["Title"].str.casefold().isin(["unknown product", "nan", "none", "null"]),
            "invalid_price": clean["Price"].gt(0) & np.isfinite(clean["Price"].astype(float)),
            "invalid_rating": clean["Rating"].between(0, 5),
            "invalid_colors": clean["Colors"].between(1, 100),
            "invalid_size": clean["Size"].isin(SIZES),
            "invalid_gender": clean["Gender"].isin(GENDERS),
            "invalid_timestamp": parsed_time.notna(),
        }
        reasons = pd.Series("", index=clean.index, dtype=object)
        for reason, valid in checks.items():
            reasons.loc[reasons.eq("") & ~valid.fillna(False)] = reason
        duplicate = clean.loc[reasons.eq(""), "Title"].duplicated(keep="first")
        reasons.loc[duplicate.index[duplicate]] = "duplicate_product"
        rejected = data.loc[reasons.ne("")].assign(rejection_reason=reasons[reasons.ne("")])
        clean = clean.loc[reasons.eq("")].reset_index(drop=True)
        clean = clean.astype({"Title": object, "Price": "float64", "Rating": "float64",
                              "Colors": "int64", "Size": object, "Gender": object, "timestamp": object})
        clean["Price"] = clean["Price"].round(2)
        validate_clean_data(clean)
        metrics = {"raw_rows": len(data), "clean_rows": len(clean), "rejected_rows": len(rejected),
                   "yield_ratio": round(len(clean) / len(data), 6), "usd_to_idr": USD_TO_IDR,
                   "rejection_reasons": reasons[reasons.ne("")].value_counts().to_dict(),
                   "reason_policy": "first failing rule; duplicate check after validation"}
        return TransformResult(clean, rejected.reset_index(drop=True), metrics)
    except Exception as exc:
        raise QualityError("Transformation failed; source data violates the transform contract") from exc


def validate_clean_data(frame):
    """Recheck every load boundary so untransformed input cannot be published."""
    try:
        if not isinstance(frame, pd.DataFrame) or frame.empty or list(frame.columns) != COLUMNS:
            raise ValueError("Wrong columns or empty dataset")
        expected = {"Title": "object", "Price": "float64", "Rating": "float64", "Colors": "int64",
                    "Size": "object", "Gender": "object", "timestamp": "object"}
        if any(str(frame[c].dtype) != dtype for c, dtype in expected.items()):
            raise ValueError("Wrong dtypes")
        if frame.isna().any().any() or frame["Title"].duplicated().any():
            raise ValueError("Nulls or duplicate identities")
        if not frame["Title"].map(lambda x: isinstance(x, str) and bool(x.strip())
                                  and x.strip().casefold() not in {"unknown product", "nan", "none", "null"}).all():
            raise ValueError("Invalid title")
        if not (np.isfinite(frame[["Price", "Rating"]]).all().all()
                and frame["Price"].gt(0).all() and frame["Rating"].between(0, 5).all()
                and frame["Colors"].between(1, 100).all()
                and frame["Size"].isin(SIZES).all() and frame["Gender"].isin(GENDERS).all()):
            raise ValueError("Invalid product attributes")
        timestamps = frame["timestamp"].astype("string")
        if not (timestamps.str.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z").all()
                and pd.to_datetime(timestamps, utc=True, errors="coerce").notna().all()):
            raise ValueError("Invalid UTC timestamp")
    except Exception as exc:
        raise QualityError("Clean dataset contract violation") from exc
