import pandas as pd

# Try different separators and encodings
try:
    df = pd.read_csv('family_data.csv', sep='§', encoding='utf-8')
    print("Columns with sep='§':")
    print(list(df.columns))
    print("\nFirst few column names repr:")
    for col in df.columns[:5]:
        print(f"  {repr(col)}")
except Exception as e:
    print(f"Error with §: {e}")

try:
    df = pd.read_csv('family_data.csv', sep=';', encoding='utf-8')
    print("\n\nColumns with sep=';':")
    print(list(df.columns))
    print("\nFirst few column names repr:")
    for col in df.columns[:5]:
        print(f"  {repr(col)}")
except Exception as e:
    print(f"Error with ;: {e}")
