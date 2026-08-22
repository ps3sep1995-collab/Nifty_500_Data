import os
import json
import time
import requests
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/market-data/live-equity-market'
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        # NSE होमपेज से सेशन कुकीज़ प्राप्त करें
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
        # लाइव इक्विटी मार्केट पेज से कुकीज़ रिफ्रेश करें
        session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=15)
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ NSE कुकी वार्निंग: {e}", flush=True)
    return session

def fetch_fno_symbols_from_nse_live():
    """NSE Live Equity Market API से Sec_FO / F&O स्टॉक्स प्राप्त करना"""
    fno_symbols = set()
    session = get_nse_session()
    
    # NSE Live Equity Market API URL (Securities in F&O)
    live_fno_url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
    
    try:
        print("🔄 NSE Live Market API से F&O स्टॉक्स खींचे जा रहे हैं...", flush=True)
        res = session.get(live_fno_url, timeout=20)
        
        if res.status_code == 200:
            data = res.json()
            if 'data' in data:
                for item in data['data']:
                    symbol = str(item.get('symbol', '')).strip().upper()
                    if symbol and symbol != 'NAN':
                        fno_symbols.add(symbol)
                        
            if len(fno_symbols) > 50:
                print(f"✅ NSE Live API से सीधे F&O स्टॉक्स मिले: {len(fno_symbols)}", flush=True)
                return fno_symbols
        else:
            print(f"⚠️ NSE Live API Status Code: {res.status_code}", flush=True)
            
    except Exception as e:
        print(f"⚠️ NSE Live API त्रुटि: {e}", flush=True)

    return fno_symbols

def create_nifty500_master():
    print("🚀 NSE Live Market से Master List तैयार की जा रही है...", flush=True)
    os.makedirs("data/master", exist_ok=True)

    # 1. Nifty 500 मास्टर लिस्ट (Archives)
    n500_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = requests.get(n500_url, headers=HEADERS, timeout=15)
        n500_df = pd.read_csv(pd.io.common.BytesIO(res.content))
        n500_df.columns = n500_df.columns.str.strip()
        print(f"✅ Nifty 500 स्टॉक्स लोड हो गए: {len(n500_df)}", flush=True)
    except Exception as e:
        print(f"❌ Nifty 500 डाउनलोड में समस्या: {e}", flush=True)
        return

    # 2. Live API से F&O स्टॉक्स निकालें
    fno_symbols = fetch_fno_symbols_from_nse_live()

    # 3. Master CSV डेटाबेस बनाएं
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

        master_rows.append({
            'SYMBOL': symbol,
            'COMPANY_NAME': company_name,
            'ISIN': isin,
            'SECTOR': industry,
            'INDICES': 'NIFTY 500',
            'IS_FNO': is_fno
        })

    master_df = pd.DataFrame(master_rows)
    output_path = "data/master/nifty500_master.csv"
    master_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! मास्टर फ़ाइल `{output_path}` तैयार है।", flush=True)
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}", flush=True)
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}", flush=True)

if __name__ == "__main__":
    create_nifty500_master()
