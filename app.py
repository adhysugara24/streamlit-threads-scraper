import streamlit as st
import pandas as pd
import subprocess
import tempfile
import os
import time
import shutil
import sys

st.set_page_config(
    page_title="Threads Scraper - Karhutla",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 Threads Scraper untuk Data Karhutla")
st.markdown(
    "Aplikasi ini menggunakan **threads-comment-scraper** untuk menambang komentar "
    "dan balasan dari Threads berdasarkan kata kunci tertentu. "
    "Cocok untuk riset sentimen masyarakat terhadap isu kebakaran hutan dan lahan gambut."
)

# --- Sidebar: Konfigurasi ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Scraping")

    keywords_input = st.text_area(
        "Kata Kunci (satu per baris)",
        value="karhutla\nkebakaran hutan\nkebakaran lahan\ngambut",
        height=120,
        help="Masukkan kata kunci yang ingin dicari di Threads."
    )

    limit = st.number_input(
        "Batas Maksimal Komentar",
        min_value=10,
        max_value=50000,
        value=1000,
        step=100,
        help="Total maksimal komentar yang akan dikumpulkan."
    )

    col1, col2 = st.columns(2)
    with col1:
        delay_min = st.number_input("Delay Min (detik)", min_value=1.0, max_value=30.0, value=2.0, step=0.5)
    with col2:
        delay_max = st.number_input("Delay Max (detik)", min_value=1.0, max_value=60.0, value=5.0, step=0.5)

    min_length = st.slider(
        "Panjang Minimum Komentar (karakter)",
        min_value=0,
        max_value=100,
        value=10,
        help="Abaikan komentar yang lebih pendek dari ini."
    )
    st.divider()
    st.subheader("📅 Filter Waktu")

    use_date_filter = st.checkbox(
        "Aktifkan filter rentang tanggal",
        value=False,
        help="Filter ini diterapkan SETELAH data terkumpul, bukan saat scraping."
    )

    if use_date_filter:
        date_from = st.date_input("Dari Tanggal", value=None)
        date_to = st.date_input("Sampai Tanggal", value=None)
    else:
        date_from = None
        date_to = None

    run_button = st.button("🚀 Mulai Scraping", type="primary", use_container_width=True)

# --- Main Area ---
if "df_result" not in st.session_state:
    st.session_state.df_result = None

if run_button:
    if not keywords_input.strip():
        st.error("Masukkan setidaknya satu kata kunci.")
    elif delay_min > delay_max:
        st.error("Delay minimum tidak boleh lebih besar dari delay maximum.")
    else:
        with st.status("Menjalankan scraping...", expanded=True) as status:
            st.write("Menyiapkan file kata kunci...")

            # Buat file kata kunci sementara
            keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                for kw in keywords:
                    f.write(kw + "\n")
                keywords_file = f.name

            # File output sementara
            output_fd, output_path = tempfile.mkstemp(suffix=".csv")
            os.close(output_fd)

            st.write(f"Kata kunci: {', '.join(keywords)}")
            st.write("Menjalankan threads-scraper... (proses ini mungkin memakan waktu)")

            # ============================================================
            # ▼▼▼ KODE FINAL: MONKEY-PATCH CHROME OPTIONS ▼▼▼
            # ============================================================
            st.info("Menginisialisasi ThreadsScraper dengan opsi Cloud...")

            try:
                import sys
                import os
                import pandas as pd
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options

                # --- MULAI TAMBALAN (MONKEY-PATCH) ---
                # Kita paksa library threads_scraper untuk menggunakan opsi Chrome yang aman untuk cloud
                import threads_scraper.scraper as ts

                def get_cloud_driver(self):
                    chrome_options = Options()
                    # Opsi wajib untuk lingkungan cloud/container
                    chrome_options.add_argument("--headless=new")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--window-size=1920,1080")

                    # Tentukan path chromedriver yang benar di Streamlit Cloud
                    # Berdasarkan log, chromedriver ada di /usr/bin/chromedriver
                    service = Service("/usr/bin/chromedriver")

                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    return self.driver

                # Timpa method asli di dalam library
                ts.ThreadsScraper.get_driver = get_cloud_driver
                # --- AKHIR TAMBALAN ---

                # Sekarang panggil library seperti biasa
                from threads_scraper.scraper import ThreadsScraper

                scraper = ThreadsScraper(
                    username=None,
                    password=None,
                    driver_path="/usr/bin/chromedriver" # Tetap berikan path agar tidak error di library
                )

                # Mulai driver
                scraper.get_driver()

                st.info("Mengecek akses ke halaman Threads...")
                scraper.driver.get("https://www.threads.net/search?q=karhutla")

                import time
                time.sleep(5) # Tunggu 5 detik

                # Simpan screenshot
                scraper.driver.save_screenshot("debug_threads.png")

                # Tampilkan di Streamlit
                if os.path.exists("debug_threads.png"):
                    st.image("debug_threads.png", caption="Tampilan Threads dari Server AWS")

                # Cek apakah diblokir
                page_source = scraper.driver.page_source.lower()
                if "log in" in page_source or "masuk" in page_source:
                    st.error("🚨 TERDETEKSI HALAMAN LOGIN. Threads memblokir akses dari IP Server Cloud.")
                elif "captcha" in page_source:
                    st.error("🚨 TERDETEKSI CAPTCHA. Threads mendeteksi bot.")
                else:
                    st.success("Halaman berhasil dimuat tanpa blokir.")

                # 4. Proses Scraping
                st.info("Sedang melakukan scraping... (Mohon tunggu, jangan tutup halaman ini)")

                keywords_list = [k.strip() for k in keywords_input.split("\n") if k.strip()]
                scroll_times = max(5, int(limit / 10))

                data = scraper.scrape(keywords_list, scroll_times)

                # 5. Simpan ke CSV
                scraper.save_to_csv(data, output_path, csv_index=False)
                scraper.close()

                # ============================================================
                # ▼▼▼ GANTI BAGIAN PEMBACAAN CSV DENGAN INI ▼▼▼
                # ============================================================
                # 6. Baca hasil dan tampilkan (dengan penanganan file kosong)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    try:
                        df = pd.read_csv(output_path)
                        if not df.empty:
                            st.session_state.df_result = df
                            st.success(f"✅ Scraping selesai! Berhasil mengumpulkan **{len(df)}** baris data.")
                        else:
                            st.warning("Scraping selesai, tetapi DataFrame kosong (tidak ada baris data).")
                    except pd.errors.EmptyDataError:
                        st.warning("⚠️ Scraper berjalan, tetapi file CSV kosong (tidak ada data yang berhasil diekstrak).")
                else:
                    st.warning("⚠️ Scraper berjalan, tetapi tidak menghasilkan file atau file berukuran 0 bytes.")
                    st.info("Kemungkinan Threads tidak memuat hasil untuk kata kunci ini, atau akses dari server cloud diblokir (GeoIP).")

            except Exception as e:
                st.error(f"Terjadi error saat scraping: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                try:
                    if os.path.exists(keywords_file):
                        os.unlink(keywords_file)
                except Exception:
                    pass

            status.update(label="Proses Selesai", state="complete")

# --- Tampilkan Hasil ---
if st.session_state.df_result is not None:
    df = st.session_state.df_result.copy()

    st.header("📊 Hasil Scraping")

    # --- Terapkan filter waktu jika diaktifkan ---
    if use_date_filter and "timestamp" in df.columns:
        # Konversi timestamp ke datetime
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
        df["date"] = df["datetime"].dt.date

        original_count = len(df)

        if date_from is not None:
            df = df[df["date"] >= date_from]
        if date_to is not None:
            df = df[df["date"] <= date_to]

        filtered_count = len(df)
        st.info(
            f"🔍 Filter waktu aktif: **{filtered_count}** dari **{original_count}** baris "
            f"({date_from or 'awal'} s/d {date_to or 'sekarang'})"
        )

        if filtered_count == 0:
            st.warning("Tidak ada data dalam rentang tanggal yang dipilih.")
            st.stop()

    # --- Ringkasan ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Baris", len(df))
    with col2:
        if "type" in df.columns:
            st.metric("Total Komentar", len(df[df["type"] == "comment"]))
    with col3:
        if "type" in df.columns:
            st.metric("Total Balasan", len(df[df["type"] == "reply"]))

    # --- Tabel ---
    st.dataframe(df, use_container_width=True, height=400)

    # Tombol download hasil filter
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV (hasil filter)",
        data=csv_data,
        file_name=f"threads_karhutla_filtered_{int(time.time())}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Tombol download data mentah
    if use_date_filter:
        raw_csv = st.session_state.df_result.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download CSV (data mentah lengkap)",
            data=raw_csv,
            file_name=f"threads_karhutla_raw_{int(time.time())}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # --- Statistik ---
    with st.expander("📈 Lihat Statistik Kolom"):
        st.write(df.describe(include="all"))
