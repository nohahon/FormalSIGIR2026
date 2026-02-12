import pandas as pd

df = pd.read_csv("output4.csv")  

# Extract the first digit (1–5) that appears right after {"Alignment Score": "
scores = df["comparison_json"].astype(str).str.extract(r'\{"Alignment Score":\s*"([1-5])')[0]

counts = (
    scores.astype("Int64")
          .value_counts(dropna=False)
          .reindex([1,2,3,4,5], fill_value=0)
)

print({
    "1s": int(counts.loc[1]),
    "2s": int(counts.loc[2]),
    "3s": int(counts.loc[3]),
    "4s": int(counts.loc[4]),
    "5s": int(counts.loc[5]),
})
