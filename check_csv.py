import pandas as pd

df = pd.read_csv("family_data.csv", sep=";", encoding="cp1252", dtype=str)
print(f"Total columns: {len(df.columns)}")
print("Column indices and names:")
for i, col in enumerate(df.columns):
    print(f"  {i}: {repr(col)}")

print(f"\nFirst row:\n{df.iloc[0]}")
