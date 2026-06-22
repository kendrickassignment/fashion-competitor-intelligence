"""
airflow_dag_example.py
-----------------------
CONTOH ILUSTRATIF (bukan untuk dijalankan langsung) yang menunjukkan
bagaimana pipeline ini akan terlihat jika dijadwalkan dengan Apache
Airflow di lingkungan produksi sungguhan, alih-alih cron sederhana.

Airflow dipilih sebagai contoh karena memberi keuntungan dibanding
cron untuk kasus seperti ini:
- Dependency antar-task eksplisit (transform tidak akan jalan kalau
  extract gagal).
- Retry otomatis per task kalau scraping gagal sementara (mis. situs
  down sebentar), tanpa perlu mengulang seluruh pipeline dari awal.
- UI untuk memonitor riwayat run, durasi tiap task, dan log per task.

Untuk menjalankan ini sungguhan, file ini perlu disalin ke folder
`dags/` instalasi Airflow, dan setiap PythonOperator perlu memanggil
fungsi asli dari src/extract.py, src/transform.py, dst (bukan
fungsi placeholder di bawah).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Import fungsi pipeline asli (lihat src/ pada project ini)
# from src.extract import scrape_main, save_raw_snapshot
# from src.transform import transform_main
# from src.quality import generate_quality_report, save_quality_report
# from src.versioning import load_previous_snapshot, save_silver_snapshot, detect_changes, save_change_log
# from src.analytics import generate_summary, save_summary
# from src.load import load_main

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fashion_competitor_intelligence_pipeline",
    description="Daily Bronze -> Silver -> Gold pipeline untuk fashion-studio.dicoding.dev",
    schedule_interval="0 3 * * *",  # setiap hari jam 03:00, sama seperti contoh cron
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["fashion", "competitor-intelligence", "etl"],
) as dag:

    def task_extract(**context):
        """Scraping seluruh halaman -> simpan ke layer bronze."""
        # raw_data = scrape_main()
        # save_raw_snapshot(raw_data, BRONZE_DIR)
        # context["ti"].xcom_push(key="raw_data", value=raw_data)
        ...

    def task_transform_and_quality(**context):
        """Bersihkan data + hasilkan laporan kualitas data."""
        # raw_data = context["ti"].xcom_pull(key="raw_data")
        # clean_df = transform_main(raw_data)
        # report = generate_quality_report(raw_data, clean_df)
        # save_quality_report(report, GOLD_DIR)
        ...

    def task_versioning(**context):
        """Simpan snapshot silver + deteksi produk baru/perubahan harga."""
        ...

    def task_analytics(**context):
        """Hasilkan summary insight untuk layer gold."""
        ...

    def task_load(**context):
        """Simpan ke PostgreSQL (processed) dan Google Sheets (serving)."""
        ...

    extract_task = PythonOperator(task_id="extract_bronze", python_callable=task_extract)
    transform_task = PythonOperator(
        task_id="transform_and_quality_check", python_callable=task_transform_and_quality
    )
    versioning_task = PythonOperator(task_id="versioning_silver", python_callable=task_versioning)
    analytics_task = PythonOperator(task_id="analytics_gold", python_callable=task_analytics)
    load_task = PythonOperator(task_id="load_downstream", python_callable=task_load)

    # Dependency chain: extract harus selesai duluan, baru transform,
    # baru versioning & analytics bisa jalan paralel, baru load di akhir.
    extract_task >> transform_task >> [versioning_task, analytics_task] >> load_task
