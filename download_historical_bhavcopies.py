import os
import io
import time
import zipfile
import subprocess
import requests
import pandas as pd
from datetime import datetime, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def auto_git_push(downloaded_count):
    """हर 10 फ़ाइलों के बाद ऑटोमैटिक GitHub पर Commit & Push करता है"""
    try:
        print(f"\n🔄 [Auto-Sync] {downloaded_count} नई फ़ाइलें डाउनलोड हुईं। GitHub पर Push किया जा रहा है...", flush=True)
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", "data/raw/"], check=False)
        subprocess.run(["git", "commit", "-m", f"Auto-save: Downloaded {downloaded_count} files [skip ci]"], check=False)
        
        result = subprocess.run(["git", "push"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✅ [Auto-Sync Complete] Repo सफलतापूर्वक अपडेट हो गया है!\n", flush=True)
        else:
            print(f"⚠️ Git Push Warning: {result.stderr.strip()}\n", flush=True)
    except Exception as e:
        print(f"⚠️ Git Push करने में त्रुटि: {e}\n", flush=True)

def extract_df_from_response(response):
    """ZIP या CSV फ़ाइल को Read करके DataFrame में बदलता है"""
    content = response.content
    if content.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            csv_filenames = [f for f in z.namelist() if f.lower().endswith('.csv')]
            if csv_filenames:
                with z.open(csv_filenames[0]) as csv_file:
                    return pd.read_csv(csv_file)
    return pd.read_csv(io.BytesIO(content))

def download_data_from_earliest_available(start_year=2005):
    os.makedirs("data/raw", exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass

    current_date = datetime(start_year, 1, 1)
    today = datetime.now()

    downloaded_count = 0
    newly_downloaded_in_this_run = 0
    skipped_count = 0

    print(f"🚀 NSE ऐतिहासिक डेटा डाउनलोड शुरू ({start_year} से {today.strftime('%Y-%m-%d')} तक)...\n", flush=True)

    while current_date <= today:
        date_str_file = current_date.strftime('%Y-%m-%d')
        date_dmy = current_date.strftime('%d%m%Y')
        date_str_upper = current_date.strftime('%d%b%Y').upper()
        date_str_lower = current_date.strftime('%d%b%Y').lower()
        year_str = current_date.strftime('%Y')
        month_str = current_date.strftime('%b').upper()

        file_path = f"data/raw/bhav_{date_str_file}.csv"

        # Auto-Resume Support: अगर फ़ाइल पहले से मौजूद है, तो स्किप करें
        if os.path.exists(file_path):
            downloaded_count += 1
            current_date += timedelta(days=1)
            continue

        urls_to_try = [
            f"https://archives.nseindia.com/content/historical/EQUITIES/{year_str}/{month_str}/cm{date_str_upper}bhav.csv.zip",
            f"https://archives.nseindia.com/content/historical/EQUITIES/{year_str}/{month_str}/cm{date_str_lower}bhav.csv.zip",
            f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_dmy}.csv"
        ]

        success = False
        for bhav_url in urls_to_try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = session.get(bhav_url, timeout=12)

                    if response.status_code == 200 and len(response.content) > 500:
                        df = extract_df_from_response(response)
                        df.columns = df.columns.str.strip().str.upper()

                        # Strict Date Check
                        date_col = 'DATE1' if 'DATE1' in df.columns else ('TIMESTAMP' if 'TIMESTAMP' in df.columns else None)
                        if date_col and not df.empty:
                            raw_date = str(df[date_col].iloc[0]).strip()
                            file_actual_date = pd.to_datetime(raw_date).strftime('%Y-%m-%d')

                            if file_actual_date != date_str_file:
                                break

                        # Keep EQ & BE series
                        if 'SERIES' in df.columns:
                            df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])].copy()

                        df.to_csv(file_path, index=False)
                        print(f"✅ [{date_str_file}] Downloaded & Saved", flush=True)

                        downloaded_count += 1
                        newly_downloaded_in_this_run += 1
                        success = True

                        # हर 10 नई फ़ाइलों पर Auto Push
                        if newly_downloaded_in_this_run % 10 == 0:
                            auto_git_push(newly_downloaded_in_this_run)

                        break

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                    if attempt < max_retries - 1:
                        print(f"⚠️ [{date_str_file}] Network Timeout. Retrying ({attempt + 1}/{max_retries})...", flush=True)
                        time.sleep(2)
                except Exception:
                    break

            if success:
                break

        if not success:
            skipped_count += 1

        time.sleep(0.3)
        current_date += timedelta(days=1)

    # बचा हुआ डेटा अंत में पुश करें
    if newly_downloaded_in_this_run % 10 != 0:
        auto_git_push(newly_downloaded_in_this_run)

    print(f"\n🎉 डाउनलोड और सिंक प्रक्रिया पूरी हुई!", flush=True)
    print(f"📊 कुल फ़ाइलें: {downloaded_count} | छुट्टियाँ/नॉन-ट्रेडिंग डेज़: {skipped_count}", flush=True)

if __name__ == "__main__":
    download_data_from_earliest_available(start_year=2005)
