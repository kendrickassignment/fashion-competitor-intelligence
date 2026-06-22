"""
extract.py
----------
Tahapan EXTRACT pada ETL pipeline.

Modul ini bertanggung jawab untuk mengambil (scraping) seluruh data produk
dari website https://fashion-studio.dicoding.dev/ (halaman 1 sampai 50).

Setiap fungsi pada modul ini memiliki mekanisme penanganan kesalahan
(error handling) berupa blok try/except agar proses ekstraksi tidak
berhenti total ketika menemui satu kondisi yang tidak diharapkan
(misalnya koneksi gagal, halaman tidak ditemukan, atau struktur HTML
yang tidak terduga pada salah satu kartu produk).
"""

import logging
import os
import time
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://fashion-studio.dicoding.dev"
TOTAL_PAGES = 50


def build_page_url(page_number, base_url=BASE_URL):
    """
    Membangun URL untuk halaman tertentu.

    Halaman 1 berada pada root URL, sedangkan halaman berikutnya
    mengikuti pola "/page{nomor_halaman}".
    """
    try:
        if page_number is None or page_number < 1:
            raise ValueError(f"Nomor halaman tidak valid: {page_number}")
        if page_number == 1:
            return f"{base_url}/"
        return f"{base_url}/page{page_number}"
    except Exception as e:
        logger.error(f"Gagal membangun URL untuk halaman {page_number}: {e}")
        return None


def fetch_page(url, session=None, timeout=10):
    """
    Mengambil konten HTML mentah dari sebuah URL.

    Mengembalikan None apabila request gagal (misalnya koneksi
    bermasalah, timeout, atau status HTTP error) sehingga proses
    scraping pada halaman lain tetap dapat dilanjutkan.
    """
    try:
        http_client = session if session is not None else requests
        response = http_client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Gagal mengambil data dari {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Terjadi kesalahan tak terduga saat mengambil {url}: {e}")
        return None


def parse_product_card(card, timestamp):
    """
    Mengekstrak field mentah (Title, Price, Rating, Colors, Size, Gender)
    dari satu elemen kartu produk (div.collection-card).

    Nilai dikembalikan dalam bentuk teks mentah apa adanya (belum
    dibersihkan/ditransformasi) sesuai tugas tahapan extract.
    """
    try:
        title_tag = card.find("h3", class_="product-title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Price bisa muncul dalam dua bentuk tag HTML berbeda:
        # <div class="price-container"><span class="price">$xx.xx</span></div>
        # atau <p class="price">Price Unavailable</p>
        price = None
        price_container = card.find("div", class_="price-container")
        if price_container is not None:
            price_span = price_container.find("span", class_="price")
            if price_span is not None:
                price = price_span.get_text(strip=True)
        if price is None:
            price_tag = card.find("p", class_="price")
            if price_tag is not None:
                price = price_tag.get_text(strip=True)

        details = card.find("div", class_="product-details")
        info_paragraphs = details.find_all("p", style=True) if details is not None else []

        rating = info_paragraphs[0].get_text(strip=True) if len(info_paragraphs) > 0 else None
        colors = info_paragraphs[1].get_text(strip=True) if len(info_paragraphs) > 1 else None
        size = info_paragraphs[2].get_text(strip=True) if len(info_paragraphs) > 2 else None
        gender = info_paragraphs[3].get_text(strip=True) if len(info_paragraphs) > 3 else None

        return {
            "Title": title,
            "Price": price,
            "Rating": rating,
            "Colors": colors,
            "Size": size,
            "Gender": gender,
            "timestamp": timestamp,
        }
    except Exception as e:
        logger.error(f"Gagal mem-parsing salah satu kartu produk: {e}")
        return None


def parse_page(html, timestamp):
    """
    Mem-parsing satu halaman HTML penuh dan mengembalikan list of dict
    berisi data mentah seluruh kartu produk pada halaman tersebut.
    """
    try:
        if not html:
            raise ValueError("Konten HTML kosong, tidak dapat di-parsing.")
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="collection-card")
        products = []
        for card in cards:
            product = parse_product_card(card, timestamp)
            if product is not None:
                products.append(product)
        return products
    except Exception as e:
        logger.error(f"Gagal mem-parsing halaman: {e}")
        return []


def scrape_main(total_pages=TOTAL_PAGES, delay=0.5, session=None, base_url=BASE_URL):
    """
    Fungsi utama tahapan extract.

    Melakukan iterasi pengambilan data dari halaman 1 sampai
    `total_pages`, lalu mengembalikan seluruh data mentah dalam
    bentuk list of dict yang siap diolah pada tahapan transform.
    """
    all_products = []
    timestamp = datetime.now().isoformat()
    try:
        for page_number in range(1, total_pages + 1):
            url = build_page_url(page_number, base_url=base_url)
            if not url:
                logger.warning(f"Melewati halaman {page_number} karena URL tidak valid.")
                continue

            html = fetch_page(url, session=session)
            if not html:
                logger.warning(f"Melewati halaman {page_number} karena gagal diambil.")
                continue

            products = parse_page(html, timestamp)
            all_products.extend(products)

            if delay:
                time.sleep(delay)

        logger.info(
            f"Ekstraksi selesai: {len(all_products)} data produk berhasil diambil "
            f"dari {total_pages} halaman."
        )
        return all_products
    except Exception as e:
        logger.error(f"Terjadi kesalahan pada proses scraping utama: {e}")
        return all_products


def save_raw_snapshot(raw_data, bronze_dir, run_timestamp=None):
    """
    Menyimpan hasil ekstraksi mentah (sebelum dibersihkan) ke layer
    BRONZE sebagai satu snapshot per run.

    Bronze bersifat immutable dan append-only: setiap run akan
    membuat berkas baru dengan nama berbasis timestamp, file lama
    tidak pernah ditimpa. Tujuannya agar selalu ada "source of truth"
    mentah yang bisa dipakai untuk reprocessing ulang kalau suatu
    saat ditemukan bug pada logika transform.

    Mengembalikan path file yang berhasil ditulis, atau None jika gagal.
    """
    try:
        if not raw_data:
            logger.warning("Tidak ada data mentah untuk disimpan ke layer bronze.")
            return None

        os.makedirs(bronze_dir, exist_ok=True)
        ts = run_timestamp or datetime.now().strftime("%Y%m%dT%H%M%S")
        file_path = os.path.join(bronze_dir, f"raw_snapshot_{ts}.csv")

        df = pd.DataFrame(raw_data)
        df.to_csv(file_path, index=False)
        logger.info(f"Snapshot mentah (bronze) disimpan: {file_path} ({len(df)} baris).")
        return file_path
    except Exception as e:
        logger.error(f"Gagal menyimpan snapshot bronze: {e}")
        return None


if __name__ == "__main__":
    data = scrape_main()
    print(f"Total data mentah yang diekstrak: {len(data)}")
