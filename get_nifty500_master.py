
import os
import requests
import pandas as pd

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

def create_nifty500_master():
    print("🚀 Nifty 500 लिस्ट, F&O फ्लैग, सेक्टर्स और इंडेक्स डेटा तैयार किया जा रहा है...")
    os.makedirs("data", exist_ok=True)
    
    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Nifty 500 की आधिकारिक लिस्ट डाउनलोड करें
    nifty500_url = "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv"
    try:
        n500_df = pd.read_csv(nifty500_url)
        n500_df.columns = n500_df.columns.str.strip()
        print(f"✅ Nifty 500 स्टॉक्स लोड हो गए! कुल स्टॉक्स: {len(n500_df)}")
    except Exception as e:
        print(f"❌ Nifty 500 लिस्ट डाउनलोड करने में त्रुटि: {e}")
        return

    # 2. F&O Derivatives List डाउनलोड करें (F&O फ्लैग सेट करने के लिए)
    fno_url = "https://niftyindices.com/IndexConstituent/ind_niftyderivativeslist.csv"
    fno_symbols = set()
    try:
        fno_df = pd.read_csv(fno_url)
        fno_df.columns = fno_df.columns.str.strip()
        fno_symbols = set(fno_df['Symbol'].str.strip().str.upper().unique())
        print(f"✅ F&O स्टॉक्स की लिस्ट मिली: {len(fno_symbols)} स्टॉक्स")
    except Exception as e:
        print(f"⚠️ F&O लिस्ट प्राप्त करने में त्रुटि: {e}")

    # 3. मुख्य सूचकांक (Indices) डाउनलोड करें ताकि इंडेक्स मैपिंग हो सके
    indices_urls = {
        'NIFTY 50': 'https://niftyindices.com/IndexConstituent/ind_nifty50list.csv',
        'NIFTY BANK': 'https://niftyindices.com/IndexConstituent/ind_niftybanklist.csv',
        'NIFTY NEXT 50': 'https://niftyindices.com/IndexConstituent/ind_niftynext50list.csv',
        'NIFTY MIDCAP 100': 'https://niftyindices.com/IndexConstituent/ind_niftymidcap100list.csv',
        'NIFTY SMALLCAP 100': 'https://niftyindices.com/IndexConstituent/ind_niftysmallcap100list.csv',
        'NIFTY FIN SERVICE': 'https://niftyindices.com/IndexConstituent/ind_niftyfinancialserviceslist.csv'
    }

    index_mapping = {}
    for idx_name, url in indices_urls.items():
        try:
            df = pd.read_csv(url)
            df.columns = df.columns.str.strip()
            for sym in df['Symbol'].str.strip().str.upper():
                index_mapping.setdefault(sym, []).append(idx_name)
        except Exception:
            pass

    # 4. Nifty 500 मास्टर डेटाबेस बनाएं
    master_rows = []

    for _, row in n500_df.iterrows():
        symbol = str(row.get('Symbol', '')).strip().upper()
        company_name = str(row.get('Company Name', '')).strip()
        industry = str(row.get('Industry', 'Others')).strip()
        isin = str(row.get('ISIN Code', 'NA')).strip()

        if not symbol or symbol == 'NAN':
            continue

        # F&O Flag (1 अगर F&O में है, वर्ना 0)
        is_fno = 1 if symbol in fno_symbols else 0

        # Sub-Indices Map
        matched_indices = index_mapping.get(symbol, [])
        if not matched_indices:
            matched_indices.append("NIFTY 500")
        else:
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
    output_path = "data/nifty500_master.csv"
    master_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! Nifty 500 की मास्टर फ़ाइल `{output_path}` में सेव हो गई है।")
    print(f"📊 कुल रिकॉर्ड्स: {len(master_df)}")
    print(f"🔥 इनमें से F&O स्टॉक्स: {master_df['IS_FNO'].sum()}")
    print("\n--- SAMPLE DATA ---")
    print(master_df[['SYMBOL', 'SECTOR', 'INDICES', 'IS_FNO']].head(10))

if __name__ == "__main__":
    create_nifty500_master()
