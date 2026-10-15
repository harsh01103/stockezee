import polars as pl
import math

df = pl.DataFrame({
    "composite_alpha_score": [50.0, float('nan'), None, 90.0]
})

df = df.with_columns(
    (0.60 + (pl.col("composite_alpha_score") / 100.0) * 0.15).clip(0.60, 0.75).alias("confidence")
)

print("DF with confidence:")
print(df.to_dicts())

df_pub = df.filter(pl.col("confidence") >= 0.70)
print("\nDF after filter >= 0.70:")
print(df_pub.to_dicts())

for row in df_pub.iter_rows(named=True):
    print("Row:", row)
    conf = row.get("confidence")
    print("Conf value:", conf, type(conf))
