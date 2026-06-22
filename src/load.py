"""
load.py
-------
Tahapan LOAD pada pipeline.

Modul ini menyimpan data SILVER (sudah bersih) ke layer-layer hilir:
- PostgreSQL  -> "processed layer", representasi data warehouse/DB
  yang dipakai tim lain (analytics engineer, BI) untuk query.
- Google Sheets -> "serving layer", representasi dashboard ringan yang
  bisa langsung dibuka stakeholder non-teknis tanpa akses database.
- CSV (opsional) -> convenience export di root project untuk
  pengecekan cepat manual.

Setiap fungsi penyimpanan dipisah dan punya error handling sendiri
sehingga kegagalan menyimpan ke satu repositori tidak menggagalkan
repositori lainnya.
"""

import logging

logger = logging.getLogger(__name__)

GOOGLE_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def save_to_csv(df, file_path="products.csv"):
    """Menyimpan DataFrame ke dalam berkas CSV (convenience export)."""
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Data berhasil disimpan ke berkas CSV: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan data ke CSV ({file_path}): {e}")
        return False


def get_postgresql_engine(db_url):
    """Membuat SQLAlchemy engine untuk koneksi ke PostgreSQL."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(db_url)
        return engine
    except Exception as e:
        logger.error(f"Gagal membuat koneksi engine PostgreSQL: {e}")
        return None


def save_to_postgresql(df, db_url, table_name="products", if_exists="replace"):
    """Menyimpan DataFrame ke dalam tabel PostgreSQL (processed layer)."""
    engine = None
    try:
        engine = get_postgresql_engine(db_url)
        if engine is None:
            raise ConnectionError("Engine PostgreSQL tidak berhasil dibuat.")
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        logger.info(f"Data berhasil disimpan ke PostgreSQL pada tabel '{table_name}'.")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan data ke PostgreSQL: {e}")
        return False
    finally:
        try:
            if engine is not None:
                engine.dispose()
        except Exception as e:
            logger.error(f"Gagal menutup koneksi PostgreSQL: {e}")


def get_google_sheets_service(credentials_file="google-sheets-api.json"):
    """Membangun service client Google Sheets API dari berkas service account."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=GOOGLE_SHEETS_SCOPES
        )
        service = build("sheets", "v4", credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Gagal membangun service Google Sheets API: {e}")
        return None


def save_to_google_sheets(
    df,
    spreadsheet_id,
    range_name="Products!A1",
    credentials_file="google-sheets-api.json",
):
    """Menyimpan DataFrame ke dalam tab Google Sheets tertentu (serving layer)."""
    try:
        service = get_google_sheets_service(credentials_file)
        if service is None:
            raise ConnectionError("Service Google Sheets tidak berhasil dibuat.")

        values = [df.columns.tolist()] + df.astype(str).values.tolist()
        body = {"values": values}

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body=body,
        ).execute()

        logger.info(f"Data berhasil disimpan ke Google Sheets (range: {range_name}).")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan data ke Google Sheets: {e}")
        return False


def save_summary_to_google_sheets(
    summary,
    spreadsheet_id,
    range_name="Summary!A1",
    credentials_file="google-sheets-api.json",
):
    """
    Menyimpan analytics summary (dict) ke tab terpisah pada Google
    Sheets yang sama, dalam format dua kolom (metric, value), supaya
    stakeholder bisa lihat insight tanpa scroll ratusan baris data.
    """
    try:
        service = get_google_sheets_service(credentials_file)
        if service is None:
            raise ConnectionError("Service Google Sheets tidak berhasil dibuat.")

        rows = [["metric", "value"]]
        for key, value in summary.items():
            rows.append([str(key), str(value)])

        body = {"values": rows}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body=body,
        ).execute()

        logger.info(f"Analytics summary berhasil disimpan ke Google Sheets (range: {range_name}).")
        return True
    except Exception as e:
        logger.error(f"Gagal menyimpan analytics summary ke Google Sheets: {e}")
        return False


def load_main(
    df,
    csv_path=None,
    db_url=None,
    spreadsheet_id=None,
    credentials_file="google-sheets-api.json",
    summary=None,
):
    """
    Fungsi utama tahapan load.

    - csv_path diisi  -> simpan convenience CSV.
    - db_url diisi     -> simpan ke PostgreSQL (processed layer).
    - spreadsheet_id diisi -> simpan data + summary ke Google Sheets (serving layer).
    """
    results = {"csv": None, "postgresql": None, "google_sheets": None, "google_sheets_summary": None}
    try:
        if csv_path:
            results["csv"] = save_to_csv(df, csv_path)

        if db_url:
            results["postgresql"] = save_to_postgresql(df, db_url)

        if spreadsheet_id:
            results["google_sheets"] = save_to_google_sheets(
                df, spreadsheet_id, credentials_file=credentials_file
            )
            if summary:
                results["google_sheets_summary"] = save_summary_to_google_sheets(
                    summary, spreadsheet_id, credentials_file=credentials_file
                )

        logger.info(f"Proses load selesai dengan hasil: {results}")
        return results
    except Exception as e:
        logger.error(f"Terjadi kesalahan pada proses load utama: {e}")
        return results
