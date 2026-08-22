import os
import io
import time
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta

def get_nse_session():
    """NSE कुकीज़ और हेडर्स जनरेट करता है"""
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/'
    }
    session.headers.update(headers)
    
    try:
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ NSE Homepage Connect Warning: {e}", flush=True)
        
    return session

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
    session = get_nse_session()

    current_date = datetime(start_year, 1, 1)
    today = datetime.now()

    downloaded_count = 0
    skipped_count = 0

    print(f"🚀 NSE ऐतिहासिक डेटा डाउनलोड शुरू ({start_year} से आज तक) [With Strict Holiday Date Verification]...\n", flush=True)

    while current_date <= today:
        date_str_file = current_date.strftime('%Y-%m-%d')
        date_dmy = current_date.strftime('%d%m%Y')
        date_str_upper = current_date.strftime('%d%b%Y').upper()
        date_str_lower = current_date.strftime('%d%b%Y').lower()
        year_str = current_date.strftime('%Y')
        month_str = current_date.strftime('%b').upper()

        file_path = f"data/raw/bhav_{date_str_file}.csv"

        # Auto-Resume Support
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
            try:
                response = session.get(bhav_url, timeout=10)

                if response.status_code == 200 and len(response.content) > 500:
                    df = extract_df_from_response(response)
                    df.columns = df.columns.str.strip().str.upper()

                    # 🚨 STRICT HOLIDAY CHECK: फ़ाइल के अंदर की तारीख की जाँच
                    date_col = 'DATE1' if 'DATE1' in df.columns else ('TIMESTAMP' if 'TIMESTAMP' in df.columns else None)
                    if date_col and not df.empty:
                        raw_date = str(df[date_col].iloc[0]).strip()
                        file_actual_date = pd.to_datetime(raw_date).strftime('%Y-%m-%d')

                        # अगर फ़ाइल के अंदर की तारीख और हमारी तारीख मैच न करे, तो रिजेक्ट करें
                        if file_actual_date != date_str_file:
                            continue

                    # Filter EQ and BE series
                    if 'SERIES' in df.columns:
                        df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])].copy()

                    df.to_csv(file_path, index=False)
                    print(f"✅ [{date_str_file}] Downloaded & Verified", flush=True)
                    downloaded_count += 1
                    success = True
                    break
                elif response.status_code == 403:
                    session = get_nse_session()
            except Exception:
                continue

        if not success:
            skipped_count += 1

        time.sleep(0.2)
        current_date += timedelta(days=1)

    print(f"\n🎉 डाउनलोड पूरा हुआ! कुल वैध फ़ाइलें: {downloaded_count}", flush=True)

if __name__ == "__main__":
    download_data_from_earliest_available(start_year=2005)
