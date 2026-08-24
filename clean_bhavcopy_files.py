import os
import glob
import pandas as pd

def clean_raw_bhavcopy_files():
    raw_dir = "data/raw"
    fno_file = "data/fno_symbols.txt"

    # F&O Symbols चेक करें
    if not os.path.exists(fno_file):
        print(f"❌ Error: `{fno_file}` नहीं मिली!", flush=True)
        return

    with open(fno_file, 'r', encoding='utf-8') as f:
        fno_symbols = {line.strip().upper() for line in f if line.strip()}

    print(f"🎯 F&O List Loaded: {len(fno_symbols)} symbols.", flush=True)

    files = sorted(glob.glob(os.path.join(raw_dir, "*.csv")))
    if not files:
        print(f"❌ `{raw_dir}` फ़ोल्डर में कोई CSV नहीं मिली!", flush=True)
        return

    print(f"🧹 कुल {len(files)} फ़ाइलों को साफ़ किया जा रहा है...", flush=True)

    for filepath in files:
        fname = os.path.basename(filepath)
        try:
            df = pd.read_csv(filepath)
            original_count = len(df)
            df.columns = df.columns.str.strip().str.upper()

            # Symbol कॉलम ढूँढना
            sym_col = [c for c in df.columns if 'SYMBOL' in c or 'TICKER' in c][0]
            
            if 'SERIES' in df.columns:
                df = df[df['SERIES'].astype(str).str.strip().isin(['EQ', 'BE'])]

            df['SYMBOL_CLEAN'] = df[sym_col].astype(str).str.strip().str.upper()

            # केवल F&O सिंबल्स रखें
            df_filtered = df[df['SYMBOL_CLEAN'].isin(fno_symbols)].drop(columns=['SYMBOL_CLEAN'])

            # फ़ाइल को ओवरराइट (अपडेट) करें
            df_filtered.to_csv(filepath, index=False)
            print(f"✅ {fname}: {original_count} ➔ {len(df_filtered)} rows (Non-F&O removed)")

        except Exception as e:
            print(f"❌ Error cleaning {fname}: {e}")

if __name__ == "__main__":
    clean_raw_bhavcopy_files()
