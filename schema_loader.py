import pandas as pd
from pathlib import Path

def _parse_features_table(df: pd.DataFrame):
    choices = {}
    if df.shape[1] < 2:
        return choices
    col_field = 1  # Column B
    col_value = 2 if df.shape[1] > 2 else None  # Column C
    current_field = None
    for _, row in df.iterrows():
        field = str(row.iloc[col_field]).strip() if pd.notna(row.iloc[col_field]) else ""
        value = str(row.iloc[col_value]).strip() if (col_value is not None and pd.notna(row.iloc[col_value])) else ""
        if field and field.lower() not in ("nan",):
            current_field = field
            if current_field not in choices:
                choices[current_field] = []
            if value:
                choices[current_field].append(value)
        else:
            if current_field and value:
                choices[current_field].append(value)
    # de-dup and clean
    for k, vals in list(choices.items()):
        clean, seen = [], set()
        for v in vals:
            if not v or v.lower() == "nan":
                continue
            if v not in seen:
                seen.add(v)
                clean.append(v)
        choices[k] = clean
    return choices

def load_schema_from_excels(features_path: str, example_path: str):
    schema = {"columns": [], "choices": {}}
    ex_fp = Path(example_path)
    if ex_fp.exists():
        ex = pd.read_excel(ex_fp, sheet_name=0)
        # Normalize column names on the DataFrame FIRST
        # - drop Video_Name if present
        # - rename 'Video ID' -> 'video_id'
        # - ensure 'video_id' exists
        cols_lower = [str(c).strip().lower() for c in ex.columns]
        drop_names = [ex.columns[i] for i,cl in enumerate(cols_lower) if cl == "video_name"]
        if drop_names:
            ex = ex.drop(columns=drop_names, errors="ignore")
        rename_map = {}
        for i,c in enumerate(ex.columns):
            if str(c).strip() == "Video ID":
                rename_map[c] = "video_id"
        if rename_map:
            ex = ex.rename(columns=rename_map)
        # Build column order with video_id first if present
        columns = list(ex.columns)
        if "video_id" not in columns:
            # If missing entirely, inject it
            columns = ["video_id"] + columns
        else:
            columns = ["video_id"] + [c for c in columns if c != "video_id"]
        schema["columns"] = columns
        # Fallback choices from example values (use the normalized DF)
        for col in [c for c in ex.columns if c != "video_id"]:
            vals = [v for v in ex[col].dropna().astype(str).unique() if v != ""]
            if vals:
                schema["choices"].setdefault(col, vals)
    else:
        schema["columns"] = ["video_id", "timestamp_utc", "rater_id", "notes"]
    feat_fp = Path(features_path)
    if feat_fp.exists():
        feat = pd.read_excel(feat_fp, sheet_name=0, header=None)
        parsed = _parse_features_table(feat)
        for field, vals in parsed.items():
            if str(field).strip().lower() in ("video_name",):
                continue
            schema["choices"][field] = vals
    # Ensure every column has an entry in choices (even if empty)
    for col in schema["columns"]:
        schema["choices"].setdefault(col, [])
    return schema
