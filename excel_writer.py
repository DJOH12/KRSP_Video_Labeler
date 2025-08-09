from datetime import datetime, timezone
def build_row(schema_columns, form_values: dict):
    row = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for col in schema_columns:
        if col == "timestamp_utc":
            row.append(now_iso)
        else:
            row.append(form_values.get(col, ""))
    return row
