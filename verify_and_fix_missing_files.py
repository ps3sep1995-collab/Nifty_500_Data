import os
import requests
import pandas as pd
from datetime import datetime, timedelta
# download function import or integrate here

def verify_and_download_missing():
    print("🔍 मिसिंग फ़ाइलों की जाँच की जा रही है...")
    start_date = datetime(2005, 1, 1)
    today = datetime.now()
    
    missing_dates = []
    current_date = start_date
    
    while current_date <= today:
        date_str = current_date.strftime('%Y-%m-%d')
        file_path = f"data/raw/bhav_{date_str}.csv"
        
        # वीकेंड नहीं है और फ़ाइल गायब है
        if current_date.weekday() < 5 and not os.path.exists(file_path):
            missing_dates.append(current_date)
            
        current_date += timedelta(days=1)
        
    print(f"🚨 कुल मिसिंग संभावित ट्रेडिंग दिन: {len(missing_dates)}")
    
    # अब सिर्फ मिसिंग तारीखों को दोबारा डाउनलोड करें
    for m_date in missing_dates:
        print(f"🔄 Re-downloading: {m_date.strftime('%Y-%m-%d')}")
        # Call download logic here...

if __name__ == "__main__":
    verify_and_download_missing()
