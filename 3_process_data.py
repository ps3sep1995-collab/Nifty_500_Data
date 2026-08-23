import os
import glob
import zipfile
import pandas as pd
import numpy as np

def load_all_bhavcopies(bhavcopy_dir):
    """सभी Bhavcopy फ़ाइलों (CSV/ZIP) को लोड करके एक संयुक्त Dataframe बनाना"""
    files = sorted(glob.glob(os.path.join(bhavcopy_dir, "*.csv")) + glob.glob(os.path.join(bhavcopy_dir, "*.zip")))
    
    if not files:
        print(f"❌ `{bhavcopy_dir}` में कोई Bhavcopy फ़ाइल नहीं मिली!", flush=True)
        return None

    print(f"📂 कुल {len(files)} Bhavcopy फ़ाइलें मिलीं। डेटा प्रोसेस हो रहा है...", flush=True)
    all_dfs = []

    for file_path in files:
        try:
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path) as z:
                    csv_name = [f for f in z.namelist() if f.endswith('.csv')][0]
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f)
            else:
                df = pd.read_csv(file_path)

            df.columns = df.columns.str.strip().str.upper()

            # EQ / BE Series फ़िल्टर
            if 'SERIES' in df.columns:
                df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])]

            # Symbol Column
            sym_col = [c for c in df.columns if 'SYMBOL' in c or 'TICKER' in c][0]
            df['SYMBOL'] = df[sym_col].astype(str).str.strip().str.upper()

            # Delivery Qty Identification
            deliv_col = [c for c in df.columns if 'DELIV_QTY' in c or 'DELIVERY' in c or 'DELIVQTY' in c]
            if deliv_col:
                df['DELIV_QTY'] = pd.to_numeric(df[deliv_col[0]], errors='coerce').fillna(0)
            else:
                # अगर Delivery Qty उपलब्ध नहीं है, तो Total Volume का उपयोग करें
                df['DELIV_QTY'] = pd.to_numeric(df.get('TOTTRDQTY', 0), errors='coerce').fillna(0)

            # Essential Columns Standardisation
            df['CLOSE'] = pd.to_numeric(df.get('CLOSE', 0), errors='coerce').fillna(0)
            df['PREVCLOSE'] = pd.to_numeric(df.get('PREVCLOSE', 0), errors='coerce').fillna(0)

            # Date Extraction
            if 'DATE1' in df.columns:
                df['DATE'] = pd.to_datetime(df['DATE1'], errors='coerce')
            elif 'TRADEDATE' in df.columns:
                df['DATE'] = pd.to_datetime(df['TRADEDATE'], errors='coerce')
            else:
                # फ़ाइल के नाम से तिथि निकालें
                df['DATE'] = pd.to_datetime(os.path.basename(file_path)[:10], errors='coerce')

            all_dfs.append(df[['SYMBOL', 'DATE', 'CLOSE', 'PREVCLOSE', 'DELIV_QTY']])
        except Exception as e:
            continue

    if not all_dfs:
        return None

    combined_df = pd.concat(all_dfs, ignore_index=True)
    combined_df = combined_df.sort_values(by=['SYMBOL', 'DATE']).reset_index(drop=True)
    return combined_df

def process_and_scan_stocks():
    master_path = "data/master/nifty500_master.csv"
    bhavcopy_dir = "data/bhavcopy"
    output_path = "data/processed/volume_breakout_scan.csv"

    # 1. Master File Load
    if not os.path.exists(master_path):
        print(f"❌ Master फ़ाइल नहीं मिली: `{master_path}`", flush=True)
        return

    master_df = pd.read_csv(master_path)
    master_df['SYMBOL'] = master_df['SYMBOL'].astype(str).str.strip().str.upper()

    # Rule 1: केवल F&O स्टॉक्स (IS_FNO == 1) फ़िल्टर करें
    fno_master = master_df[master_df['IS_FNO'] == 1].copy()

    # 2. Historical Bhavcopies Load
    bhav_df = load_all_bhavcopies(bhavcopy_dir)
    if bhav_df is None:
        return

    # Master के केवल F&O स्टॉक्स का Bhavcopy डेटा रखें
    bhav_df = bhav_df[bhav_df['SYMBOL'].isin(fno_master['SYMBOL'])]

    # 3. Percentage Change की गणना
    bhav_df['PCT_CHANGE'] = np.where(
        bhav_df['PREVCLOSE'] > 0,
        ((bhav_df['CLOSE'] - bhav_df['PREVCLOSE']) / bhav_df['PREVCLOSE'] * 100).round(2),
        0
    )

    # 4. Moving Averages of Delivery Quantity (2D, 5D, 7D, 10D)
    bhav_df['DELIV_AVG_2D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(2).mean())
    bhav_df['DELIV_AVG_5D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(5).mean())
    bhav_df['DELIV_AVG_7D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(7).mean())
    bhav_df['DELIV_AVG_10D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(10).mean())

    # केवल सबसे ताज़ा ट्रेडिंग डे (Latest Date) का डेटा निकालें
    latest_date = bhav_df['DATE'].max()
    latest_df = bhav_df[bhav_df['DATE'] == latest_date].copy()

    print(f"🗓️ स्कैन की तिथि: {latest_date.strftime('%Y-%m-%d')}", flush=True)

    # 5. Top 5 Gainers & Losers Ranking की गणना (उस दिन के लिए)
    latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=False).reset_index(drop=True)
    latest_df['GAIN_RANK'] = latest_df.index + 1

    latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=True).reset_index(drop=True)
    latest_df['LOSE_RANK'] = latest_df.index + 1

    def assign_rank_status(row):
        if row['GAIN_RANK'] <= 5:
            return f"Top 5 Gainer (Rank #{int(row['GAIN_RANK'])})"
        elif row['LOSE_RANK'] <= 5:
            return f"Top 5 Loser (Rank #{int(row['LOSE_RANK'])})"
        else:
            return "NO"

    latest_df['TOP_5_STATUS'] = latest_df.apply(assign_rank_status, axis=1)

    # 6. Rule 2: 2x Delivery Volume Breakout Check
    def check_volume_breakout(row):
        reasons = []
        deliv = row['DELIV_QTY']
        
        if row['DELIV_AVG_2D'] > 0 and deliv >= 2 * row['DELIV_AVG_2D']:
            reasons.append("2D_AVG")
        if row['DELIV_AVG_5D'] > 0 and deliv >= 2 * row['DELIV_AVG_5D']:
            reasons.append("5D_AVG")
        if row['DELIV_AVG_7D'] > 0 and deliv >= 2 * row['DELIV_AVG_7D']:
            reasons.append("7D_AVG")
        if row['DELIV_AVG_10D'] > 0 and deliv >= 2 * row['DELIV_AVG_10D']:
            reasons.append("10D_AVG")

        return ", ".join(reasons) if reasons else "NO"

    latest_df['BREAKOUT_SIGNAL'] = latest_df.apply(check_volume_breakout, axis=1)

    # केवल Breakout वाले स्टॉक्स फ़िल्टर करें
    scan_results = latest_df[latest_df['BREAKOUT_SIGNAL'] != "NO"].copy()

    # 7. Master File (Sector & Indices Info) के साथ Merge करें
    final_df = pd.merge(scan_results, fno_master[['SYMBOL', 'COMPANY_NAME', 'SECTOR', 'INDICES', 'IS_FNO']], on='SYMBOL', how='left')

    # Final Table Columns Rearrange
    output_cols = [
        'SYMBOL', 'COMPANY_NAME', 'SECTOR', 'INDICES', 'IS_FNO',
        'CLOSE', 'PCT_CHANGE', 'DELIV_QTY', 
        'DELIV_AVG_2D', 'DELIV_AVG_5D', 'DELIV_AVG_7D', 'DELIV_AVG_10D',
        'BREAKOUT_SIGNAL', 'TOP_5_STATUS'
    ]
    
    final_df = final_df[output_cols]

    # File Output Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! स्कैनर रिजल्ट तैयार है: `{output_path}`", flush=True)
    print(f"📊 कुल F&O Breakout स्टॉक्स मिले: {len(final_df)}", flush=True)

if __name__ == "__main__":
    process_and_scan_stocks()
