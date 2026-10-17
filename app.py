import streamlit as st
import pandas as pd
import os
import sys
import time
import tempfile

st.set_page_config(page_title="Threads Scraper Karhutla", page_icon="🔥", layout="wide")

st.title("🔥 Threads Scraper untuk Data Karhutla")
st.markdown("Aplikasi ini menambang komentar publik di Threads terkait isu kebakaran hutan dan lahan gambut.")

# --- Sidebar: Konfigurasi ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Scraping")

    keywords_input = st.text_area(
        "Kata Kunci (satu per baris)",
        value="karhutla\nkebakaran hutan\ngambut",
        height=120
    )

    limit = st.number_input("Batas Maksimal Komentar", min_value=10, max_value=5000, value=50, step=10)

    col1, col2 = st.columns(2)
    with col1:
        delay_min = st.number_input("Delay Min (detik)", min_value=1.0, max_value=30.0, value=2.0)
    with col2:
        delay_max = st.number_input("Delay Max (detik)", min_value=1.0, max_value=60.0, value=5.0)

    min_length = st.slider("Panjang Minimum Komentar", 0, 100, 10)

    run_button = st.button("🚀 Mulai Scraping", type="primary", use_container_width=True)

# --- Main Area ---
if "df_result" not in st.session_state:
    st.session_state.df_result = None

if run_button:
    if not keywords_input.strip():
        st.error("Masukkan setidaknya satu kata kunci.")
    else:
        with st.status("Menjalankan scraping...", expanded=True) as status:
            st.write("Menyiapkan file...")

            # Buat file sementara untuk output
            output_fd, output_path = tempfile.mkstemp(suffix=".csv")
            os.close(output_fd)

            keywords_list = [k.strip() for k in keywords_input.split("\n") if k.strip()]

            # Konversi limit ke perkiraan jumlah scroll (1 scroll ≈ 10 data)
            scroll_times = max(1, int(limit / 10))

            st.write(f"Kata kunci: {', '.join(keywords_list)}")
            st.write(f"Target: ~{limit} komentar ({scroll_times} kali scroll)")

            try:
                # --- IMPORT LIBRARY ---
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                from webdriver_manager.chrome import ChromeDriverManager
                import threads_scraper.scraper as ts

                # --- SETUP DRIVER BERDASARKAN OS ---
                def get_custom_driver(self):
                    chrome_options = Options()

                    # Deteksi OS
                    if sys.platform == "win32":
                        # Windows (Lokal): Bisa pakai GUI (headless=False) agar terlihat
                        st.info("🖥️ Mendeteksi Windows (Lokal). Menjalankan browser dengan tampilan...")
                        # chrome_options.add_argument("--headless=new") # Uncomment jika ingin tanpa tampilan
                    elif sys.platform == "darwin":
                        # macOS (Lokal)
                        st.info("🍎 Mendeteksi macOS (Lokal). Menjalankan browser...")
                    else:
                        # Linux (Streamlit Cloud)
                        st.info("☁️ Mendeteksi Linux (Cloud). Menjalankan headless browser...")
                        chrome_options.add_argument("--headless=new")
                        chrome_options.add_argument("--no-sandbox")
                        chrome_options.add_argument("--disable-dev-shm-usage")
                        chrome_options.add_argument("--disable-gpu")

                    chrome_options.add_argument("--window-size=1920,1080")
                    chrome_options.add_argument("--disable-notifications")

                    # Gunakan webdriver-manager untuk otomatis mengunduh driver yang cocok
                    # Ini jauh lebih mudah daripada hardcode path
                    service = Service(ChromeDriverManager().install())

                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    return self.driver

                # Timpa fungsi bawaan library
                ts.ThreadsScraper.get_driver = get_custom_driver
                from threads_scraper.scraper import ThreadsScraper

                # Inisialisasi Scraper
                scraper = ThreadsScraper(
                    username=None,
                    password=None,
                    driver_path="dummy" # Path diabaikan karena kita pakai webdriver-manager
                )

                st.write("Membuka browser...")
                scraper.get_driver()

                st.write("Melakukan scraping... (Mohon tunggu, proses ini memakan waktu)")
                data = scraper.scrape(keywords_list, scroll_times)

                st.write("Menyimpan data...")
                scraper.save_to_csv(data, output_path, csv_index=False)
                scraper.close()

                # Baca hasil
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    try:
                        df = pd.read_csv(output_path)
                        if not df.empty:
                            st.session_state.df_result = df
                            st.success(f"✅ Scraping selesai! Berhasil mengumpulkan **{len(df)}** baris data.")
                        else:
                            st.warning("Scraping selesai, tetapi tidak ada data yang ditemukan.")
                    except pd.errors.EmptyDataError:
                        st.warning("File CSV kosong.")
                else:
                    st.warning("Scraper berjalan, tetapi tidak menghasilkan file data.")

            except Exception as e:
                st.error(f"Terjadi error saat scraping: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                try:
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                except:
                    pass

            status.update(label="Proses Selesai", state="complete")

# --- Tampilkan Hasil ---
if st.session_state.df_result is not None:
    df = st.session_state.df_result

    st.header("📊 Hasil Scraping")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Baris", len(df))
    with col2:
        if "type" in df.columns:
            st.metric("Total Komentar", len(df[df["type"] == "comment"]))
    with col3:
        if "type" in df.columns:
            st.metric("Total Balasan", len(df[df["type"] == "reply"]))

    st.dataframe(df, use_container_width=True, height=400)

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name=f"threads_karhutla_{int(time.time())}.csv",
        mime="text/csv",
        use_container_width=True,
    )
