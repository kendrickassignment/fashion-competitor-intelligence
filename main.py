"""
main.py
-------
Entry point pipeline "Fashion Competitor Intelligence".

Mengorkestrasi seluruh tahapan secara berurutan:

    EXTRACT --> BRONZE
             --> TRANSFORM --> QUALITY CHECK
                             --> SILVER (versioned)
                                       --> VERSIONING (deteksi perubahan) --> GOLD
                                       --> ANALYTICS (summary insight)    --> GOLD
                                       --> LOAD (PostgreSQL / Google Sheets / CSV)

Setiap tahap dicatat lewat logging (ke console DAN ke berkas log per
run di folder logs/), dan di akhir pipeline dicetak ringkasan
sukses/gagal per komponen -- ini mensimulasikan monitoring sederhana
seperti yang biasa dilihat di Airflow UI atau dashboard observability.
"""

import logging
import os
import sys
from datetime import datetime

import config
from src import analytics, extract, load, quality, transform, versioning


def setup_logging():
    """Konfigurasi logging terpusat: tulis ke console dan ke berkas log per run."""
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_file = os.path.join(config.LOGS_DIR, f"pipeline_{run_id}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
        force=True,
    )
    return run_id, log_file


def run_pipeline():
    run_id, log_file = setup_logging()
    logger = logging.getLogger("pipeline")
    status = {
        "extract": False,
        "bronze_save": False,
        "transform": False,
        "quality_check": False,
        "silver_save": False,
        "versioning": False,
        "analytics": False,
        "load_csv": None,
        "load_postgresql": None,
        "load_google_sheets": None,
    }

    logger.info("=" * 70)
    logger.info(f"=== Memulai Fashion Competitor Intelligence Pipeline (run_id={run_id}) ===")
    logger.info("=" * 70)

    # --- 1. EXTRACT -> BRONZE ---
    logger.info("Tahap 1/5: EXTRACT - scraping fashion-studio.dicoding.dev")
    raw_data = extract.scrape_main(
        total_pages=config.TOTAL_PAGES,
        delay=config.REQUEST_DELAY_SECONDS,
        base_url=config.BASE_URL,
    )
    status["extract"] = len(raw_data) > 0

    bronze_path = extract.save_raw_snapshot(raw_data, config.BRONZE_DIR, run_timestamp=run_id)
    status["bronze_save"] = bronze_path is not None

    # --- 2. TRANSFORM + DATA QUALITY ---
    logger.info("Tahap 2/5: TRANSFORM - membersihkan dan menstandardisasi data")
    clean_df = transform.transform_main(raw_data)
    status["transform"] = not clean_df.empty

    quality_report = quality.generate_quality_report(raw_data, clean_df, run_timestamp=run_id)
    quality.save_quality_report(quality_report, config.GOLD_DIR, run_timestamp=run_id)
    status["quality_check"] = "error" not in quality_report

    # --- 3. VERSIONING (ambil snapshot lama SEBELUM ditimpa) ---
    logger.info("Tahap 3/5: VERSIONING - incremental load & deteksi perubahan")
    latest_path = os.path.join(config.SILVER_DIR, "latest.csv")
    previous_df = versioning.load_previous_snapshot(latest_path)

    history_path, new_latest_path = versioning.save_silver_snapshot(clean_df, config.SILVER_DIR)
    status["silver_save"] = history_path is not None

    changes = versioning.detect_changes(previous_df, clean_df)
    versioning.save_change_log(changes, config.GOLD_DIR)
    status["versioning"] = True
    logger.info(
        f"Produk baru terdeteksi: {len(changes['new_products'])} | "
        f"Perubahan harga terdeteksi: {len(changes['price_changes'])}"
    )

    # --- 4. ANALYTICS -> GOLD ---
    logger.info("Tahap 4/5: ANALYTICS - menghasilkan summary insight")
    summary = analytics.generate_summary(clean_df)
    analytics.save_summary(summary, config.GOLD_DIR)
    status["analytics"] = "error" not in summary

    # --- 5. LOAD ---
    logger.info("Tahap 5/5: LOAD - menyimpan ke repositori data hilir")
    load_results = load.load_main(
        clean_df,
        csv_path=config.CSV_OUTPUT_PATH,
        db_url=config.DB_URL,
        spreadsheet_id=config.SPREADSHEET_ID,
        credentials_file=config.GOOGLE_CREDENTIALS_FILE,
        summary=summary,
    )
    status["load_csv"] = load_results.get("csv")
    status["load_postgresql"] = load_results.get("postgresql")
    status["load_google_sheets"] = load_results.get("google_sheets")

    # --- Ringkasan akhir (mensimulasikan monitoring dashboard) ---
    logger.info("=" * 70)
    logger.info("=== RINGKASAN RUN PIPELINE ===")
    for step, result in status.items():
        symbol = "OK" if result else ("SKIPPED" if result is None else "FAILED")
        logger.info(f"  [{symbol:7}] {step}")
    logger.info(f"Total data mentah   : {len(raw_data)}")
    logger.info(f"Total data bersih   : {len(clean_df)}")
    logger.info(f"Persentase di-drop  : {quality_report.get('pct_dropped', 'N/A')}%")
    logger.info(f"Log lengkap run ini : {log_file}")
    logger.info("=" * 70)

    return status


if __name__ == "__main__":
    run_pipeline()
