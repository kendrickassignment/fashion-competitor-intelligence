"""
config.py
---------
Konfigurasi terpusat untuk seluruh pipeline.

Memisahkan konfigurasi dari logika kode adalah praktik standar agar
pipeline mudah dipindahkan antar environment (local/staging/production)
cukup dengan mengganti nilai di sini atau lewat environment variable,
tanpa menyentuh kode.
"""

import os

# --- Sumber data ---
BASE_URL = "https://fashion-studio.dicoding.dev"
TOTAL_PAGES = 50
REQUEST_DELAY_SECONDS = 0.5

# --- Direktori data per layer ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
BRONZE_DIR = os.path.join(DATA_DIR, "bronze")
SILVER_DIR = os.path.join(DATA_DIR, "silver")
GOLD_DIR = os.path.join(DATA_DIR, "gold")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# --- Convenience export ---
CSV_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "products.csv")

# --- PostgreSQL (processed layer) ---
DB_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.kztiwpjksnicmsvyfglh.supabase.co:5432/postgres"
# Ganti_dengan_password_anda" atau bisa juga diisi lewat environment variable agar kredensial tidak hardcode.


# --- Google Sheets (serving layer) ---
SPREADSHEET_ID = os.environ.get("PEMDA_SPREADSHEET_ID", None)
#Ganti dengan ID spreadsheet Google Sheets Anda, atau bisa juga diisi lewat environment variable agar kredensial tidak hardcode.
GOOGLE_CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "google-sheets-api.json")
