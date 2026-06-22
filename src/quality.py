"""
quality.py
----------
Data Quality Check untuk pipeline.

Modul ini membandingkan data SEBELUM transform (bronze/raw) dan
SESUDAH transform (silver/clean) untuk menghasilkan laporan kualitas
data: berapa persen data tidak valid, berapa baris yang di-drop, dan
alasan utama drop-nya (judul invalid, harga invalid, rating invalid,
duplikat, atau null).

Laporan ini disimpan ke layer GOLD sebagai bukti observability
pipeline -- praktik umum di data engineering production untuk
memantau kesehatan data dari waktu ke waktu, bukan cuma "berhasil
jalan atau tidak".
"""

import json
import logging
import os
from datetime import datetime

import pandas as pd

from src.transform import INVALID_PRICE_TEXTS, INVALID_RATING_TEXTS, INVALID_TITLES

logger = logging.getLogger(__name__)


def _count_invalid_title(raw_df):
    try:
        return int(raw_df["Title"].isin(INVALID_TITLES).sum() + raw_df["Title"].isna().sum())
    except Exception as e:
        logger.error(f"Gagal menghitung baris Title invalid: {e}")
        return 0


def _count_invalid_price(raw_df):
    try:
        return int(raw_df["Price"].isin(INVALID_PRICE_TEXTS).sum() + raw_df["Price"].isna().sum())
    except Exception as e:
        logger.error(f"Gagal menghitung baris Price invalid: {e}")
        return 0


def _count_invalid_rating(raw_df):
    try:
        pattern = "|".join(INVALID_RATING_TEXTS)
        text = raw_df["Rating"].astype(str)
        return int(text.str.contains(pattern, case=False, na=False, regex=True).sum())
    except Exception as e:
        logger.error(f"Gagal menghitung baris Rating invalid: {e}")
        return 0


def generate_quality_report(raw_data, clean_df, run_timestamp=None):
    """
    Membuat laporan kualitas data dari hasil extract (raw_data, list of
    dict atau DataFrame) dibandingkan dengan hasil transform (clean_df).

    Mengembalikan dict berisi:
    - total_raw, total_clean, total_dropped
    - pct_dropped (persentase baris yang dibuang)
    - breakdown jumlah baris invalid per kolom (title/price/rating)
    - generated_at (timestamp pembuatan laporan)
    """
    try:
        raw_df = raw_data.copy() if isinstance(raw_data, pd.DataFrame) else pd.DataFrame(raw_data)
        total_raw = len(raw_df)
        total_clean = len(clean_df) if clean_df is not None else 0
        total_dropped = max(total_raw - total_clean, 0)
        pct_dropped = round((total_dropped / total_raw) * 100, 2) if total_raw else 0.0

        report = {
            "generated_at": run_timestamp or datetime.now().isoformat(),
            "total_raw_rows": total_raw,
            "total_clean_rows": total_clean,
            "total_dropped_rows": total_dropped,
            "pct_dropped": pct_dropped,
            "invalid_breakdown": {
                "invalid_title_rows": _count_invalid_title(raw_df) if total_raw else 0,
                "invalid_price_rows": _count_invalid_price(raw_df) if total_raw else 0,
                "invalid_rating_rows": _count_invalid_rating(raw_df) if total_raw else 0,
            },
        }
        logger.info(
            f"Data quality report: {total_dropped}/{total_raw} baris di-drop "
            f"({pct_dropped}%)."
        )
        return report
    except Exception as e:
        logger.error(f"Gagal membuat data quality report: {e}")
        return {
            "generated_at": run_timestamp or datetime.now().isoformat(),
            "error": str(e),
        }


def save_quality_report(report, gold_dir, run_timestamp=None):
    """Menyimpan laporan kualitas data sebagai berkas JSON ke layer GOLD."""
    try:
        os.makedirs(gold_dir, exist_ok=True)
        ts = run_timestamp or datetime.now().strftime("%Y%m%dT%H%M%S")
        file_path = os.path.join(gold_dir, f"quality_report_{ts}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Quality report (gold) disimpan: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Gagal menyimpan quality report: {e}")
        return None
