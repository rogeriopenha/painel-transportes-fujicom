import json
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

SHEET_PREFIXES = {
    "Braspress": "BR-",
    "Gbex": "GB-",
    "DHL": "DH-",
}

def conectar(creds_dict: dict | str | bytes):
    if isinstance(creds_dict, bytes):
        creds_dict = creds_dict.decode("utf-8")
    if isinstance(creds_dict, str):
        creds_dict = json.loads(creds_dict)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    return client

def abrir_planilha(creds_dict, sheet_url: str):
    client = conectar(creds_dict)
    return client.open_by_url(sheet_url)

def df_from_ws(ws):
    raw = ws.get_all_values()
    if not raw:
        return pd.DataFrame()
    return pd.DataFrame(raw[1:], columns=raw[0])

def criar_aba(sheet, nome: str, cabecalhos: list[str] | None = None):
    try:
        ws = sheet.worksheet(nome)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=nome, rows=100, cols=len(cabecalhos) if cabecalhos else 10)
        if cabecalhos:
            ws.append_row(cabecalhos)
        return ws

def sync_dataframe_to_sheet(ws, df: pd.DataFrame, cabecalhos: list[str], merge_key: str = None):
    if merge_key and merge_key in df.columns and not df.empty:
        raw = ws.get_all_values()
        if raw and len(raw) > 1:
            df_existing = pd.DataFrame(raw[1:], columns=raw[0])
        else:
            df_existing = pd.DataFrame(columns=cabecalhos)

        df[merge_key] = df[merge_key].astype(str)
        df_existing[merge_key] = df_existing[merge_key].astype(str)
        existing_keys = set(df_existing[merge_key].tolist())
        df_new_only = df[~df[merge_key].isin(existing_keys)]
        df_updated = df[df[merge_key].isin(existing_keys)]
        df_preserved = df_existing[~df_existing[merge_key].isin(df_updated[merge_key])]
        df_merged = pd.concat([df_preserved, df_updated, df_new_only], ignore_index=True)
    else:
        df_merged = df

    ws.clear()
    if df_merged.empty:
        ws.append_row(cabecalhos)
        return
    data = [cabecalhos] + df_merged.astype(str).values.tolist()
    for i in range(0, len(data), 100):
        ws.append_rows(data[i:i+100])

def obter_aba(sheet, nome: str):
    try:
        return sheet.worksheet(nome)
    except gspread.exceptions.WorksheetNotFound:
        return None

def get_sheet_names(sheet):
    return [ws.title for ws in sheet.worksheets()]

def append_rows(ws, rows: list[list]):
    for i in range(0, len(rows), 100):
        ws.append_rows(rows[i:i+100])

def update_cell(ws, row: int, col: int, value):
    ws.update_cell(row, col, str(value))
