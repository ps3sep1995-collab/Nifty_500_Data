import os
import requests
import pandas as pd
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def download_today_bhavcopy():
    os.makedirs("data/raw", exist_ok=True)
    today_str = datetime.now().strftime('%Y-%m-%d')
    date_dmy = datetime.now().strftime('%d%m%Y')
    raw_file = f"data/raw/bhav_{today_str}.csv"

    print(f"📥 NSE से आज की ({today_str}) Bhavcopy डाउनलोड हो रही है...")
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        session.get("https://www.nseindia.com", timeout=10)
        bhav_url = f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_dmy}.csv"
        response = session.get(bhav_url, timeout=15)

        if response.status_code != 200:
            print(f"⚠️ आज का NSE डेटा अभी उपलब्ध नहीं है (HTTP Status: {response.status_code})")
            return None

        with open(raw_file, 'wb') as f:
            f.write(response.content)

        df = pd.read_csv(raw_file)
        df.columns = df.columns.str.strip().str.upper()

        # Equity Series filter (केवल EQ शेयर्स)
        if 'SERIES' in df.columns:
            df = df[df['SERIES'].str.strip() == 'EQ'].copy()

        df.to_csv(raw_file, index=False)
        print(f"✅ `data/raw/bhav_{today_str}.csv` सफलतापूर्वक डाउनलोड हो गई!")
        return raw_file

    except Exception as e:
        print(f"❌ Bhavcopy डाउनलोड में त्रुटि: {e}")
        return None

if __name__ == "__main__":
    download_today_bhavcopy()
