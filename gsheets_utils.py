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

def sync_dataframe_to_sheet(ws, df: pd.DataFrame, cabecalhos: list[str]):
    ws.clear()
    if df.empty:
        ws.append_row(cabecalhos)
        return
    data = [cabecalhos] + df.astype(str).values.tolist()
    for row in data:
        ws.append_row(row)

def obter_aba(sheet, nome: str):
    try:
        return sheet.worksheet(nome)
    except gspread.exceptions.WorksheetNotFound:
        return None

def get_sheet_names(sheet):
    return [ws.title for ws in sheet.worksheets()]

def append_rows(ws, rows: list[list]):
    for row in rows:
        ws.append_row(row)

def update_cell(ws, row: int, col: int, value):
    ws.update_cell(row, col, str(value))
