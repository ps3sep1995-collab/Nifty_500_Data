import os
import io
import requests
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': '*/*'
}

def load_fno_symbols_from_local():
    """लोकल अपलोड की गई फ़ाइल से F&O सिंबल्स लोड करना"""
    fno_symbols = set()
    local_path = "data/fno_symbols.txt"
    
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            content = f.read()
            tokens = content.replace(',', '\n').splitlines()
            for token in tokens:
                sym = token.strip().upper()
                if sym and sym.isalnum():
                    fno_symbols.add(sym)
        print(f"✅ लोकल फ़ाइल `{local_path}` से {len(fno_symbols)} F&O स्टॉक्स लोड हुए!", flush=True)
    else:
        print(f"⚠️ चेतावनी: `{local_path}` फ़ाइल नहीं मिली।", flush=True)
        
    return fno_symbols

def create_nifty500_master():
    print("🚀 Nifty 500 मास्टर लिस्ट और सेक्टर्स मैपिंग शुरू की जा रही है...", flush=True)
    os.makedirs("data/master", exist_ok=True)

    # 1. Nifty 500 मास्टर लिस्ट (इसमें IT, Pharma, Realty सभी सेक्टर्स का नाम पहले से ही 'Industry' कॉलम में होता है)
    n500_url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        res = requests.get(n500_url, headers=HEADERS, timeout=15)
        n500_df = pd.read_csv(io.BytesIO(res.content))
        n500_df.columns = n500_df.columns.str.strip()
        print(f"✅ Nifty 500 स्टॉक्स लोड हो गए: {len(n500_df)}", flush=True)
    except Exception as e:
        print(f"❌ Nifty 500 डाउनलोड में समस्या: {e}", flush=True)
        return

    # 2. F&O स्टॉक्स लोड करें
    fno_symbols = load_fno_symbols_from_local()

    # 3. सभी सेक्टोरल और ब्रॉड इंडेक्स मैपिंग (IT, Pharma, Realty, Media, Bank आदि)
    indices_config = {
        'NIFTY 50': "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
        'NIFTY BANK': "https://archives.nseindia.com/content/indices/ind_niftybanklist.csv",
        'NIFTY NEXT 50': "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
        'NIFTY MIDCAP 100': "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
        'NIFTY SMALLCAP 100': "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
        'NIFTY IT': "https://archives.nseindia.com/content/indices/ind_niftyitlist.csv",
        'NIFTY PHARMA': "https://archives.nseindia.com/content/indices/ind_niftypharmalist.csv",
        'NIFTY REALTY': "https://archives.nseindia.com/content/indices/ind_niftyrealtylist.csv",
        'NIFTY MEDIA': "https://archives.nseindia.com/content/indices/ind_niftymedialist.csv",
        'NIFTY AUTO': "https://archives.nseindia.com/content/indices/ind_niftyautolist.csv",
        'NIFTY FMCG': "https://archives.nseindia.com/content/indices/ind_niftyfmcglist.csv",
        'NIFTY METAL': "https://archives.nseindia.com/content/indices/ind_niftymetallist.csv",
        'NIFTY ENERGY': "https://archives.nseindia.com/content/indices/ind_niftyenergylist.csv"
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

    # 4. Master CSV का निर्माण
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

        # इंडेक्स लिस्ट मैप करें
        matched_indices = index_mapping.get(symbol, [])
        if "NIFTY 500" not in matched_indices:
            matched_indices.append("NIFTY 500")

        indices_str = ", ".join(matched_indices)

        master_rows.append({
            'SYMBOL': symbol,
            'COMPANY_NAME': company_name,
            'ISIN': isin,
            'SECTOR': industry,          # उदाहरण: Information Technology, Pharmaceuticals, Realty आदि।
            'INDICES': indices_str,       # उदाहरण: NIFTY 500, NIFTY IT
            'IS_FNO': is_fno
        })

    master_df = pd.DataFrame(master_rows)
    output_path = "data/master/nifty500_master.csv"
    master_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! मास्टर फ़ाइल `{output_path}` में तैयार है।", flush=True)
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}", flush=True)
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}", flush=True)

if __name__ == "__main__":
    create_nifty500_master()
