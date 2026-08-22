import os
import io
import time
import requests
import pandas as pd

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

def fetch_nse_official_fno(session):
    """NSE के आधिकारिक F&O Lot Size डेटाबेस से सही सिंबल्स निकालना"""
    fno_symbols = set()
    furl = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    try:
        res = session.get(furl, timeout=15)
        if res.status_code == 200:
            lines = res.text.splitlines()
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                # NSE fo_mktlots में सिंबल 2रे या 3रे कॉलम में होता है
                if len(parts) >= 2:
                    sym = parts[1].upper()
                    # अगर हेडर्स या बेकार टेक्स्ट न हो
                    if sym and sym not in ['SYMBOL', 'UNDERLYING', 'DERIVATIVES', 'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
                        # केवल वैलिड स्टॉक अक्षरों को ही लें
                        if sym.isalnum():
                            fno_symbols.add(sym)
    except Exception as e:
        print(f"⚠️ NSE F&O Error: {e}", flush=True)
        
    return fno_symbols

def create_nifty500_master():
    print("🚀 Nifty 500 लिस्ट, F&O फ्लैग, सेक्टर्स और इंडेक्स डेटा तैयार किया जा रहा है...", flush=True)
    os.makedirs("data/master", exist_ok=True)
    
    session = get_nse_session()

    # 1. Nifty 500 की आधिकारिक लिस्ट
    n500_urls = [
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
        "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv"
    ]
    n500_df = fetch_csv_safe(session, n500_urls)
    
    if n500_df is None:
        print("❌ Nifty 500 लिस्ट डाउनलोड करने में असमर्थ।", flush=True)
        return

    print(f"✅ Nifty 500 स्टॉक्स लोड हो गए! कुल स्टॉक्स: {len(n500_df)}", flush=True)

    # 2. NSE Official F&O List
    fno_symbols = fetch_nse_official_fno(session)
    if fno_symbols:
        print(f"✅ NSE Official से F&O स्टॉक्स मिले: {len(fno_symbols)} स्टॉक्स", flush=True)
    else:
        print("⚠️ NSE F&O लिस्ट प्राप्त नहीं हो सकी, आगे बढ़ रहे हैं...", flush=True)

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

    # 4. Master Data Frame तैयार करना
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
