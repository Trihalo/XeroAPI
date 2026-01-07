import pandas as pd
import datetime

try:
    df = pd.read_excel("./PO.xlsx")
    print("Types in PO column:")
    print(df['PO'].apply(type).value_counts())
    
    print("\nSample values:")
    print(df['PO'].head(10))

    # check for datetime
    datetimes = df[df['PO'].apply(lambda x: isinstance(x, (datetime.datetime, datetime.date)))]
    if not datetimes.empty:
        print("\nFound datetimes in PO column:")
        print(datetimes['PO'])
except Exception as e:
    print(f"Error reading excel: {e}")
