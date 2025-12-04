import pandas as pd
import sys

print("Python version:", sys.version)
print()

# Read the CSV file
df = pd.read_csv('family_data.csv', encoding='utf-8-sig')

print("Raw columns before cleaning:")
for i, col in enumerate(df.columns):
    print(f"  {i}: {repr(col)}")

print("\n" + "="*60)

# Get the actual column names by removing the § symbol
df.columns = df.columns.str.replace('§', '').str.strip()

print("\nColumns after cleaning:")
for i, col in enumerate(df.columns):
    print(f"  {i}: {repr(col)}")

print("\n" + "="*60)
print("\nFirst row:")
print(df.iloc[0])
