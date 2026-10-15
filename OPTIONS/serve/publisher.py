import json
import polars as pl

def format_publish_payload(df_decisions: pl.DataFrame) -> list:
    """
    Simulates publishing by returning a list of dictionaries.
    """
    if df_decisions.is_empty():
        return []
    
    return df_decisions.to_dicts()
