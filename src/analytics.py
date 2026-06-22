"""
analytics.py
------------
Analytics output (layer GOLD - serving).

Modul ini mengubah data SILVER yang sudah bersih menjadi insight
ringkas yang langsung bisa dikonsumsi stakeholder bisnis, tanpa
mereka perlu membaca 800+ baris data mentah.
"""

import json
import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def generate_summary(df):
    """
    Menghasilkan ringkasan insight dari data produk yang sudah bersih:
    - jumlah produk, rata-rata & median harga, rentang harga
    - rata-rata harga per Gender dan per Size
    - distribusi rating (rata-rata + jumlah produk rating >= 4.5)
    - 5 produk dengan rating tertinggi
    - distribusi jumlah produk per kategori (kata pertama pada Title,
      mis. "T-shirt", "Hoodie", "Pants")
    """
    try:
        if df is None or df.empty:
            logger.warning("Data kosong, tidak ada insight yang dapat dihasilkan.")
            return {"generated_at": datetime.now().isoformat(), "total_products": 0}

        df = df.copy()
        df["category"] = df["Title"].astype(str).str.split().str[0]

        top_rated = (
            df.sort_values("Rating", ascending=False)
            .head(5)[["Title", "Rating", "Price"]]
            .to_dict(orient="records")
        )

        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_products": int(len(df)),
            "price_idr": {
                "average": round(float(df["Price"].mean()), 2),
                "median": round(float(df["Price"].median()), 2),
                "min": round(float(df["Price"].min()), 2),
                "max": round(float(df["Price"].max()), 2),
            },
            "average_price_by_gender": {
                k: round(float(v), 2) for k, v in df.groupby("Gender")["Price"].mean().items()
            },
            "average_price_by_size": {
                k: round(float(v), 2) for k, v in df.groupby("Size")["Price"].mean().items()
            },
            "rating": {
                "average": round(float(df["Rating"].mean()), 2),
                "products_rating_4_5_or_above": int((df["Rating"] >= 4.5).sum()),
            },
            "product_count_by_category": df["category"].value_counts().to_dict(),
            "top_5_rated_products": top_rated,
        }
        logger.info(f"Analytics summary dihasilkan untuk {len(df)} produk.")
        return summary
    except Exception as e:
        logger.error(f"Gagal menghasilkan analytics summary: {e}")
        return {"generated_at": datetime.now().isoformat(), "error": str(e)}


def save_summary(summary, gold_dir, run_date=None):
    """Menyimpan analytics summary sebagai berkas JSON ke layer GOLD."""
    try:
        date_str = run_date or datetime.now().strftime("%Y-%m-%d")
        os.makedirs(gold_dir, exist_ok=True)
        file_path = os.path.join(gold_dir, f"analytics_summary_{date_str}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"Analytics summary (gold) disimpan: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Gagal menyimpan analytics summary: {e}")
        return None
