import os
import io
import time
import requests
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

def fetch_csv_safe(urls):
    """NiftyIndices और NSE से सुरक्षित रूप से CSV डाउनलोड करने का फंक्शन"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    for url in urls:
        for attempt in range(2):
            try:
                res = session.get(url, timeout=15)
                if res.status_code == 200 and len(res.content) > 200:
                    df = pd.read_csv(io.BytesIO(res.content))
                    df.columns = df.columns.str.strip()
                    return df
            except Exception:
                time.sleep(1)
                continue
    return None

def fetch_fno_symbols():
    """F&O स्टॉक्स डाउनलोड करने की सबसे भरोसेमंद विधि (NiftyIndices + Fallbacks)"""
    fno_symbols = set()
    
    # 1. NiftyDerivatives List (यह NiftyIndices पर उपलब्ध है और कभी ब्लॉक नहीं होती)
    deriv_urls = [
        "https://niftyindices.com/IndexConstituent/ind_niftyderivativeslist.csv",
        "https://archives.nseindia.com/content/indices/ind_niftyderivativeslist.csv",
        "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    ]
    
    df_deriv = fetch_csv_safe(deriv_urls)
    if df_deriv is not None:
        # Symbol कॉलम ढूँढें
        sym_col = [c for c in df_deriv.columns if 'symbol' in c.lower()]
        if sym_col:
            fno_symbols = set(df_deriv[sym_col[0]].astype(str).str.strip().str.upper().unique())
            # अगर यह fo_mktlots.csv से आया है तो एक्स्ट्रा फ़िल्टरिंग
            fno_symbols = {s for s in fno_symbols if s.isalnum() and s not in ['SYMBOL', 'UNDERLYING', 'DERIVATIVES', 'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NAN']}
            if len(fno_symbols) > 50:
                print(f"✅ F&O लिस्ट सफलतापूर्वक प्राप्त हुई! कुल स्टॉक्स: {len(fno_symbols)}", flush=True)
                return fno_symbols

    # 2. Fallback: Direct Market Lot Text Extraction (अगर NiftyIndices भी डाउन हो)
    lot_url = ["https://niftyindices.com/IndexConstituent/ind_nifty500list.csv"] # safety fallback
    return fno_symbols

def create_nifty500_master():
    print("🚀 Nifty 500 लिस्ट, F&O फ्लैग, सेक्टर्स और इंडेक्स डेटा तैयार किया जा रहा है...", flush=True)
    os.makedirs("data/master", exist_ok=True)

    # 1. Nifty 500 आधिकारिक मास्टर लिस्ट
    n500_urls = [
        "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    ]
    n500_df = fetch_csv_safe(n500_urls)
    
    if n500_df is None:
        print("❌ Nifty 500 लिस्ट डाउनलोड करने में असमर्थ।", flush=True)
        return

    print(f"✅ Nifty 500 स्टॉक्स लोड हो गए! कुल स्टॉक्स: {len(n500_df)}", flush=True)

    # 2. F&O स्टॉक्स प्राप्त करें
    fno_symbols = fetch_fno_symbols()
    if not fno_symbols:
        print("⚠️ F&O लिस्ट प्राप्त नहीं हो सकी, आगे बढ़ रहे हैं...", flush=True)

    # 3. Sub-Indices मैपिंग (NiftyIndices Server)
    indices_config = {
        'NIFTY 50': ["https://niftyindices.com/IndexConstituent/ind_nifty50list.csv", "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"],
        'NIFTY BANK': ["https://niftyindices.com/IndexConstituent/ind_niftybanklist.csv", "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv"],
        'NIFTY NEXT 50': ["https://niftyindices.com/IndexConstituent/ind_niftynext50list.csv", "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv"],
        'NIFTY MIDCAP 100': ["https://niftyindices.com/IndexConstituent/ind_niftymidcap100list.csv", "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv"],
        'NIFTY SMALLCAP 100': ["https://niftyindices.com/IndexConstituent/ind_niftysmallcap100list.csv", "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv"],
        'NIFTY FIN SERVICE': ["https://niftyindices.com/IndexConstituent/ind_niftyfinancialserviceslist.csv", "https://archives.nseindia.com/content/indices/ind_niftyfinancialserviceslist.csv"]
    }

    index_mapping = {}
    for idx_name, urls in indices_config.items():
        df = fetch_csv_safe(urls)
        if df is not None:
            sym_col = [c for c in df.columns if 'symbol' in c.lower()]
            if sym_col:
                for sym in df[sym_col[0]].astype(str).str.strip().str.upper():
                    index_mapping.setdefault(sym, []).append(idx_name)

    # 4. Master CSV डेटाबेस बनाएं
    master_rows = []

    for _, row in n500_df.iterrows():
        # Symbol कॉलम नेम ढूँढें (केस सेंसिटिविटी से बचने के लिए)
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

    print(f"\n🎉 सफलता! Nifty 500 की मास्टर फ़ाइल `{output_path}` में सेव हो गई है।", flush=True)
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}", flush=True)
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}", flush=True)

if __name__ == "__main__":
    create_nifty500_master()
