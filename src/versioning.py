"""
versioning.py
-------------
Simulasi Incremental Load & Data Versioning.

Karena sumber data berupa situs statis tanpa API perubahan
(change-data-capture), modul ini mensimulasikan praktik incremental
load dengan cara:

1. Menyimpan setiap hasil transform sebagai snapshot berhistori di
   silver/history/ (data versioning -- tidak pernah ditimpa).
2. Membandingkan snapshot SILVER hari ini dengan snapshot SILVER
   sebelumnya (latest.csv sebelum ditimpa) untuk mendeteksi:
   - produk baru (Title muncul di snapshot sekarang, tidak ada di
     snapshot sebelumnya)
   - perubahan harga (Title sama, nilai Price berbeda)

CATATAN DESAIN (penting, untuk transparansi):
Title pada situs ini berformat "{Kategori} {nomor_urut}" yang konsisten
per posisi produk (mis. "T-shirt 2", "Hoodie 3", ...), sehingga dipakai
sebagai natural key untuk pencocokan antar snapshot. Karena situs
sumber men-generate sebagian nilai (rating/availability) secara acak
pada tiap load, sebuah Title yang baris-nya invalid pada satu run bisa
saja valid pada run berikutnya -- pada kasus ini modul akan
menganggapnya sebagai "produk baru" relatif terhadap snapshot
sebelumnya. Ini adalah trade-off yang wajar untuk sumber data statis
tanpa primary key/ID asli.
"""

import logging
import os
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

KEY_COLUMN = "Title"


def save_silver_snapshot(df, silver_dir, run_date=None):
    """
    Menyimpan DataFrame bersih ke layer SILVER:
    - sebagai file berhistori (silver/history/products_{tanggal}.csv),
      tidak pernah ditimpa (data versioning).
    - sekaligus memperbarui silver/latest.csv sebagai pointer ke versi
      paling baru, dipakai sebagai input untuk tahap load/analytics.

    Mengembalikan tuple (history_path, latest_path), atau (None, None)
    jika gagal.
    """
    try:
        date_str = run_date or datetime.now().strftime("%Y-%m-%d")
        history_dir = os.path.join(silver_dir, "history")
        os.makedirs(history_dir, exist_ok=True)

        history_path = os.path.join(history_dir, f"products_{date_str}.csv")
        latest_path = os.path.join(silver_dir, "latest.csv")

        df.to_csv(history_path, index=False)
        df.to_csv(latest_path, index=False)

        logger.info(f"Snapshot silver disimpan: {history_path} ({len(df)} baris).")
        return history_path, latest_path
    except Exception as e:
        logger.error(f"Gagal menyimpan snapshot silver: {e}")
        return None, None


def load_previous_snapshot(latest_path):
    """
    Memuat snapshot SILVER sebelumnya (latest.csv versi lama) SEBELUM
    file tersebut ditimpa oleh snapshot baru.

    Mengembalikan None apabila belum ada snapshot sebelumnya (mis. ini
    adalah run pertama kali pipeline dijalankan).
    """
    try:
        if not os.path.exists(latest_path):
            logger.info("Belum ada snapshot silver sebelumnya (kemungkinan run pertama).")
            return None
        return pd.read_csv(latest_path)
    except Exception as e:
        logger.error(f"Gagal memuat snapshot silver sebelumnya: {e}")
        return None


def detect_changes(previous_df, current_df, key_column=KEY_COLUMN):
    """
    Membandingkan snapshot sebelumnya dengan snapshot saat ini untuk
    mendeteksi produk baru dan perubahan harga.

    Mengembalikan dict:
    {
        "new_products": DataFrame produk yang baru muncul,
        "price_changes": DataFrame dengan kolom Title, old_price, new_price, delta_price,
    }
    """
    empty_changes = pd.DataFrame(columns=[key_column, "old_price", "new_price", "delta_price"])
    try:
        if previous_df is None or previous_df.empty:
            return {
                "new_products": current_df.copy() if current_df is not None else pd.DataFrame(),
                "price_changes": empty_changes,
            }

        if current_df is None or current_df.empty:
            return {"new_products": pd.DataFrame(), "price_changes": empty_changes}

        prev_keys = set(previous_df[key_column])
        curr_keys = set(current_df[key_column])

        new_keys = curr_keys - prev_keys
        new_products = current_df[current_df[key_column].isin(new_keys)].copy()

        common_keys = curr_keys & prev_keys
        prev_indexed = previous_df.set_index(key_column)["Price"]
        curr_indexed = current_df.set_index(key_column)["Price"]

        changes = []
        for key in common_keys:
            old_price = prev_indexed.get(key)
            new_price = curr_indexed.get(key)
            if pd.notna(old_price) and pd.notna(new_price) and old_price != new_price:
                changes.append(
                    {
                        key_column: key,
                        "old_price": old_price,
                        "new_price": new_price,
                        "delta_price": new_price - old_price,
                    }
                )

        price_changes = pd.DataFrame(changes) if changes else empty_changes
        logger.info(
            f"Deteksi perubahan: {len(new_products)} produk baru, "
            f"{len(price_changes)} perubahan harga."
        )
        return {"new_products": new_products, "price_changes": price_changes}
    except Exception as e:
        logger.error(f"Gagal mendeteksi perubahan data: {e}")
        return {"new_products": pd.DataFrame(), "price_changes": empty_changes}


def save_change_log(changes, gold_dir, run_date=None):
    """Menyimpan hasil deteksi perubahan (new_products & price_changes) ke layer GOLD."""
    try:
        date_str = run_date or datetime.now().strftime("%Y-%m-%d")
        os.makedirs(gold_dir, exist_ok=True)

        new_products_path = os.path.join(gold_dir, f"new_products_{date_str}.csv")
        price_changes_path = os.path.join(gold_dir, f"price_changes_{date_str}.csv")

        changes.get("new_products", pd.DataFrame()).to_csv(new_products_path, index=False)
        changes.get("price_changes", pd.DataFrame()).to_csv(price_changes_path, index=False)

        logger.info(f"Change log (gold) disimpan: {new_products_path}, {price_changes_path}")
        return new_products_path, price_changes_path
    except Exception as e:
        logger.error(f"Gagal menyimpan change log: {e}")
        return None, None
