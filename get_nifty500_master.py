import os
import io
import requests
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': '*/*'
}

def fetch_fno_symbols_from_nse_archives():
    """NSE Archives की fo_mktlots.csv फ़ाइल से सीधे F&O स्टॉक्स निकालना"""
    fno_symbols = set()
    
    # NSE official static market lots CSV (No Cookies/Session required, zero timeout)
    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    
    try:
        print("🔄 NSE Archives से F&O Master CSV फ़ाइल डाउनलोड हो रही है...", flush=True)
        res = requests.get(url, headers=HEADERS, timeout=20)
        
        if res.status_code == 200 and len(res.content) > 500:
            lines = res.text.splitlines()
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                # फ़ाइल के शुरुआती कॉलम्स में सिंबल होता है
                for p in parts[:3]:
                    sym = p.upper().replace('"', '').strip()
                    # वैध सिंबल्स को फ़िल्टर करें (हेडर्स और इंडेक्स छोड़कर)
                    if sym and sym.isalnum() and sym not in ['SYMBOL', 'UNDERLYING', 'DERIVATIVES', 'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NAN']:
                        fno_symbols.add(sym)

            if len(fno_symbols) > 50:
                print(f"✅ NSE Archives से सीधे F&O स्टॉक्स मिले: {len(fno_symbols)}", flush=True)
                return fno_symbols
        else:
            print(f"⚠️ NSE Archives Status: {res.status_code}", flush=True)

    except Exception as e:
        print(f"⚠️ NSE Archives डाउनलोड में त्रुटि: {e}", flush=True)

    return fno_symbols

def create_nifty500_master():
    print("🚀 NSE Archives से Nifty 500 और F&O डेटा तैयार किया जा रहा है...", flush=True)
    os.makedirs("data/master", exist_ok=True)

    # 1. Nifty 500 मास्टर लिस्ट
    n500_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = requests.get(n500_url, headers=HEADERS, timeout=15)
        n500_df = pd.read_csv(io.BytesIO(res.content))
        n500_df.columns = n500_df.columns.str.strip()
        print(f"✅ Nifty 500 स्टॉक्स लोड हो गए: {len(n500_df)}", flush=True)
    except Exception as e:
        print(f"❌ Nifty 500 डाउनलोड में समस्या: {e}", flush=True)
        return

    # 2. Direct NSE Archives F&O Fetching
    fno_symbols = fetch_fno_symbols_from_nse_archives()

    # 3. Sub-Indices मैपिंग
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
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                df = pd.read_csv(io.BytesIO(res.content))
                sym_col = [c for c in df.columns if 'symbol' in c.lower()]
                if sym_col:
                    for sym in df[sym_col[0]].astype(str).str.strip().str.upper():
                        index_mapping.setdefault(sym, []).append(idx_name)
        except Exception:
            continue

    # 4. Master CSV डेटाबेस का निर्माण
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
