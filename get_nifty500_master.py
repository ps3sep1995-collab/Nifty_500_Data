import os
import io
import time
import zipfile
import requests
import pandas as pd
from datetime import datetime, timedelta

# Browser Headers to bypass NSE Cloudflare/Bot-blocker
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}

def get_nse_session():
    """NSE वेबसाइट से असली Cookies और Session प्राप्त करने के लिए Warmup"""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        # NSE Home page hit to get valid cookies
        res = session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        # Option Chain page hit to refresh active session
        session.get("https://www.nseindia.com/option-chain", timeout=15)
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ NSE Session Connection Warning: {e}", flush=True)
    return session

def fetch_fno_symbols_from_nse():
    """सीधे NSE Archives से F&O (Derivatives) मास्टर लिस्ट खींचना"""
    fno_symbols = set()
    session = get_nse_session()

    # 1. NSE Direct Live Fo-Lots List
    mktlot_urls = [
        "https://archives.nseindia.com/content/fo/fo_mktlots.csv",
        "https://www.nseindia.com/content/fo/fo_mktlots.csv"
    ]

    for url in mktlot_urls:
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200 and len(res.content) > 200:
                lines = res.text.splitlines()
                for line in lines:
                    parts = [p.strip() for p in line.split(',')]
                    for p in parts[:3]:
                        sym = p.upper().replace('"', '').strip()
                        if sym and sym.isalnum() and sym not in ['SYMBOL', 'UNDERLYING', 'DERIVATIVES', 'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NAN']:
                            fno_symbols.add(sym)
                if len(fno_symbols) > 50:
                    print(f"✅ NSE (fo_mktlots.csv) से सीधे F&O स्टॉक्स मिले: {len(fno_symbols)}", flush=True)
                    return fno_symbols
        except Exception:
            continue

    # 2. NSE Bhavcopy (Last 5 days search if Weekend/Holiday)
    today = datetime.now()
    for i in range(5):
        date_str = (today - timedelta(days=i)).strftime('%d%b%Y').upper()
        # NSE F&O Bhavcopy URL
        bhav_url = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{today.strftime('%Y')}/{date_str[:3]}/fo{date_str}bhav.csv.zip"
        
        try:
            res = session.get(bhav_url, timeout=15)
            if res.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(res.content)) as z:
                    csv_filename = z.namelist()[0]
                    with z.open(csv_filename) as f:
                        df = pd.read_csv(f)
                        df.columns = df.columns.str.strip()
                        # STKFS (Stock Futures) फ़िल्टर करें
                        fno_df = df[df['INSTRUMENT'].isin(['FUTSTK', 'OPTSTK'])]
                        fno_symbols = set(fno_df['SYMBOL'].str.strip().str.upper().unique())
                        
                        if len(fno_symbols) > 50:
                            print(f"✅ NSE Historical Bhavcopy ({date_str}) से F&O स्टॉक्स मिले: {len(fno_symbols)}", flush=True)
                            return fno_symbols
        except Exception:
            continue

    return fno_symbols

def create_nifty500_master():
    print("🚀 NSE से Nifty 500 लिस्ट, F&O फ्लैग और इंडेक्स डेटा डाउनलोड किया जा रहा है...", flush=True)
    os.makedirs("data/master", exist_ok=True)

    session = get_nse_session()

    # 1. Nifty 500 Master List directly from NSE Archives
    n500_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = session.get(n500_url, timeout=15)
        n500_df = pd.read_csv(io.BytesIO(res.content))
        n500_df.columns = n500_df.columns.str.strip()
        print(f"✅ NSE से Nifty 500 स्टॉक्स लोड हो गए! कुल: {len(n500_df)}", flush=True)
    except Exception as e:
        print(f"❌ NSE Nifty 500 डाउनलोड में समस्या: {e}", flush=True)
        return

    # 2. Direct NSE F&O List Fetching
    fno_symbols = fetch_fno_symbols_from_nse()

    # 3. Sub-Indices Mapping from NSE
    indices_config = {
        'NIFTY 50': "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        'NIFTY BANK': "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        'NIFTY NEXT 50': "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        'NIFTY MIDCAP 100': "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        'NIFTY SMALLCAP 100': "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
        'NIFTY FIN SERVICE': "https://archives.nseindia.com/content/indices/ind_niftyfinancialserviceslist.csv"
    }

    index_mapping = {}
    for idx_name, url in indices_config.items():
        try:
            res = session.get(url, timeout=10)
            if res.status_code == 200:
                df = pd.read_csv(io.BytesIO(res.content))
                sym_col = [c for c in df.columns if 'symbol' in c.lower()]
                if sym_col:
                    for sym in df[sym_col[0]].astype(str).str.strip().str.upper():
                        index_mapping.setdefault(sym, []).append(idx_name)
        except Exception:
            continue

    # 4. Final Master File Processing
    master_rows = []
    for _, row in n500_df.iterrows():
        sym_key = [c for c in row.index if 'symbol' in str(c).lower()]
        comp_key = [c for c in row.index if 'company' in str(c).lower()]
        ind_key = [c for c in row.index if 'industry' in str(c).lower()]
        isin_key = [c for c in row.index if 'isin' in str(c).lower()]

        symbol = str(row[sym_key[0]]).strip().upper() if sym_key else ""
        company_name = str(row[comp_key[0]]).strip() if comp_key else ""
        industry = str(row[ind_key[0]]).strip() if ind_key else "Others"
        isin = str(row[isin_key[0]]).strip() if isin_key else "NA"

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

    print(f"\n🎉 सफलता! NSE डेटा से मास्टर फ़ाइल `{output_path}` तैयार है।", flush=True)
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}", flush=True)
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}", flush=True)

if __name__ == "__main__":
    create_nifty500_master()
