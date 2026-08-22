import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def download_historical_bhavcopies(days_to_fetch=30):
    """
    पिछले N दिनों की NSE Bhavcopy डाउनलोड करता है।
    """
    os.makedirs("data/raw", exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    # Initial session request to set cookies
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception as e:
        print(f"⚠️ NSE होमपेज कनेक्ट करने में समस्या: {e}")

    end_date = datetime.now()
    downloaded_count = 0
    skipped_count = 0

    print(f"🚀 पिछले {days_to_fetch} दिनों का ऐतिहासिक (Historical) डेटा डाउनलोड शुरू हो रहा है...\n")

    for i in range(days_to_fetch):
        target_date = end_date - timedelta(days=i)
        
        # शनिवार (5) और रविवार (6) को स्किप करें
        if target_date.weekday() >= 5:
            continue

        date_str_file = target_date.strftime('%Y-%m-%d')
        date_dmy = target_date.strftime('%d%m%Y')
        file_path = f"data/raw/bhav_{date_str_file}.csv"

        # अगर फ़ाइल पहले से डाउनलोड है, तो दोबारा न करें
        if os.path.exists(file_path):
            print(f"⏩ [{date_str_file}] पहले से मौजूद है। Skipping...")
            downloaded_count += 1
            continue

        bhav_url = f"https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_dmy}.csv"
        
        try:
            response = session.get(bhav_url, timeout=12)

            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)

                # EQ Series Filter
                df = pd.read_csv(file_path)
                df.columns = df.columns.str.strip().str.upper()
                if 'SERIES' in df.columns:
                    df = df[df['SERIES'].str.strip() == 'EQ'].copy()
                df.to_csv(file_path, index=False)

                print(f"✅ [{date_str_file}] Bhavcopy डाउनलोड सफल!")
                downloaded_count += 1
            else:
                # 404 यानी मार्केट हॉलिडे या डेटा उपलब्ध नहीं है
                print(f"❌ [{date_str_file}] डेटा उपलब्ध नहीं है (मार्केट हॉलिडे या संडे)")
                skipped_count += 1

        except Exception as e:
            print(f"⚠️ [{date_str_file}] डाउनलोड एरर: {e}")
            skipped_count += 1

        # NSE Server पर लोड न पड़े इसलिए छोटा सा delay
        time.sleep(1)

    print(f"\n🎉 डाउनलोड प्रक्रिया पूरी हुई!")
    print(f"📊 कुल उपलब्ध फ़ाइलें: {downloaded_count} | स्किप/हॉलिडे: {skipped_count}")

if __name__ == "__main__":
    # आप जितने दिनों का डेटा डाउनलोड करना चाहते हैं (उदा. 30 या 60 दिन) यहाँ बदल सकते हैं
    download_historical_bhavcopies(days_to_fetch=30)
