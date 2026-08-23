import os
import glob
import pandas as pd
import numpy as np

def load_all_raw_bhavcopies(raw_dir):
    """data/raw/ फोल्डर से सभी CSV फाइलों को लोड करना"""
    files = sorted(glob.glob(os.path.join(raw_dir, "*.csv")))
    
    if not files:
        print(f"❌ `{raw_dir}` में कोई Bhavcopy फाइल नहीं मिली!", flush=True)
        return None

    print(f"📂 कुल {len(files)} Historical Bhavcopies मिलीं। प्रोसेसिंग जारी है...", flush=True)
    all_dfs = []

    for file_path in files:
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip().str.upper()

            # 1. Equity Series Filtering
            if 'SERIES' in df.columns:
                df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])]

            # 2. Symbol Identification
            sym_col = [c for c in df.columns if 'SYMBOL' in c or 'TICKER' in c][0]
            df['SYMBOL'] = df[sym_col].astype(str).str.strip().str.upper()

            # 3. Delivery Quantity / Total Volume
            deliv_col = [c for c in df.columns if 'DELIV_QTY' in c or 'DELIVERY' in c or 'DELIVQTY' in c]
            if deliv_col:
                df['DELIV_QTY'] = pd.to_numeric(df[deliv_col[0]], errors='coerce').fillna(0)
            else:
                df['DELIV_QTY'] = pd.to_numeric(df.get('TOTTRDQTY', 0), errors='coerce').fillna(0)

            # 4. Price Cleaning
            df['CLOSE'] = pd.to_numeric(df.get('CLOSE', 0), errors='coerce').fillna(0)
            df['PREVCLOSE'] = pd.to_numeric(df.get('PREVCLOSE', 0), errors='coerce').fillna(0)

            # 5. Extract Date from Filename (e.g. bhav_2005-01-03.csv)
            base_name = os.path.basename(file_path)
            date_part = base_name.replace('bhav_', '').replace('.csv', '')
            df['DATE'] = pd.to_datetime(date_part, errors='coerce')

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
    raw_dir = "data/raw"
    output_path = "data/processed/volume_breakout_scan.csv"

    # Master File Load
    if not os.path.exists(master_path):
        print(f"❌ Master फ़ाइल नहीं मिली: `{master_path}`", flush=True)
        return

    master_df = pd.read_csv(master_path)
    master_df['SYMBOL'] = master_df['SYMBOL'].astype(str).str.strip().str.upper()

    # Rule 1: Filter F&O Stocks Only
    fno_master = master_df[master_df['IS_FNO'] == 1].copy()

    # Raw Bhavcopies Load
    bhav_df = load_all_raw_bhavcopies(raw_dir)
    if bhav_df is None:
        return

    # Keep F&O Stocks Only
    bhav_df = bhav_df[bhav_df['SYMBOL'].isin(fno_master['SYMBOL'])]

    # Calculate Daily Percentage Change
    bhav_df['PCT_CHANGE'] = np.where(
        bhav_df['PREVCLOSE'] > 0,
        ((bhav_df['CLOSE'] - bhav_df['PREVCLOSE']) / bhav_df['PREVCLOSE'] * 100).round(2),
        0
    )

    # Calculate Rolling Averages for Delivery Quantity (2D, 5D, 7D, 10D)
    bhav_df['DELIV_AVG_2D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(2).mean())
    bhav_df['DELIV_AVG_5D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(5).mean())
    bhav_df['DELIV_AVG_7D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(7).mean())
    bhav_df['DELIV_AVG_10D'] = bhav_df.groupby('SYMBOL')['DELIV_QTY'].transform(lambda x: x.shift(1).rolling(10).mean())

    # Get Latest Trading Date Data
    latest_date = bhav_df['DATE'].max()
    latest_df = bhav_df[bhav_df['DATE'] == latest_date].copy()

    print(f"🗓️ स्कैनिंग की तिथि: {latest_date.strftime('%Y-%m-%d')}", flush=True)

    # Top 5 Gainers & Losers Ranking (F&O Universe)
    latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=False).reset_index(drop=True)
    latest_df['GAIN_RANK'] = latest_df.index + 1

    latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=True).reset_index(drop=True)
    latest_df['LOSE_RANK'] = latest_df.index + 1

    def assign_rank(row):
        if row['GAIN_RANK'] <= 5:
            return f"Top 5 Gainer (Rank #{int(row['GAIN_RANK'])})"
        elif row['LOSE_RANK'] <= 5:
            return f"Top 5 Loser (Rank #{int(row['LOSE_RANK'])})"
        else:
            return "NO"

    latest_df['TOP_5_STATUS'] = latest_df.apply(assign_rank, axis=1)

    # Rule 2: 2x Delivery Volume Breakout Check
    def check_breakout(row):
        signals = []
        d = row['DELIV_QTY']
        if row['DELIV_AVG_2D'] > 0 and d >= 2 * row['DELIV_AVG_2D']: signals.append("2D")
        if row['DELIV_AVG_5D'] > 0 and d >= 2 * row['DELIV_AVG_5D']: signals.append("5D")
        if row['DELIV_AVG_7D'] > 0 and d >= 2 * row['DELIV_AVG_7D']: signals.append("7D")
        if row['DELIV_AVG_10D'] > 0 and d >= 2 * row['DELIV_AVG_10D']: signals.append("10D")
        return ", ".join(signals) if signals else "NO"

    latest_df['BREAKOUT_SIGNAL'] = latest_df.apply(check_breakout, axis=1)

    # Filter Stocks with Breakouts
    scan_results = latest_df[latest_df['BREAKOUT_SIGNAL'] != "NO"].copy()

    # Merge Sector & Index Info from Master
    final_df = pd.merge(scan_results, fno_master[['SYMBOL', 'COMPANY_NAME', 'SECTOR', 'INDICES', 'IS_FNO']], on='SYMBOL', how='left')

    output_cols = [
        'SYMBOL', 'COMPANY_NAME', 'SECTOR', 'INDICES', 'IS_FNO',
        'CLOSE', 'PCT_CHANGE', 'DELIV_QTY', 
        'DELIV_AVG_2D', 'DELIV_AVG_5D', 'DELIV_AVG_7D', 'DELIV_AVG_10D',
        'BREAKOUT_SIGNAL', 'TOP_5_STATUS'
    ]
    
    final_df = final_df[output_cols]

    # Save Output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_df.to_csv(output_path, index=False)

    print(f"\n🎉 सफलता! स्कैनर फाइल यहाँ तैयार है: `{output_path}`", flush=True)
    print(f"📊 कुल F&O Breakout स्टॉक्स मिले: {len(final_df)}", flush=True)

if __name__ == "__main__":
    process_and_scan_stocks()
