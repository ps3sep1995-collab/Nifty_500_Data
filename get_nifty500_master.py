import os
import io
import time
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/'
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
    except Exception:
        pass
    return session

def fetch_csv_safe(session, urls):
    for url in urls:
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200 and len(res.content) > 200:
                df = pd.read_csv(io.BytesIO(res.content))
                df.columns = df.columns.str.strip()
                return df
        except Exception:
            continue
    return None

def fetch_fno_symbols_from_bhavcopy(session):
    """NSE F&O Bhavcopy से ताज़ा F&O स्टॉक्स निकालना"""
    fno_symbols = set()
    current_date = datetime.now()
    
    # पिछले 10 दिनों में से सबसे हालिया वर्किंग डे (Trading Day) ढूंढना
    for i in range(10):
        target_date = current_date - timedelta(days=i)
        
        # शनिवार (5) और रविवार (6) को स्किप करें
        if target_date.weekday() >= 5:
            continue

        date_str_upper = target_date.strftime("%d%b%Y").upper() # Ex: 19AUG2026
        year_str = target_date.strftime("%Y")
        month_str_upper = target_date.strftime("%b").upper()   # Ex: AUG
        
        # NSE FO Bhavcopy URL
        url = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{year_str}/{month_str_upper}/fo{date_str_upper}bhav.csv.zip"
        
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200 and len(res.content) > 1000:
                # Zip फ़ाइल अनज़िप करें
                with zipfile.ZipFile(io.BytesIO(res.content)) as z:
                    csv_filename = z.namelist()[0]
                    with z.open(csv_filename) as f:
                        df = pd.read_csv(f)
                        df.columns = df.columns.str.strip()
                        
                        # F&O स्टॉक्स (INSTRUMENT == 'STKFUT' या 'STKOPT') के सिंबल्स निकालना
                        if 'INSTRUMENT' in df.columns and 'SYMBOL' in df.columns:
                            stk_df = df[df['INSTRUMENT'].str.startswith('STK', na=False)]
                            fno_symbols = set(stk_df['SYMBOL'].str.strip().str.upper().unique())
                        elif 'SYMBOL' in df.columns:
                            # नए फॉर्मैट के लिए
                            fno_symbols = set(df['SYMBOL'].str.strip().str.upper().unique())
                            
                        if len(fno_symbols) > 50:
                            print(f"✅ NSE F&O Bhavcopy ({target_date.strftime('%Y-%m-%d')}) से F&O स्टॉक्स मिले: {len(fno_symbols)} स्टॉक्स", flush=True)
                            return fno_symbols
        except Exception:
            continue
            
    return fno_symbols

def create_nifty500_master():
    print("🚀 Nifty 500 लिस्ट, F&O फ्लैग, सेक्टर्स और इंडेक्स डेटा तैयार किया जा रहा है...", flush=True)
    os.makedirs("data/master", exist_ok=True)
    
    session = get_nse_session()

    # 1. Nifty 500 आधिकारिक लिस्ट
    n500_urls = [
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv"
    ]
    n500_df = fetch_csv_safe(session, n500_urls)
    
    if n500_df is None:
        print("❌ Nifty 500 लिस्ट डाउनलोड करने में असमर्थ।", flush=True)
        return

    print(f"✅ Nifty 500 स्टॉक्स लोड हो गए! कुल स्टॉक्स: {len(n500_df)}", flush=True)

    # 2. NSE F&O Bhavcopy से F&O स्टॉक्स निकालें
    fno_symbols = fetch_fno_symbols_from_bhavcopy(session)
    if not fno_symbols:
        print("⚠️ F&O Bhavcopy प्राप्त नहीं हो सकी, आगे बढ़ रहे हैं...", flush=True)

    # 3. Sub-Indices मैपिंग
    indices_config = {
        'NIFTY 50': ["https://archives.nseindia.com/content/indices/ind_nifty50list.csv"],
        'NIFTY BANK': ["https://archives.nseindia.com/content/indices/ind_niftybanklist.csv"],
        'NIFTY NEXT 50': ["https://archives.nseindia.com/content/indices/ind_niftynext50list.csv"],
        'NIFTY MIDCAP 100': ["https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv"],
        'NIFTY SMALLCAP 100': ["https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv"],
        'NIFTY FIN SERVICE': ["https://archives.nseindia.com/content/indices/ind_niftyfinancialserviceslist.csv"]
    }

    index_mapping = {}
    for idx_name, urls in indices_config.items():
        df = fetch_csv_safe(session, urls)
        if df is not None and 'Symbol' in df.columns:
            for sym in df['Symbol'].str.strip().str.upper():
                index_mapping.setdefault(sym, []).append(idx_name)

    # 4. Master CSV डेटाबेस बनाएं
    master_rows = []

    for _, row in n500_df.iterrows():
        symbol = str(row.get('Symbol', '')).strip().upper()
        company_name = str(row.get('Company Name', '')).strip()
        industry = str(row.get('Industry', 'Others')).strip()
        isin = str(row.get('ISIN Code', 'NA')).strip()

        if not symbol or symbol == 'NAN':
            continue

        is_fno = 1 if symbol in fno_symbols else 0

        matched_indices = index_mapping.get(symbol, [])
        if "NIFTY 500" not in matched_indices:
            matched_indices.append("NIFTY 500")

        indices_str = ", ".join(matched_indices)

        master_rows.append({
            'SYMBOL': symbol,
            'COMPANY_NAME': company_name,
            'ISIN': isin,
            'SECTOR': industry,
            'INDICES': indices_str,
            'IS_FNO': is_fno
        })

    master_df = pd.DataFrame(master_rows)
    output_path = "data/master/nifty500_master.csv"
    master_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! Nifty 500 की मास्टर फ़ाइल `{output_path}` में सेव हो गई है।", flush=True)
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}", flush=True)
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}", flush=True)

if __name__ == "__main__":
    create_nifty500_master()
