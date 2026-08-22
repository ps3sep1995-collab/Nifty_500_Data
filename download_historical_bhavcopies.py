import os
import io
import time
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def extract_df_from_response(response):
    """ZIP या सीधी CSV को आसानी से DataFrame में बदलता है"""
    content = response.content
    # ZIP Format Check (Magic Bytes)
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
    skipped_count = 0

    print(f"🚀 NSE डेटा डाउनलोड शुरू ({start_year} से {today.strftime('%Y-%m-%d')} तक) [With Auto-Retry]...\n")

    while current_date <= today:
        date_str_file = current_date.strftime('%Y-%m-%d')
        date_dmy = current_date.strftime('%d%m%Y')
        date_str_upper = current_date.strftime('%d%b%Y').upper()   # e.g. 03JAN2005
        date_str_lower = current_date.strftime('%d%b%Y').lower()   # e.g. 03jan2005
        year_str = current_date.strftime('%Y')
        month_str = current_date.strftime('%b').upper()

        file_path = f"data/raw/bhav_{date_str_file}.csv"

        # Auto-Resume: अगर फ़ाइल पहले से मौजूद है, तो तुरंत स्किप करें
        if os.path.exists(file_path):
            downloaded_count += 1
            current_date += timedelta(days=1)
            continue

        # NSE के अलग-अलग URL पैटर्न्स
        urls_to_try = [
            f"https://archives.nseindia.com/content/historical/EQUITIES/{year_str}/{month_str}/cm{date_str_upper}bhav.csv.zip",
            f"https://archives.nseindia.com/content/historical/EQUITIES/{year_str}/{month_str}/cm{date_str_lower}bhav.csv.zip",
            f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_dmy}.csv"
        ]

        success = False
        for bhav_url in urls_to_try:
            # 🔁 AUTO-RETRY LOGIC (Timeout या Network error आने पर 3 बार प्रयास करेगा)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = session.get(bhav_url, timeout=12)

                    if response.status_code == 200 and len(response.content) > 500:
                        df = extract_df_from_response(response)
                        df.columns = df.columns.str.strip().str.upper()

                        # Date Match Check (छुट्टी वाले दिन पुराना डेटा रिजेक्ट करने के लिए)
                        date_col = 'DATE1' if 'DATE1' in df.columns else ('TIMESTAMP' if 'TIMESTAMP' in df.columns else None)
                        if date_col and not df.empty:
                            raw_date = str(df[date_col].iloc[0]).strip()
                            file_actual_date = pd.to_datetime(raw_date).strftime('%Y-%m-%d')

                            if file_actual_date != date_str_file:
                                break  # तारीख मैच नहीं हुई मतलब छुट्टी थी, Retry करने की ज़रूरत नहीं

                        # Clean EQ/BE series
                        if 'SERIES' in df.columns:
                            df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])].copy()

                        df.to_csv(file_path, index=False)
                        print(f"✅ [{date_str_file}] Data Downloaded & Verified")
                        downloaded_count += 1
                        success = True
                        break  # Successful download, exit retry loop

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ [{date_str_file}] Network/Timeout Error. Retrying ({attempt + 1}/{max_retries})...")
                        time.sleep(2)  # Pause before retry
                    else:
                        print(f"❌ [{date_str_file}] Failed after {max_retries} attempts.")
                except Exception:
                    break  # अन्य त्रुटियों के लिए सीधे अगले URL पर जाएँ

            if success:
                break  # अगर डाउनलोड सफल हो गया तो दूसरे URL ट्राई करने की ज़रूरत नहीं

        if not success:
            skipped_count += 1

        time.sleep(0.3)
        current_date += timedelta(days=1)

    print(f"\n🎉 NSE के ऐतिहासिक डेटा का डाउनलोड पूरा हुआ!")
    print(f"📊 कुल डाउनलोड फ़ाइलें: {downloaded_count} | छुट्टियाँ/नॉन-ट्रेडिंग डेज़: {skipped_count}")

if __name__ == "__main__":
    download_data_from_earliest_available(start_year=2005)
