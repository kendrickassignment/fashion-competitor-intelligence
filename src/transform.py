"""
transform.py
------------
Tahapan TRANSFORM pada ETL pipeline.

Modul ini bertanggung jawab untuk membersihkan dan menstandardisasi
data mentah hasil scraping agar siap dipakai oleh tim data science:
- Mengonversi kolom Price dari USD ke IDR (kurs Rp16.000).
- Mengonversi Rating menjadi tipe float.
- Mengonversi Colors menjadi tipe int (hanya angka).
- Membersihkan teks "Size: " dan "Gender: " pada kolom Size & Gender.
- Menghapus data invalid, null, dan duplikat.

Setiap fungsi memiliki mekanisme penanganan kesalahan (try/except)
agar kegagalan pada satu kolom tidak menghentikan seluruh pipeline.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

EXCHANGE_RATE_USD_TO_IDR = 16000
INVALID_TITLES = {"Unknown Product"}
INVALID_PRICE_TEXTS = {"Price Unavailable"}
INVALID_RATING_TEXTS = {"Invalid Rating", "Not Rated"}

REQUIRED_COLUMNS = ["Title", "Price", "Rating", "Colors", "Size", "Gender", "timestamp"]


def clean_title(df):
    """Menghapus baris dengan judul produk yang tidak valid (misal: 'Unknown Product')."""
    try:
        df = df.copy()
        df = df[df["Title"].notna()]
        df = df[~df["Title"].isin(INVALID_TITLES)]
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Title: {e}")
        return df


def clean_price(df):
    """
    Membersihkan kolom Price:
    - Menghapus baris dengan teks 'Price Unavailable'.
    - Menghapus simbol '$' dan mengonversi ke tipe numerik.
    - Mengonversi nilai dari USD ke IDR dengan kurs Rp16.000.
    """
    try:
        df = df.copy()
        df = df[df["Price"].notna()]
        df = df[~df["Price"].isin(INVALID_PRICE_TEXTS)]

        df["Price"] = (
            df["Price"].astype(str).str.replace(r"[^0-9.]", "", regex=True).str.strip()
        )
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df = df.dropna(subset=["Price"])
        df["Price"] = df["Price"] * EXCHANGE_RATE_USD_TO_IDR
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Price: {e}")
        return df


def clean_rating(df):
    """
    Membersihkan kolom Rating:
    - Menghapus baris yang mengandung teks 'Invalid Rating' atau 'Not Rated'
      (dicocokkan dengan substring agar tetap terdeteksi meskipun masih
      mengandung label/prefix seperti "Rating: ⭐ Invalid Rating / 5").
    - Mengambil nilai numerik dari pola seperti '⭐ 4.8 / 5' menjadi 4.8 (float).
    """
    try:
        df = df.copy()
        df = df[df["Rating"].notna()]

        rating_text = df["Rating"].astype(str)
        invalid_pattern = "|".join(INVALID_RATING_TEXTS)
        is_invalid = rating_text.str.contains(invalid_pattern, case=False, na=False, regex=True)
        df = df[~is_invalid]

        extracted = df["Rating"].astype(str).str.extract(r"(\d+\.?\d*)")[0]
        df["Rating"] = pd.to_numeric(extracted, errors="coerce")
        df = df.dropna(subset=["Rating"])
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Rating: {e}")
        return df


def clean_colors(df):
    """Mengambil nilai numerik dari pola seperti '3 Colors' menjadi 3 (int)."""
    try:
        df = df.copy()
        df = df[df["Colors"].notna()]
        extracted = df["Colors"].astype(str).str.extract(r"(\d+)")[0]
        df["Colors"] = pd.to_numeric(extracted, errors="coerce")
        df = df.dropna(subset=["Colors"])
        df["Colors"] = df["Colors"].astype(int)
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Colors: {e}")
        return df


def clean_size(df):
    """Menghapus prefix teks 'Size: ' sehingga kolom Size hanya berisi ukuran saja."""
    try:
        df = df.copy()
        df = df[df["Size"].notna()]
        df["Size"] = (
            df["Size"].astype(str).str.replace("Size:", "", regex=False).str.strip()
        )
        df = df[df["Size"] != ""]
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Size: {e}")
        return df


def clean_gender(df):
    """Menghapus prefix teks 'Gender: ' sehingga kolom Gender hanya berisi jenis kelamin saja."""
    try:
        df = df.copy()
        df = df[df["Gender"].notna()]
        df["Gender"] = (
            df["Gender"].astype(str).str.replace("Gender:", "", regex=False).str.strip()
        )
        df = df[df["Gender"] != ""]
        return df
    except Exception as e:
        logger.error(f"Gagal membersihkan kolom Gender: {e}")
        return df


def remove_duplicates_and_na(df):
    """Menghapus seluruh baris dengan nilai null dan baris yang duplikat."""
    try:
        df = df.copy()
        df = df.dropna()
        df = df.drop_duplicates()
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"Gagal menghapus nilai null/duplikat: {e}")
        return df


def enforce_data_types(df):
    """Memastikan setiap kolom memiliki tipe data akhir yang sesuai dengan rubrik penilaian."""
    try:
        df = df.copy()
        df["Title"] = df["Title"].astype(str)
        df["Price"] = df["Price"].astype(float)
        df["Rating"] = df["Rating"].astype(float)
        df["Colors"] = df["Colors"].astype(int)
        df["Size"] = df["Size"].astype(str)
        df["Gender"] = df["Gender"].astype(str)
        df["timestamp"] = df["timestamp"].astype(str)
        return df
    except Exception as e:
        logger.error(f"Gagal mengonversi tipe data akhir: {e}")
        return df


def transform_main(raw_data):
    """
    Fungsi utama tahapan transform.

    Menerima data mentah (list of dict ataupun pandas DataFrame) hasil
    tahapan extract, lalu mengembalikan DataFrame yang sudah bersih,
    bertipe data sesuai rubrik, bebas null, invalid, dan duplikat.
    """
    try:
        if raw_data is None:
            raise ValueError("Data mentah bernilai None.")

        df = raw_data.copy() if isinstance(raw_data, pd.DataFrame) else pd.DataFrame(raw_data)

        if df.empty:
            logger.warning("Data mentah kosong, tidak ada yang dapat ditransformasi.")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise KeyError(f"Kolom wajib berikut tidak ditemukan: {missing_cols}")

        df = clean_title(df)
        df = clean_price(df)
        df = clean_rating(df)
        df = clean_colors(df)
        df = clean_size(df)
        df = clean_gender(df)
        df = remove_duplicates_and_na(df)
        df = enforce_data_types(df)

        logger.info(f"Transformasi selesai: {len(df)} baris data bersih dihasilkan.")
        return df
    except Exception as e:
        logger.error(f"Terjadi kesalahan pada proses transformasi utama: {e}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)


if __name__ == "__main__":
    sample = [
        {
            "Title": "T-shirt 2",
            "Price": "$102.15",
            "Rating": "⭐ 3.9 / 5",
            "Colors": "3 Colors",
            "Size": "Size: M",
            "Gender": "Gender: Women",
            "timestamp": "2026-06-17T00:00:00",
        }
    ]
    print(transform_main(sample))
