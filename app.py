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

            # Susun perintah
            if sys.platform == "win32":
                exe_name = "threads-scraper.exe"
            else:
                exe_name = "threads-scraper"

            venv_scripts = os.path.dirname(sys.executable)
            scraper_exe = os.path.join(venv_scripts, exe_name)

            if not os.path.exists(scraper_exe):
                scraper_exe = shutil.which("threads-scraper")

            if scraper_exe is None:
                st.error("Tidak dapat menemukan threads-scraper. Pastikan paket sudah diinstal.")
                st.stop()

            st.success(f"Scraper ditemukan di: {scraper_exe}")

            cmd = [
                scraper_exe,  # Gunakan jalur absolut
                "--keywords-file", keywords_file,
                "--output", output_path,
                "--limit", str(limit),
                "--delay-min", str(delay_min),
                "--delay-max", str(delay_max),
                "--min-length", str(min_length),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                shell=True  # Biarkan sistem mencari perintah itu sendiri
            )

            try:
                # Jalankan dengan subprocess
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600,  # max 1 jam
                )

                if result.returncode == 0:
                    st.write("✅ Scraping selesai!")
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        df = pd.read_csv(output_path)
                        st.session_state.df_result = df
                        st.write(f"Berhasil mengumpulkan **{len(df)}** baris data.")
                    else:
                        st.warning("File output kosong. Tidak ada data yang ditemukan.")
                else:
                    st.error("Scraping gagal.")
                    st.code(result.stderr)
                    st.code(result.stdout)

            except subprocess.TimeoutExpired:
                st.error("Scraping timeout (melebihi 1 jam). Coba kurangi limit atau kata kunci.")
            except Exception as e:
                st.error(f"Terjadi error: {e}")
            finally:
                # Cleanup file sementara
                for p in [keywords_file, output_path]:
                    try:
                        if os.path.exists(p):
                            os.unlink(p)
                    except Exception:
                        pass

            status.update(label="Scraping selesai", state="complete")

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
