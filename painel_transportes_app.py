import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import io
import os
import base64
from PIL import Image

PERIOD_OPTIONS = ["Última semana", "Últimos 30 dias", "Mês fechado", "Todo período"]
PT_MONTH_MAP = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
    "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"
}
PT_MONTH_REVERSE = {v: k for k, v in PT_MONTH_MAP.items()}

def _get_available_months(*date_series_list):
    all_dates = pd.concat(date_series_list, ignore_index=True) if date_series_list else pd.Series()
    dt = pd.to_datetime(all_dates, errors="coerce", dayfirst=True).dropna()
    if dt.empty:
        now = datetime.now()
        return [f"{PT_MONTH_REVERSE.get(str(now.month).zfill(2), '')}-{now.year}"]
    months = sorted(dt.dt.to_period("M").unique(), reverse=True)
    result = []
    for m in months:
        mon_str = str(m.month).zfill(2)
        pt_name = PT_MONTH_REVERSE.get(mon_str, mon_str)
        result.append(f"{pt_name}-{m.year}")
    return result

def _apply_period_filter(df, period_option, date_col, mes_fechado_option=None):
    if period_option == "Todo período" or not date_col or date_col not in df.columns:
        return df
    df = df.copy()
    df["_pf_dt"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    if period_option == "Última semana":
        cutoff = datetime.now() - timedelta(days=7)
        df = df[df["_pf_dt"] >= cutoff]
    elif period_option == "Últimos 30 dias":
        cutoff = datetime.now() - timedelta(days=30)
        df = df[df["_pf_dt"] >= cutoff]
    elif period_option == "Mês fechado" and mes_fechado_option:
        parts = mes_fechado_option.split("-")
        if len(parts) == 2:
            pt_mon, yr = parts[0], parts[1]
            mon_num = PT_MONTH_MAP.get(pt_mon, "01")
            target_start = pd.Timestamp(f"{yr}-{mon_num}-01")
            target_end = target_start + relativedelta(months=1)
            df = df[(df["_pf_dt"] >= target_start) & (df["_pf_dt"] < target_end)]
    df = df.drop(columns=["_pf_dt"], errors="ignore")
    return df

st.set_page_config(page_title="Painel Transportes - Fujicom", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    * { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }
    .main > div { padding: 1rem 2rem; }
    .stApp { background: #0f1629; }
    .kpi-card { background: #1a2340; border-radius: 14px; padding: 1.2rem 1.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.3); border-left: 4px solid #7c9ccf; margin-bottom: 0.5rem; }
    .kpi-card:hover { transform: translateY(-1px); }
    .kpi-card .label { font-size: 0.72rem; color: #8899b8; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }
    .kpi-card .value { font-size: 1.6rem; font-weight: 700; color: #e8edf5; margin-top: 0.15rem; }
    .kpi-card .sub { font-size: 0.78rem; color: #8899b8; margin-top: 0.1rem; }
    .card { background: #1a2340; border-radius: 14px; padding: 1.5rem; box-shadow: 0 4px 16px rgba(0,0,0,0.3); margin-bottom: 1rem; }
    h1, h2, h3, h4, h5, h6 { color: #e8edf5; font-weight: 600; }
    p, .stMarkdown, .caption, .stCaption { color: #c5ccd9; }
    .stButton > button, .stDownloadButton > button { background: linear-gradient(180deg, #2b5090 0%, #1e3a6e 100%); color: white; border: none; border-radius: 8px; padding: 0.4rem 1.5rem; font-weight: 500; }
    .stButton > button:hover { background: linear-gradient(180deg, #3663a8 0%, #2b5090 100%); }
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #253052; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.4rem; background: #1a2340; padding: 0.5rem 0.8rem; border-radius: 12px; margin-bottom: 1rem; }
    .stTabs button[data-baseweb="tab"] { border-radius: 8px; padding: 0.45rem 1.1rem; font-weight: 500; font-size: 0.85rem; color: #8899b8; border: none; }
    .stTabs button[data-baseweb="tab"]:hover { color: #e8edf5; background: #253052; }
    .stTabs button[data-baseweb="tab"][aria-selected="true"] { background: #253e81 !important; color: white !important; }
    footer { display: none; }
    section[data-testid="stSidebar"] { background: #0f1629; border-right: 1px solid #1a2340; }
    .stSidebar .stMarkdown, .stSidebar .stMarkdown p { color: #e8edf5; }
    .stButton > button[kind="secondary"] { background: #253052; color: #c5ccd9; border: 1px solid #3a4a6e; }
    .stAlert { background: #1a2340; color: #e8edf5; border-color: #253052; }
    .block-config { background: #16233a; border: 1px solid #253e81; border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.8rem; }
    .block-config h4 { color: #7c9ccf; margin: 0 0 0.3rem 0; }
    .block-config .param { font-size: 0.82rem; color: #8899b8; margin: 0.15rem 0; }
    .block-config .param span { color: #e8edf5; font-weight: 500; }
    .login-container { max-width: 380px; margin: 0 auto; padding: 2rem 0; }
    .stStatus { color: #e8edf5; }
    div[data-baseweb="menu"] { background: #ffffff; border: 1px solid #a0b8cc; }
    li[role="option"] { color: #1a1a2e; }
    li[role="option"]:hover, li[role="option"][aria-selected="true"] { background: #253e81; color: #ffffff; }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] .stTextInput input { background: #d9e4f4 !important; border-color: #b8c9dd !important; }
    section[data-testid="stSidebar"] [data-baseweb="select"] * { color: #000000 !important; }
    section[data-testid="stSidebar"] .stTextInput input { color: #000000 !important; }
    div[data-baseweb="multi-select"] span,
    div[data-baseweb="tag"] span,
    div[data-baseweb="multi-select"] div[data-baseweb="input"] span { color: #ffffff !important; }
    div[data-baseweb="multi-select"] input::placeholder { color: #aabbcc !important; }
    div[data-baseweb="menu"] { background: #1a2340 !important; border: 1px solid #3a4a6e !important; }
    div[data-baseweb="menu"] li,
    div[data-baseweb="menu"] li span,
    ul[role="listbox"] li,
    ul[role="listbox"] li span,
    div[data-baseweb="select"] span[role="option"] { color: #ffffff !important; }
    div[data-baseweb="menu"] li:hover,
    div[data-baseweb="menu"] li[aria-selected="true"],
    ul[role="listbox"] li:hover { background: #253e81 !important; }
    div[data-baseweb="multi-select"] div[aria-expanded="false"] span { color: #ffffff !important; }
    div[data-baseweb="multi-select"] div[aria-expanded="true"] span { color: #ffffff !important; }
    [data-testid="stWidgetLabel"] { font-size: 1.125rem !important; font-weight: 700 !important; color: #e8edf5 !important; }
</style>
""", unsafe_allow_html=True)

logo_path = os.path.join(os.path.dirname(__file__), "..", "Fujicom", "logo_fujicom.jpg")

# ─── LOGIN ───
ALLOWED_EMAILS = [
    "glecya.frota@fujicom.com.br",
    "luis.claudio@fujicom.com.br",
    "larissa.fujita@fujicom.com.br",
    "rogeriopenha@gmail.com",
    "guilherme.abreu@fujicom.com.br",
    "financeiro01@fujicom.com.br",
]

if "auth_email" not in st.session_state:
    st.session_state.auth_email = None
if "_nf_detail" not in st.session_state:
    st.session_state._nf_detail = None
if "_go_to_carrier" not in st.session_state:
    st.session_state._go_to_carrier = False

if not st.session_state.auth_email:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        try:
            logo_login = Image.open(logo_path)
            logo_login = logo_login.resize((220, int(logo_login.height * 220 / logo_login.width)))
            st.image(logo_login)
        except:
            st.markdown("<h1 style='color:#e8edf5;'>Painel Transportes</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:#e8edf5; margin-bottom:1.5rem;'>Fujicom - Transportadoras</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu@email.com.br")
            pw = st.text_input("Senha", placeholder="Digite sua senha", type="password")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                email_ok = email.strip().lower() in [e.strip().lower() for e in ALLOWED_EMAILS]
                pw_ok = pw == "fujicom2026"
                if email_ok and pw_ok:
                    st.session_state.auth_email = email.strip().lower()
                    st.rerun()
                elif not email_ok:
                    st.error("Email não autorizado")
                else:
                    st.error("Senha incorreta")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ─── SIDEBAR ───
try:
    logo = Image.open(logo_path)
    logo = logo.resize((180, int(logo.height * 180 / logo.width)))
    st.sidebar.image(logo)
except:
    pass
st.sidebar.markdown("<h2 style='color:#1a5276; margin-bottom:0;'>Painel Transportes</h2><p style='color:#6c757d; font-size:0.85rem; margin-top:0;'>Fujicom</p>", unsafe_allow_html=True)
st.sidebar.markdown(f"👤 {st.session_state.auth_email}", unsafe_allow_html=True)
if st.sidebar.button("🚪 Sair", type="primary"):
    st.session_state.auth_email = None
    st.rerun()
st.sidebar.markdown("---")

SHEET_URL_DEFAULT = "https://docs.google.com/spreadsheets/d/1-pWMmfKCr3k4cl50mxyhp08C6qDZSTFlddmJYUpS3CU/edit?gid=0#gid=0"
SA_PATH_DEFAULT = os.path.join(os.path.dirname(__file__), "service_account.json")

GCP_JSON_SECRET = st.secrets.get("gcp_service_account") or st.secrets.get("gcp_service_account_json")
SHEET_URL_SECRET = st.secrets.get("sheet_url")
CLOUD_MODE = bool(GCP_JSON_SECRET and SHEET_URL_SECRET)

if CLOUD_MODE:
    st.sidebar.success("☁️ Modo nuvem")

# Auto-detect local service_account.json
sa_auto = None
if os.path.exists(SA_PATH_DEFAULT):
    with open(SA_PATH_DEFAULT, "r", encoding="utf-8") as f:
        sa_auto = f.read()

if "gs_creds" not in st.session_state:
    if sa_auto and SHEET_URL_DEFAULT:
        st.session_state.gs_creds = sa_auto
        st.session_state.gs_url = SHEET_URL_DEFAULT

# Sidebar UI para conexão manual (fallback)
if not CLOUD_MODE:
    st.sidebar.markdown("### 🔑 Conexão Google Sheets")
    default_url = st.session_state.get("gs_url", SHEET_URL_DEFAULT)
    sheet_url_input = st.sidebar.text_input("URL da Planilha", value=default_url, key="sheet_url_input")
    json_key = st.sidebar.file_uploader("Service Account JSON", type="json", key="gs_upload")
    conectar_btn = st.sidebar.button("Conectar", type="primary", key="conectar_btn")

# ─── HELPERS ───
def gsheet_connect(creds_dict, sheet_url):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if isinstance(creds_dict, bytes):
        creds_dict = creds_dict.decode("utf-8")
    if isinstance(creds_dict, str):
        creds_dict = json.loads(creds_dict)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(sheet_url)

def df_from_ws(ws):
    raw = ws.get_all_values()
    if not raw:
        return pd.DataFrame()
    return pd.DataFrame(raw[1:], columns=raw[0])

def get_cell(ws, row, col):
    try:
        return ws.cell(row, col).value
    except:
        return None

def ensure_sheet(sheet, name, headers):
    try:
        return sheet.worksheet(name)
    except:
        ws = sheet.add_worksheet(title=name, rows=100, cols=len(headers))
        ws.append_row(headers)
        return ws

def parse_date_br(v):
    if pd.isna(v) or not v:
        return pd.NaT
    try:
        return pd.to_datetime(str(v).strip(), dayfirst=True, errors="coerce")
    except:
        return pd.NaT

def status_color(s):
    s = str(s).lower()
    if "entreg" in s:
        return "#27ae60"
    if "trânsito" in s or "transito" in s or "colet" in s or "origem" in s:
        return "#2980b9"
    if "atras" in s or "cancel" in s or "pendent" in s:
        return "#e74c3c"
    if "previst" in s:
        return "#f39c12"
    return "#8899b8"

# ─── LOAD / CONNECT ───
creds_json = None
sheet_url = None

if CLOUD_MODE:
    creds_json = json.dumps(GCP_JSON_SECRET) if not isinstance(GCP_JSON_SECRET, str) else GCP_JSON_SECRET
    sheet_url = SHEET_URL_SECRET
elif "gs_creds" in st.session_state and "gs_url" in st.session_state:
    creds_json = st.session_state.gs_creds
    sheet_url = st.session_state.gs_url
elif conectar_btn and json_key and sheet_url_input:
    creds_json = json_key.read()
    sheet_url = sheet_url_input
    st.session_state.gs_creds = creds_json
    st.session_state.gs_url = sheet_url
    st.rerun()

if not creds_json or not sheet_url:
    st.error("❌ Planilha não configurada. Verifique os Secrets no dashboard do Streamlit Cloud.")
    st.caption("Secret necessario: `gcp_service_account` (JSON da service account) e `sheet_url` (URL da planilha).")
    st.stop()

# ─── GEBEX CONFIG ───
GBEX_FILE_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "Fujicom", "GBEX", "OCOREN_FUJICOM.TXT")

if CLOUD_MODE:
    uploaded_ocoren = st.sidebar.file_uploader("📁 Arquivo OCOREN GBEX", type="txt", key="ocoren_upload")
    if uploaded_ocoren is not None:
        st.session_state.ocoren_content = uploaded_ocoren.getvalue().decode("utf-8")
        st.session_state.ocoren_filename = uploaded_ocoren.name
    gebex_file_path = st.session_state.get("ocoren_path", "")
    if st.session_state.get("ocoren_content"):
        st.sidebar.success(f"✅ OCOREN carregado: {st.session_state.get('ocoren_filename', '')}")
else:
    gebex_file_path = st.sidebar.text_input("📁 Arquivo OCOREN GBEX", value=st.session_state.get("gebex_path", GBEX_FILE_DEFAULT), key="gebex_path_input")

# ─── LOAD PARAMETERS ───
try:
    sheet = gsheet_connect(creds_json, sheet_url)
    st.sidebar.success("✅ Conectado ao Google Sheets")
except Exception as e:
    st.sidebar.error(f"Erro ao conectar: {e}")
    st.stop()

try:
    ws_params = sheet.worksheet("Parametros")
    df_params = df_from_ws(ws_params)
except:
    ws_params = sheet.add_worksheet(title="Parametros", rows=50, cols=10)
    ws_params.append_row(["Parametro", "Valor", "Transportadora", "Grupo", "Descricao"])
    ws_params.append_row(["cnpj", "2323120000236", "Braspress", "api", "CNPJ do tomador"])
    ws_params.append_row(["usuario", "2323120000236_PRD", "Braspress", "api", "Usuário API"])
    ws_params.append_row(["senha", "J27113flmAih0D8Q", "Braspress", "api", "Senha API"])
    ws_params.append_row(["api_url", "https://api.braspress.com", "Braspress", "api", "URL base da API"])
    ws_params.append_row(["nfs", "", "Braspress", "tracking", "NFs para rastrear (separadas por vírgula)"])
    ws_params.append_row(["pedidos", "", "Braspress", "tracking", "Nº Pedidos para rastrear (separados por vírgula)"])
    df_params = df_from_ws(ws_params)

# Parse parameters
param_map = {}
for _, row in df_params.iterrows():
    key = str(row.iloc[0]).strip() if len(row) > 0 else ""
    val = str(row.iloc[1]).strip() if len(row) > 1 else ""
    transp = str(row.iloc[2]).strip() if len(row) > 2 else ""
    grupo = str(row.iloc[3]).strip() if len(row) > 3 else ""
    if key and transp:
        param_map[f"{transp}|{key}"] = val

BR_CNPJ = param_map.get("Braspress|cnpj", "2323120000236")
BR_USUARIO = param_map.get("Braspress|usuario", "2323120000236_PRD")
BR_SENHA = param_map.get("Braspress|senha", "J27113flmAih0D8Q")
BR_NFS = [nf.strip() for nf in param_map.get("Braspress|nfs", "").split(",") if nf.strip()]
BR_PEDIDOS = [p.strip() for p in param_map.get("Braspress|pedidos", "").split(",") if p.strip()]

# ─── LOAD BRASPRESS DATA ───
ws_br = ensure_sheet(sheet, "BR-Conhecimentos", ["numero", "origem", "emissao", "remetente", "destinatario",
    "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete", "previsaoEntrega", "dataEntrega",
    "status", "cidade", "uf", "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
    "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data", "data_consulta"])

try:
    df_br = df_from_ws(ws_br)
    if not df_br.empty:
        for col in ["emissao", "previsaoEntrega", "dataEntrega", "dataOcorrencia", "nf_emissao", "ultimo_status_data"]:
            if col in df_br.columns:
                df_br[col] = df_br[col].apply(parse_date_br)
except Exception:
    df_br = pd.DataFrame()

import json as _json_br_load
br_timeline_map = {}
try:
    ws_br_tl = sheet.worksheet("BR-Timeline")
    raw_br_tl = ws_br_tl.get_all_values()
    if raw_br_tl and len(raw_br_tl) > 1:
        for row_br_tl in raw_br_tl[1:]:
            if row_br_tl and row_br_tl[0]:
                try:
                    br_timeline_map[row_br_tl[0]] = {
                        "nf_numero": row_br_tl[1] if len(row_br_tl) > 1 else "",
                        "timeline": _json_br_load.loads(row_br_tl[2]) if len(row_br_tl) > 2 and row_br_tl[2] else []
                    }
                except:
                    pass
except:
    pass

# ─── LOAD GEBEX DATA ───
from ocorren_parser import processar_arquivo_ocorren, sync_ocorrencias_to_gsheet

df_gb = pd.DataFrame()
gebex_ocorrencias_raw = []
gebex_agregadas = []

ocoren_content = st.session_state.get("ocoren_content", "")
ocoren_path = gebex_file_path if not CLOUD_MODE else ""

def _load_df_gb_from_sheet(ws_gb):
    df_gb_sheet = df_from_ws(ws_gb)
    if not df_gb_sheet.empty:
        df_gb = df_gb_sheet.rename(columns={
            "ultima_ocorrencia": "ultimaOcorrencia",
            "data_ocorrencia": "dataOcorrencia",
            "data_emissao": "emissao",
        })
        df_gb["transportadora"] = "GEBEX"
        df_gb["cidade"] = ""
        df_gb["uf"] = ""
        df_gb["destinatario"] = ""
        for col in ["dataOcorrencia", "emissao"]:
            if col in df_gb.columns:
                df_gb[col] = df_gb[col].apply(parse_date_br)
        return df_gb
    return pd.DataFrame()

def _sync_raw_ocorrencias(ocorrencias_raw, sheet):
    import json as _json
    headers_raw = ["nf_numero", "ocorrencias_json"]
    try:
        ws_raw = sheet.worksheet("GB-Ocorrencias-Raw")
    except:
        ws_raw = sheet.add_worksheet(title="GB-Ocorrencias-Raw", rows=100, cols=2)
        ws_raw.append_row(headers_raw)

    from collections import defaultdict
    nfs_raw = defaultdict(list)
    for o in ocorrencias_raw:
        nf = o.get("numero_nf", "")
        if nf:
            nfs_raw[nf].append({
                "numero_nf": nf,
                "cnpj_emissor": o.get("cnpj_emissor", ""),
                "serie_nf": o.get("serie_nf", ""),
                "codigo_ocorrencia": o.get("codigo_ocorrencia", 0),
                "descricao_ocorrencia": o.get("descricao_ocorrencia", ""),
                "data_ocorrencia": o.get("data_ocorrencia", ""),
                "sequencial": o.get("sequencial", ""),
            })

    raw = ws_raw.get_all_values()
    existing_map = {}
    if raw and len(raw) > 1:
        for row in raw[1:]:
            if row and row[0]:
                try:
                    existing_map[row[0]] = _json.loads(row[1]) if row[1] else []
                except:
                    existing_map[row[0]] = []

    for nf, new_ocorrs in nfs_raw.items():
        old_ocorrs = existing_map.get(nf, [])
        old_seq = {str(o.get("sequencial", "")): o for o in old_ocorrs}
        for o in new_ocorrs:
            old_seq[str(o.get("sequencial", ""))] = o
        merged = sorted(old_seq.values(), key=lambda x: str(x.get("sequencial", "0")))
        existing_map[nf] = merged

    all_rows_raw = [[nf, _json.dumps(ocorrs, ensure_ascii=False)] for nf, ocorrs in existing_map.items()]
    ws_raw.clear()
    ws_raw.append_row(headers_raw)
    for i in range(0, len(all_rows_raw), 100):
        ws_raw.append_rows(all_rows_raw[i:i+100])

def _load_raw_ocorrencias_from_sheet(sheet):
    import json as _json
    try:
        ws_raw = sheet.worksheet("GB-Ocorrencias-Raw")
    except:
        return []
    raw = ws_raw.get_all_values()
    all_ocorrs = []
    if raw and len(raw) > 1:
        for row in raw[1:]:
            if row and row[0] and len(row) > 1 and row[1]:
                try:
                    ocorrs = _json.loads(row[1])
                    all_ocorrs.extend(ocorrs)
                except:
                    pass
    return all_ocorrs

ws_gb = ensure_sheet(sheet, "GB-Ocorrencias",
    ["nf_numero", "status", "ultima_ocorrencia", "data_ocorrencia",
     "data_emissao", "codigo_ocorrencia", "sequencial", "transportadora",
     "cnpj_emissor", "serie_nf"])

df_gb = _load_df_gb_from_sheet(ws_gb)
gebex_ocorrencias_raw = _load_raw_ocorrencias_from_sheet(sheet)

if CLOUD_MODE and ocoren_content:
    try:
        from ocorren_parser import OcorrenParser, agregar_ocorrencias
        parser = OcorrenParser()
        gebex_ocorrencias_raw_new = parser.parse_text(ocoren_content)
        gebex_agregadas = agregar_ocorrencias(gebex_ocorrencias_raw_new)
        sync_ocorrencias_to_gsheet(gebex_agregadas, ws_gb)
        _sync_raw_ocorrencias(gebex_ocorrencias_raw_new, sheet)
        gebex_ocorrencias_raw = _load_raw_ocorrencias_from_sheet(sheet)
        df_gb = _load_df_gb_from_sheet(ws_gb)
    except Exception as e:
        st.sidebar.warning(f"Erro ao processar OCOREN: {e}")
elif os.path.exists(ocoren_path):
    try:
        from ocorren_parser import OcorrenParser, agregar_ocorrencias
        parser = OcorrenParser()
        gebex_ocorrencias_raw_new = parser.parse_file(ocoren_path)
        gebex_agregadas = agregar_ocorrencias(gebex_ocorrencias_raw_new)
        sync_ocorrencias_to_gsheet(gebex_agregadas, ws_gb)
        _sync_raw_ocorrencias(gebex_ocorrencias_raw_new, sheet)
        gebex_ocorrencias_raw = _load_raw_ocorrencias_from_sheet(sheet)
        df_gb = _load_df_gb_from_sheet(ws_gb)
    except Exception as e:
        st.sidebar.warning(f"Erro ao processar OCOREN: {e}")

gb_entregues = len(df_gb[df_gb["status"].str.lower().str.contains("entreg", na=False)]) if not df_gb.empty else 0
gb_transito = len(df_gb[df_gb["status"].str.lower().str.contains("trânsito|transito", na=False)]) if not df_gb.empty else 0

# ─── MAIN HEADER ───
total_conhecimentos = len(df_br) + len(df_gb)
br_entregues = len(df_br[df_br["status"].str.lower().str.contains("entreg", na=False)]) if not df_br.empty and "status" in df_br.columns else 0
br_transito = len(df_br[df_br["status"].str.lower().str.contains("trânsito|transito|colet", na=False)]) if not df_br.empty and "status" in df_br.columns else 0
entregues = br_entregues + gb_entregues
em_transito = br_transito + gb_transito
pendentes = total_conhecimentos - entregues - em_transito

st.markdown(f"""
<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:1rem;">
    <div>
        <h1 style="margin:0;">🚚 Painel Transportes - Fujicom</h1>
        <p style="color:#6c757d; margin:0;">{total_conhecimentos} registros • {entregues} entregues • {em_transito} em trânsito</p>
    </div>
    <div style="font-size:0.85rem; color:#6c757d;">{datetime.now().strftime("%d/%m/%Y %H:%M")}</div>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""<div class="kpi-card" style="border-left-color: #27ae60;"><div class="label">📦 Total Registros</div><div class="value">{total_conhecimentos}</div><div class="sub">Braspress {len(df_br)} + GEBEX {len(df_gb)}</div></div>""", unsafe_allow_html=True)
pct_transito = em_transito / total_conhecimentos * 100 if total_conhecimentos > 0 else 0
pct_entregues = entregues / total_conhecimentos * 100 if total_conhecimentos > 0 else 0
with k2:
    st.markdown(f"""<div class="kpi-card" style="border-left-color: #2980b9;"><div class="label">🚛 Em Trânsito</div><div class="value">{em_transito}</div><div class="sub">{pct_transito:.1f}%</div></div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="kpi-card" style="border-left-color: #27ae60;"><div class="label">✅ Entregues</div><div class="value">{entregues}</div><div class="sub">{pct_entregues:.1f}%</div></div>""", unsafe_allow_html=True)
with k4:
    pct_pendentes = pendentes / total_conhecimentos * 100 if total_conhecimentos > 0 else 0
    st.markdown(f"""<div class="kpi-card" style="border-left-color: #f39c12;"><div class="label">⏳ Pendentes / Atrasados</div><div class="value">{pendentes}</div><div class="sub">{pct_pendentes:.1f}%</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── TABS ───
tabs = st.tabs(["📈 Visão Geral", "🚛 Braspress", "📦 GEBEX", "⚙️ Parâmetros", "📋 Dados Exportáveis"])
tab_geral, tab_br, tab_gb, tab_params, tab_export = tabs

# ─── TAB: VISÃO GERAL ───
with tab_geral:
    # --- Search Area ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        period_option = st.selectbox("Período", PERIOD_OPTIONS, index=3, key="periodo_cli")
    with fc2:
        nf_busca = st.text_input("Nota Fiscal", placeholder="Ex: 21070", key="nf_busca_geral")
    with fc3:
        cli_busca = st.text_input("Cliente", placeholder="Ex: COLSAN", key="cli_busca_geral")
    with fc4:
        all_statuses = []
        if not df_br.empty and "status" in df_br.columns:
            all_statuses.extend(df_br["status"].dropna().unique().tolist())
        if not df_gb.empty and "status" in df_gb.columns:
            all_statuses.extend(df_gb["status"].dropna().unique().tolist())
        all_statuses = sorted(set(str(s) for s in all_statuses if s))
        status_filter = st.multiselect("Status", all_statuses, key="status_filter_geral", placeholder="Status...")

    fb1, fb2, fb3, fb4 = st.columns(4)
    with fb1:
        mes_fechado_geral = None
        if period_option == "Mês fechado":
            _dates_geral = pd.concat([
                pd.Series(df_br["emissao"].tolist() if "emissao" in df_br.columns else []),
                pd.Series(df_gb["dataOcorrencia"].tolist() if "dataOcorrencia" in df_gb.columns else [])
            ], ignore_index=True)
            _months_geral = _get_available_months(_dates_geral)
            mes_fechado_geral = st.selectbox("Mês", _months_geral, key="mes_fechado_geral", label_visibility="collapsed", placeholder="Selecione o mês")
    with fb2:
        busca_nf_click = st.button("Buscar NF", type="primary", use_container_width=True, key="btn_busca_nf")
    with fb3:
        busca_cli_click = st.button("Buscar Cliente", type="primary", use_container_width=True, key="btn_busca_cli")
    with fb4:
        if st.button("🗑️ Limpar", key="btn_clear_filters", use_container_width=True):
            for k in ["nf_busca_geral", "cli_busca_geral", "status_filter_geral", "periodo_cli", "mes_fechado_geral"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    # Build a unified dataset with carrier column
    def build_unified_data():
        rows = []
        if not df_br.empty:
            for _, r in df_br.iterrows():
                row = r.to_dict()
                row["_transportadora"] = "Braspress"
                row["_prefixo"] = "BR"
                rows.append(row)
        if not df_gb.empty:
            for _, r in df_gb.iterrows():
                row = r.to_dict()
                row["_transportadora"] = "GEBEX"
                row["_prefixo"] = "GB"
                rows.append(row)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    df_unified = build_unified_data()
    if status_filter and not df_unified.empty and "status" in df_unified.columns:
        df_unified = df_unified[df_unified["status"].isin(status_filter)]
        df_br_filtered = df_br[df_br["status"].isin(status_filter)] if not df_br.empty and "status" in df_br.columns else df_br
        df_gb_filtered = df_gb[df_gb["status"].isin(status_filter)] if not df_gb.empty and "status" in df_gb.columns else df_gb
    else:
        df_br_filtered = df_br
        df_gb_filtered = df_gb
    st.markdown("</div>", unsafe_allow_html=True)

    # --- NF Panorama ---
    if busca_nf_click and nf_busca.strip():
        nf_clean = nf_busca.strip()
        match = df_unified[df_unified.astype(str).apply(lambda r: r.str.contains(nf_clean, case=False, na=False)).any(axis=1)]
        if not match.empty:
            row = match.iloc[0]
            transp = row.get("_transportadora", "?")
            st.markdown('<div class="card" style="border-left: 4px solid #2980b9;">', unsafe_allow_html=True)
            st.markdown(f'<h3 style="color:#e8edf5;">📦 Panorama da NF {nf_clean}</h3>', unsafe_allow_html=True)
            p1, p2, p3, p4 = st.columns(4)
            with p1:
                emissao = str(row.get("emissao", ""))[:10] if pd.notna(row.get("emissao")) else "-"
                st.markdown(f"""<div class="kpi-card" style="border-left-color:#2980b9;"><div class="label">📅 Data Emissão</div><div class="value" style="font-size:1.1rem;">{emissao}</div></div>""", unsafe_allow_html=True)
            with p2:
                prev = str(row.get("previsaoEntrega", ""))[:10] if pd.notna(row.get("previsaoEntrega")) else "-"
                st.markdown(f"""<div class="kpi-card" style="border-left-color:#f39c12;"><div class="label">📅 Previsão Entrega</div><div class="value" style="font-size:1.1rem;">{prev}</div></div>""", unsafe_allow_html=True)
            with p3:
                sts = str(row.get("status", "-"))
                cor = "#27ae60" if "entreg" in sts.lower() else "#2980b9" if "trânsito" in sts.lower() or "colet" in sts.lower() else "#e74c3c"
                st.markdown(f"""<div class="kpi-card" style="border-left-color:{cor};"><div class="label">📌 Status</div><div class="value" style="font-size:1.1rem;">{sts}</div></div>""", unsafe_allow_html=True)
            with p4:
                st.markdown(f"""<div class="kpi-card" style="border-left-color:#8e44ad;"><div class="label">🚛 Transportadora</div><div class="value" style="font-size:1.1rem;">{transp}</div></div>""", unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Destinatário:** {row.get('destinatario', '-')}")
                st.markdown(f"**Remetente:** {row.get('remetente', '-')}")
                st.markdown(f"**Origem:** {row.get('origem', '-')} → **Destino:** {row.get('cidade', '-')}/{row.get('uf', '-')}")
            with c2:
                ult_oco = str(row.get("ultimaOcorrencia", "-"))
                dt_oco = str(row.get("dataOcorrencia", ""))[:10] if pd.notna(row.get("dataOcorrencia")) else "-"
                st.markdown(f"**Última Ocorrência:** {ult_oco}")
                st.markdown(f"**Data:** {dt_oco}")
                if row.get("totalFrete"):
                    st.markdown(f"**Valor Frete:** R$ {pd.to_numeric(row['totalFrete'], errors='coerce'):,.2f}")
            col_ver, col_limpar = st.columns([1, 1])
            with col_ver:
                if st.button(f"Ver detalhes na {transp}", key="go_to_carrier", type="secondary"):
                    st.session_state._nf_detail = nf_clean
                    st.session_state._go_to_carrier = True
            with col_limpar:
                if st.button("Limpar", key="limpar_panorama", type="secondary"):
                    st.session_state._nf_detail = None
                    st.session_state._go_to_carrier = False
                    st.rerun()
            if st.session_state.get("_go_to_carrier"):
                st.info(f"Acesse a aba **{transp}** acima para ver os detalhes completos deste conhecimento.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning(f"NF {nf_clean} não encontrada em nenhuma transportadora.")

    # --- Client Search Results ---
    if busca_cli_click and cli_busca.strip():
        cli_clean = cli_busca.strip()
        mask = df_unified.astype(str).apply(lambda r: r.str.contains(cli_clean, case=False, na=False)).any(axis=1)
        cli_results = df_unified[mask].copy()

        if not cli_results.empty:
            cli_results = _apply_period_filter(cli_results, period_option, "emissao", mes_fechado_geral)

            if not cli_results.empty:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f'<h3 style="color:#e8edf5;">📋 Notas de {cli_clean} ({len(cli_results)} registros)</h3>', unsafe_allow_html=True)
                display_cols = ["_transportadora", "nf_numero", "numero", "emissao", "previsaoEntrega", "status", "cidade", "uf", "destinatario", "valorMercantil"]
                existing_display = [c for c in display_cols if c in cli_results.columns]
                df_cli_show = cli_results[existing_display].copy()
                df_cli_show.columns = [c.replace("_transportadora","Transp.").replace("nf_numero","NF").replace("numero","CTE").replace("emissao","Emissão").replace("previsaoEntrega","Prev.Entrega").replace("status","Status").replace("cidade","Cidade").replace("uf","UF").replace("destinatario","Cliente").replace("valorMercantil","Valor") for c in existing_display]
                for c in df_cli_show.select_dtypes(include=["datetime64"]).columns:
                    df_cli_show[c] = df_cli_show[c].dt.strftime("%d/%m/%Y")
                st.dataframe(df_cli_show, use_container_width=True, hide_index=True, height=400)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info(f"Nenhum registro de {cli_clean} no período selecionado.")
        else:
            st.warning(f"Cliente '{cli_clean}' não encontrado.")

    # --- Carrier Overview ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:#e8edf5;">Visão Geral por Transportadora</h3>', unsafe_allow_html=True)

    br_ent_f = len(df_br_filtered[df_br_filtered["status"].str.lower().str.contains("entreg", na=False)]) if not df_br_filtered.empty and "status" in df_br_filtered.columns else 0
    br_trans_f = len(df_br_filtered[df_br_filtered["status"].str.lower().str.contains("trânsito|transito|colet", na=False)]) if not df_br_filtered.empty and "status" in df_br_filtered.columns else 0
    gb_ent_f = len(df_gb_filtered[df_gb_filtered["status"].str.lower().str.contains("entreg", na=False)]) if not df_gb_filtered.empty and "status" in df_gb_filtered.columns else 0
    gb_trans_f = len(df_gb_filtered[df_gb_filtered["status"].str.lower().str.contains("trânsito|transito", na=False)]) if not df_gb_filtered.empty and "status" in df_gb_filtered.columns else 0

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown("""
        <div class="block-config">
            <h4>🚛 Braspress</h4>
            <p class="param">Conhecimentos: <span>{}</span></p>
            <p class="param">Entregues: <span>{}</span></p>
            <p class="param">Em trânsito: <span>{}</span></p>
            <p class="param">Última consulta: <span>{}</span></p>
        </div>
        """.format(
            len(df_br_filtered),
            br_ent_f,
            br_trans_f,
            df_br["data_consulta"].iloc[0] if not df_br.empty and "data_consulta" in df_br.columns else "Nunca"
        ), unsafe_allow_html=True)
    with cc2:
        data_ultima = ""
        if not df_gb.empty and "dataOcorrencia" in df_gb.columns:
            dates = df_gb["dataOcorrencia"].dropna()
            if not dates.empty:
                data_ultima = str(dates.max())[:10]
        st.markdown("""
        <div class="block-config">
            <h4>📦 GEBEX</h4>
            <p class="param">NFs: <span>{}</span></p>
            <p class="param">Entregues: <span>{}</span></p>
            <p class="param">Em trânsito: <span>{}</span></p>
            <p class="param">Última atualização: <span>{}</span></p>
        </div>
        """.format(
            len(df_gb_filtered),
            gb_ent_f,
            gb_trans_f,
            data_ultima if data_ultima else "Nunca"
        ), unsafe_allow_html=True)
    with cc3:
        st.markdown("""
        <div class="block-config">
            <h4>📦 DHL</h4>
            <p class="param"><span style="color:#f39c12;">⏳ Configuração pendente</span></p>
            <p class="param">A implementar</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if (not df_br.empty and "status" in df_br.columns) or not df_gb.empty:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<h3 style="color:#e8edf5;">Status Consolidado</h3>', unsafe_allow_html=True)
            df_status_all = []
            if not df_br_filtered.empty and "status" in df_br_filtered.columns:
                for _, r in df_br_filtered.iterrows():
                    df_status_all.append({"status": r.get("status", "?"), "transportadora": "Braspress"})
            if not df_gb_filtered.empty:
                for _, r in df_gb_filtered.iterrows():
                    df_status_all.append({"status": r.get("status", "?"), "transportadora": "GEBEX"})
            df_status_all = pd.DataFrame(df_status_all)
            if not df_status_all.empty:
                sc = df_status_all["status"].value_counts()
                fig = go.Figure(data=[go.Pie(labels=sc.index, values=sc.values, hole=0.55,
                    marker=dict(colors=px.colors.sequential.Blues[::-1][:len(sc)]),
                    textinfo="label+percent", textposition="outside", showlegend=False)])
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="white", font=dict(color="black"), legend=dict(font=dict(color="black")))
                st.plotly_chart(fig, use_container_width=True, key="chart_overview_status")
            st.markdown("</div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<h3 style="color:#e8edf5;">Registros por Transportadora</h3>', unsafe_allow_html=True)
            carrier_counts = {"Braspress": len(df_br_filtered), "GEBEX": len(df_gb_filtered)}
            carrier_df = pd.DataFrame(list(carrier_counts.items()), columns=["Transportadora", "Registros"])
            carrier_df = carrier_df[carrier_df["Registros"] > 0]
            if not carrier_df.empty:
                cores = ["#2980b9" if t == "Braspress" else "#27ae60" for t in carrier_df["Transportadora"]]
                fig = go.Figure(go.Bar(x=carrier_df["Registros"], y=carrier_df["Transportadora"], orientation="h",
                    marker=dict(color=cores, line=dict(width=0)),
                    text=carrier_df["Registros"], textposition="outside"))
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white", font=dict(color="black"), plot_bgcolor="white",
                    legend=dict(font=dict(color="black")),
                    xaxis=dict(visible=False), yaxis=dict(title=None, tickfont=dict(color="black")))
                st.plotly_chart(fig, use_container_width=True, key="chart_overview_carrier")
            st.markdown("</div>", unsafe_allow_html=True)

    # --- Timeline da NF (Visão Geral) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⏳ Timeline da NF")
    vg_tl_input = st.text_input("Digite a NF para ver o histórico", placeholder="Ex: 21070 ou 47696", key="vg_timeline_input")
    if vg_tl_input:
        vg_tl_clean = vg_tl_input.strip()
        tl_found = False
        tl_style = "background:#16233a; border-left:3px solid {cor}; padding:0.5rem 1rem; margin:0.3rem 0; border-radius:6px;"

        br_tl_data = br_timeline_map.get(vg_tl_clean)
        if not br_tl_data:
            for num, info in br_timeline_map.items():
                if info.get("nf_numero", "").lstrip("0") == vg_tl_clean.lstrip("0"):
                    br_tl_data = info
                    break
        if br_tl_data and br_tl_data.get("timeline"):
            tl_found = True
            st.markdown("**🚛 Braspress:**")
            for ev in br_tl_data["timeline"]:
                desc = ev.get("descricao", ev.get("status", "?"))
                dt = ev.get("data", ev.get("dataOcorrencia", ""))
                cor = "#27ae60" if "entreg" in str(desc).lower() else "#2980b9"
                st.markdown(f"""<div style="{tl_style.format(cor=cor)}"><strong>{dt}</strong> — {desc}</div>""", unsafe_allow_html=True)

        gb_tl_filtradas = [o for o in gebex_ocorrencias_raw if o.get("numero_nf", "").lstrip("0") == vg_tl_clean.lstrip("0")]
        if gb_tl_filtradas:
            tl_found = True
            gb_tl_filtradas.sort(key=lambda x: x.get("sequencial", "0"))
            st.markdown("**📦 GEBEX:**")
            for o in gb_tl_filtradas:
                cor = "#27ae60" if o["codigo_ocorrencia"] in (1, 24, 104, 105) else "#2980b9"
                st.markdown(f"""<div style="{tl_style.format(cor=cor)}"><strong>{o.get('data_ocorrencia', '')}</strong> — {o.get('descricao_ocorrencia', '')} <span style="color:#8899b8; font-size:0.8rem;">(cód. {o.get('codigo_ocorrencia', '')})</span></div>""", unsafe_allow_html=True)

        if not tl_found:
            st.info(f"NF {vg_tl_clean} não encontrada. Faça uma consulta primeiro (Braspress) ou faça upload do arquivo OCOREN (GEBEX).")
    st.markdown("</div>", unsafe_allow_html=True)

# ─── TAB: BRASPRESS ───
with tab_br:
    from braspress_api import BraspressAPI, flatten_conhecimentos

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚛 Braspress - Rastreamento")

    ac1, ac2, ac3 = st.columns([1, 1, 1])
    with ac1:
        atualizar = st.button("🔄 Atualizar Dados da API", type="primary", use_container_width=True)
    with ac2:
        nf_input = st.text_input("Adicionar NF para rastrear", placeholder="Ex: 123456", key="nf_add")
    with ac3:
        pedido_input = st.text_input("Adicionar Pedido", placeholder="Ex: 12345", key="pedido_add")

    with st.expander("📋 Adicionar múltiplas NFs de uma vez", expanded=False):
        nf_bulk = st.text_area(
            "Cole as NFs separadas por vírgula, ponto-e-vírgula ou quebra de linha",
            placeholder="Ex: 21136, 21200, 21350\nou\n21136\n21200\n21350",
            key="nf_bulk_input", height=120
        )
        if st.button("➕ Adicionar todas as NFs", type="primary", key="btn_bulk_nfs"):
            import re
            nf_list = re.split(r'[,\n;\s]+', nf_bulk)
            nf_list = [n.strip() for n in nf_list if n.strip() and n.strip().isdigit()]
            if nf_list:
                current_nfs = param_map.get("Braspress|nfs", "")
                existing = [n.strip() for n in current_nfs.split(",") if n.strip()] if current_nfs else []
                new_nfs_list = existing + [n for n in nf_list if n not in existing]
                new_nfs = ",".join(new_nfs_list)
                for i, row in enumerate(df_params.itertuples(), start=2):
                    if str(row[1]).strip() == "nfs" and str(row[3]).strip() == "Braspress":
                        ws_params.update_cell(i, 2, new_nfs)
                        break
                added = len([n for n in nf_list if n not in existing])
                st.success(f"✅ {added} NFs adicionadas ({len(existing)} já existentes ignoradas)")
                st.rerun()
            else:
                st.warning("Nenhuma NF válida encontrada no texto.")

    if nf_input:
        nf_clean = nf_input.strip()
        if nf_clean and nf_clean not in BR_NFS:
            current_nfs = param_map.get("Braspress|nfs", "")
            new_nfs = (current_nfs + "," + nf_clean) if current_nfs else nf_clean
            # Update sheet
            for i, row in enumerate(df_params.itertuples(), start=2):
                if str(row[1]).strip() == "nfs" and str(row[3]).strip() == "Braspress":
                    ws_params.update_cell(i, 2, new_nfs)
                    break
            st.rerun()

    if pedido_input:
        ped_clean = pedido_input.strip()
        if ped_clean and ped_clean not in BR_PEDIDOS:
            current_ped = param_map.get("Braspress|pedidos", "")
            new_ped = (current_ped + "," + ped_clean) if current_ped else ped_clean
            for i, row in enumerate(df_params.itertuples(), start=2):
                if str(row[1]).strip() == "pedidos" and str(row[3]).strip() == "Braspress":
                    ws_params.update_cell(i, 2, new_ped)
                    break
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    if atualizar:
        if not BR_NFS and not BR_PEDIDOS:
            st.warning("⚠️ Nenhuma NF ou Pedido configurado para rastrear. Adicione na aba Parâmetros ou acima.")
        else:
            api = BraspressAPI(BR_CNPJ, BR_USUARIO, BR_SENHA)

            with st.spinner("Consultando API Braspress..."):
                todos = []
                progress = st.progress(0)
                total = len(BR_NFS) + len(BR_PEDIDOS)
                count = 0

                for nf in BR_NFS:
                    try:
                        data = api.tracking_by_nf(nf)
                        rows = flatten_conhecimentos(data)
                        todos.extend(rows)
                    except Exception as e:
                        st.error(f"Erro NF {nf}: {e}")
                    count += 1
                    progress.progress(count / total)

                for ped in BR_PEDIDOS:
                    try:
                        data = api.tracking_by_pedido(ped)
                        rows = flatten_conhecimentos(data)
                        todos.extend(rows)
                    except Exception as e:
                        st.error(f"Erro Pedido {ped}: {e}")
                    count += 1
                    progress.progress(count / total)

            if todos:
                df_novo = pd.DataFrame(todos)
                cabecalhos = ["numero", "origem", "emissao", "remetente", "destinatario",
                    "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete", "previsaoEntrega", "dataEntrega",
                    "status", "cidade", "uf", "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
                    "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data", "data_consulta"]

                # Upsert: merge new API data with existing sheet data
                df_existing = df_br.copy() if not df_br.empty else pd.DataFrame(columns=cabecalhos)
                merge_key = "numero"
                if not df_existing.empty and merge_key in df_existing.columns and merge_key in df_novo.columns:
                    df_novo[merge_key] = df_novo[merge_key].astype(str)
                    df_existing[merge_key] = df_existing[merge_key].astype(str)
                    existing_keys = set(df_existing[merge_key].tolist())
                    df_new_only = df_novo[~df_novo[merge_key].isin(existing_keys)]
                    df_updated = df_novo[df_novo[merge_key].isin(existing_keys)]
                    df_preserved = df_existing[~df_existing[merge_key].isin(df_updated[merge_key])]
                    df_merged = pd.concat([df_preserved, df_updated, df_new_only], ignore_index=True)
                else:
                    df_merged = df_novo

                ws_br.clear()
                ws_br.append_row(cabecalhos)
                all_rows = [["" if pd.isna(v) else str(v) for v in row.tolist()] for _, row in df_merged.iterrows()]
                for i in range(0, len(all_rows), 100):
                    ws_br.append_rows(all_rows[i:i+100])

                df_br = df_merged

                import json as _json_br
                try:
                    ws_br_tl = sheet.worksheet("BR-Timeline")
                except:
                    ws_br_tl = sheet.add_worksheet(title="BR-Timeline", rows=100, cols=3)
                    ws_br_tl.append_row(["numero", "nf_numero", "timeline_json"])
                raw_tl = ws_br_tl.get_all_values()
                tl_map = {}
                if raw_tl and len(raw_tl) > 1:
                    for row_tl in raw_tl[1:]:
                        if row_tl and row_tl[0]:
                            try:
                                data = _json_br.loads(row_tl[2]) if len(row_tl) > 2 and row_tl[2] else []
                                if isinstance(data, list):
                                    tl_map[row_tl[0]] = {"nf_numero": row_tl[1] if len(row_tl) > 1 else "", "timeline": data}
                                else:
                                    tl_map[row_tl[0]] = data
                            except:
                                tl_map[row_tl[0]] = {"nf_numero": row_tl[1] if len(row_tl) > 1 else "", "timeline": []}
                for t in todos:
                    num = str(t.get("numero", ""))
                    nf_num = str(t.get("nf_numero", ""))
                    tl = t.get("timeline", [])
                    if num and tl:
                        tl_map[num] = {"nf_numero": nf_num, "timeline": tl}
                tl_rows = [[k, v.get("nf_numero", ""), _json_br.dumps(v.get("timeline", []), ensure_ascii=False)] for k, v in tl_map.items()]
                ws_br_tl.clear()
                ws_br_tl.append_row(["numero", "nf_numero", "timeline_json"])
                for i in range(0, len(tl_rows), 100):
                    ws_br_tl.append_rows(tl_rows[i:i+100])

                if not df_existing.empty:
                    st.success(f"✅ {len(todos)} consultados | {len(df_updated)} atualizados | {len(df_new_only)} novos | {len(df_merged)} total na planilha")
                else:
                    st.success(f"✅ {len(todos)} conhecimentos salvos pela primeira vez!")
                st.rerun()
            else:
                st.warning("Nenhum dado retornado da API.")

    if not df_br.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📋 Conhecimentos Braspress")

        nf_detail = st.session_state.get("_nf_detail")
        auto_filter = st.session_state.get("_go_to_carrier", False) and nf_detail

        if auto_filter and nf_detail:
            st.session_state["br_nf_busca"] = nf_detail

        br_f1, br_f2, br_f3, br_f4 = st.columns(4)
        with br_f1:
            br_period_option = st.selectbox("Período", PERIOD_OPTIONS, index=3, key="br_periodo_cli")
        with br_f2:
            br_nf_busca = st.text_input("Nota Fiscal", placeholder="Ex: 21070", key="br_nf_busca")
        with br_f3:
            br_cli_busca = st.text_input("Cliente", placeholder="Ex: COLSAN", key="br_cli_busca")
        with br_f4:
            br_status_opts = sorted(df_br["status"].dropna().unique()) if "status" in df_br.columns else []
            br_status_filter = st.multiselect("Status", br_status_opts, default=br_status_opts, key="br_status_filter", placeholder="Status...")
        br_b1, br_b2, br_b3, br_b4 = st.columns(4)
        with br_b1:
            br_mes_fechado = None
            if br_period_option == "Mês fechado" and "emissao" in df_br.columns:
                _months_br = _get_available_months(df_br["emissao"])
                br_mes_fechado = st.selectbox("Mês", _months_br, key="br_mes_fechado", label_visibility="collapsed", placeholder="Selecione o mês")
        with br_b2:
            br_busca_nf_click = st.button("Buscar NF", type="primary", use_container_width=True, key="btn_br_busca_nf")
        with br_b3:
            br_busca_cli_click = st.button("Buscar Cliente", type="primary", use_container_width=True, key="btn_br_busca_cli")
        with br_b4:
            if st.button("🗑️ Limpar", key="btn_br_clear", use_container_width=True):
                for k in ["br_nf_busca", "br_cli_busca", "br_status_filter", "br_periodo_cli", "br_mes_fechado"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        df_disp = df_br.copy()
        if br_status_filter:
            df_disp = df_disp[df_disp["status"].isin(br_status_filter)]
        if br_nf_busca:
            mask = df_disp.astype(str).apply(lambda row: row.str.contains(br_nf_busca, case=False, na=False)).any(axis=1)
            df_disp = df_disp[mask]
        if br_cli_busca:
            mask = df_disp.astype(str).apply(lambda row: row.str.contains(br_cli_busca, case=False, na=False)).any(axis=1)
            df_disp = df_disp[mask]
        df_disp = _apply_period_filter(df_disp, br_period_option, "emissao", br_mes_fechado)

        # Date formatting
        df_show = df_disp.copy()
        for c in df_show.select_dtypes(include=["datetime64"]).columns:
            df_show[c] = df_show[c].dt.strftime("%d/%m/%Y")

        st.dataframe(df_show, use_container_width=True, hide_index=True, height=450)
        st.caption(f"{len(df_disp)} registros")

        e1, e2, e3 = st.columns(3)
        csv = df_show.to_csv(index=False).encode("utf-8-sig")
        e1.download_button("📥 CSV", csv, f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as w:
            df_show.to_excel(w, index=False, sheet_name="Braspress")
        e2.download_button("📥 Excel", output.getvalue(), f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        e3.download_button("📥 JSON", df_show.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8-sig"), f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⏳ Timeline da NF (Braspress)")
        br_tl_input = st.text_input("Digite a NF ou nº conhecimento", placeholder="Ex: 21070", key="br_timeline_input")
        if br_tl_input:
            br_tl_clean = br_tl_input.strip()
            tl_data = br_timeline_map.get(br_tl_clean)
            if not tl_data:
                for num, info in br_timeline_map.items():
                    if info.get("nf_numero", "").lstrip("0") == br_tl_clean.lstrip("0"):
                        tl_data = info
                        break
            if tl_data and tl_data.get("timeline"):
                tl_events = tl_data["timeline"]
                for ev in tl_events:
                    desc = ev.get("descricao", ev.get("status", "?"))
                    dt = ev.get("data", ev.get("dataOcorrencia", ""))
                    cor = "#27ae60" if "entreg" in str(desc).lower() else "#2980b9"
                    st.markdown(f"""
                    <div style="background:#16233a; border-left:3px solid {cor}; padding:0.5rem 1rem; margin:0.3rem 0; border-radius:6px;">
                        <strong>{dt}</strong> — {desc}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(f"NF {br_tl_clean} não encontrada no timeline. Faça uma consulta na API primeiro.")
        st.markdown("</div>", unsafe_allow_html=True)

        # KPIs Braspress
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Métricas Braspress")
        bk1, bk2, bk3, bk4 = st.columns(4)
        with bk1:
            total_frete = pd.to_numeric(df_disp["totalFrete"], errors="coerce").sum() if "totalFrete" in df_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #8e44ad;"><div class="label">💰 Total Frete</div><div class="value">R$ {total_frete:,.2f}</div></div>""", unsafe_allow_html=True)
        with bk2:
            total_valor = pd.to_numeric(df_disp["valorMercantil"], errors="coerce").sum() if "valorMercantil" in df_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #2980b9;"><div class="label">📦 Valor Mercantil</div><div class="value">R$ {total_valor:,.2f}</div></div>""", unsafe_allow_html=True)
        with bk3:
            total_peso = pd.to_numeric(df_disp["peso"], errors="coerce").sum() if "peso" in df_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #27ae60;"><div class="label">⚖️ Peso Total</div><div class="value">{total_peso:,.0f} kg</div></div>""", unsafe_allow_html=True)
        with bk4:
            total_volumes = pd.to_numeric(df_disp["volumes"], errors="coerce").sum() if "volumes" in df_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #f39c12;"><div class="label">📊 Total Volumes</div><div class="value">{total_volumes:,.0f}</div></div>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Charts
        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Evolução por Status")
            if "emissao" in df_disp.columns and "status" in df_disp.columns:
                df_chart = df_disp.copy()
                df_chart["mes"] = df_chart["emissao"].dt.to_period("M").astype(str)
                df_group = df_chart.groupby(["mes", "status"]).size().reset_index(name="count")
                fig = px.bar(df_group, x="mes", y="count", color="status",
                    color_discrete_sequence=px.colors.qualitative.Bold,
                    barmode="group")
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white", font=dict(color="black"), plot_bgcolor="white",
                    legend=dict(font=dict(color="black")),
                    xaxis=dict(title=None, tickfont=dict(color="black")), yaxis=dict(title="Qtd", tickfont=dict(color="black")))
                st.plotly_chart(fig, use_container_width=True, key="chart_br_evolucao")
            st.markdown("</div>", unsafe_allow_html=True)
        with cc2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Top Destinatários")
            if "destinatario" in df_disp.columns:
                dc = df_disp["destinatario"].value_counts().head(10)
                fig = go.Figure(go.Bar(x=dc.values, y=dc.index, orientation="h",
                    marker=dict(color=dc.values, colorscale="Blues", line=dict(width=0)),
                    text=dc.values, textposition="outside"))
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white", font=dict(color="black"), plot_bgcolor="white",
                    legend=dict(font=dict(color="black")),
                    xaxis=dict(visible=False), yaxis=dict(title=None, tickfont=dict(color="black")))
                st.plotly_chart(fig, use_container_width=True, key="chart_br_destinatarios")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("📭 Nenhum dado de rastreamento disponível. Clique em 'Atualizar Dados da API' ou configure NFs/Pedidos.")

# ─── TAB: GEBEX ───
with tab_gb:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📦 GEBEX - Ocorrências")

    if not df_gb.empty:
        col_gb1, col_gb2 = st.columns(2)
        with col_gb1:
            if st.button("🔄 Recarregar do arquivo", type="secondary", key="gb_reload"):
                st.rerun()
        with col_gb2:
            st.markdown(f"**Arquivo:** `{gebex_file_path}`")

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📋 NFs Rastreadas")
        gb_f1, gb_f2, gb_f3, gb_f4 = st.columns(4)
        with gb_f1:
            gb_period_option = st.selectbox("Período", PERIOD_OPTIONS, index=3, key="gb_periodo_cli")
        with gb_f2:
            gb_nf_busca = st.text_input("Nota Fiscal", placeholder="Ex: 47696", key="gb_nf_busca")
        with gb_f3:
            gb_cli_busca = st.text_input("Cliente", placeholder="Ex: COLSAN", key="gb_cli_busca")
        with gb_f4:
            gb_status_opts = sorted(df_gb["status"].dropna().unique()) if "status" in df_gb.columns else []
            gb_status_filter = st.multiselect("Status", gb_status_opts, default=gb_status_opts, key="gb_status_filter", placeholder="Status...")
        gb_b1, gb_b2, gb_b3, gb_b4 = st.columns(4)
        with gb_b1:
            gb_mes_fechado = None
            if gb_period_option == "Mês fechado" and "dataOcorrencia" in df_gb.columns:
                _months_gb = _get_available_months(df_gb["dataOcorrencia"])
                gb_mes_fechado = st.selectbox("Mês", _months_gb, key="gb_mes_fechado", label_visibility="collapsed", placeholder="Selecione o mês")
        with gb_b2:
            gb_busca_nf_click = st.button("Buscar NF", type="primary", use_container_width=True, key="btn_gb_busca_nf")
        with gb_b3:
            gb_busca_cli_click = st.button("Buscar Cliente", type="primary", use_container_width=True, key="btn_gb_busca_cli")
        with gb_b4:
            if st.button("🗑️ Limpar", key="btn_gb_clear", use_container_width=True):
                for k in ["gb_nf_busca", "gb_cli_busca", "gb_status_filter", "gb_periodo_cli", "gb_mes_fechado"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()
        df_gb_disp = df_gb.copy()
        if gb_status_filter:
            df_gb_disp = df_gb_disp[df_gb_disp["status"].isin(gb_status_filter)]
        if gb_nf_busca:
            mask = df_gb_disp.astype(str).apply(lambda row: row.str.contains(gb_nf_busca, case=False, na=False)).any(axis=1)
            df_gb_disp = df_gb_disp[mask]
        if gb_cli_busca:
            mask = df_gb_disp.astype(str).apply(lambda row: row.str.contains(gb_cli_busca, case=False, na=False)).any(axis=1)
            df_gb_disp = df_gb_disp[mask]
        df_gb_disp = _apply_period_filter(df_gb_disp, gb_period_option, "dataOcorrencia", gb_mes_fechado)
        if "dataOcorrencia" in df_gb_disp.columns:
            df_gb_disp["dataOcorrencia"] = df_gb_disp["dataOcorrencia"].apply(
                lambda x: str(x)[:10] if pd.notna(x) else "")
        if "emissao" in df_gb_disp.columns:
            df_gb_disp["emissao"] = df_gb_disp["emissao"].apply(
                lambda x: str(x)[:10] if pd.notna(x) else "")
        st.dataframe(df_gb_disp, use_container_width=True, hide_index=True, height=350)
        st.caption(f"{len(df_gb_disp)} registros")
        st.markdown("</div>", unsafe_allow_html=True)

        # Detailed timeline
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⏳ Timeline da NF")
        nf_timeline = st.text_input("Digite a NF para ver o histórico", placeholder="Ex: 47696", key="gb_timeline_input")
        if nf_timeline:
            nf_clean = nf_timeline.strip()
            ocor_filtradas = [o for o in gebex_ocorrencias_raw if o.get("numero_nf", "").lstrip("0") == nf_clean.lstrip("0")]
            if ocor_filtradas:
                ocor_filtradas.sort(key=lambda x: x.get("sequencial", "0"))
                for o in ocor_filtradas:
                    cor = "#27ae60" if o["codigo_ocorrencia"] in (1, 24, 104, 105) else "#2980b9"
                    st.markdown(f"""
                    <div style="background:#16233a; border-left:3px solid {cor}; padding:0.5rem 1rem; margin:0.3rem 0; border-radius:6px;">
                        <strong>{o.get('data_ocorrencia', '')}</strong> — {o.get('descricao_ocorrencia', '')}
                        <span style="color:#8899b8; font-size:0.8rem;"> (cód. {o.get('codigo_ocorrencia', '')})</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info(f"NF {nf_clean} não encontrada no arquivo de ocorrências.")
        st.markdown("</div>", unsafe_allow_html=True)

        # KPIs
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Métricas GEBEX")
        gk1, gk2, gk3, gk4 = st.columns(4)
        with gk1:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #27ae60;"><div class="label">📦 Total NFs</div><div class="value">{len(df_gb_disp)}</div></div>""", unsafe_allow_html=True)
        with gk2:
            gb_transito_disp = len(df_gb_disp[df_gb_disp["status"].isin(["EM TRANSITO", "TRÂNSITO"])]) if "status" in df_gb_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #2980b9;"><div class="label">🚛 Em Trânsito</div><div class="value">{gb_transito_disp}</div></div>""", unsafe_allow_html=True)
        with gk3:
            gb_entregues_disp = len(df_gb_disp[df_gb_disp["status"].isin(["ENTREGUE", "ENTREGA"])]) if "status" in df_gb_disp.columns else 0
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #27ae60;"><div class="label">✅ Entregues</div><div class="value">{gb_entregues_disp}</div></div>""", unsafe_allow_html=True)
        pend_gb_disp = len(df_gb_disp) - gb_entregues_disp - gb_transito_disp
        with gk4:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #f39c12;"><div class="label">⏳ Pendentes</div><div class="value">{pend_gb_disp}</div></div>""", unsafe_allow_html=True)

        # Status pie
        if "status" in df_gb_disp.columns:
            sc_gb = df_gb_disp["status"].value_counts()
            fig_gb = go.Figure(data=[go.Pie(labels=sc_gb.index, values=sc_gb.values, hole=0.55,
                marker=dict(colors=px.colors.sequential.Blues[::-1][:len(sc_gb)]),
                textinfo="label+percent", textposition="outside", showlegend=False)])
            fig_gb.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="white", font=dict(color="black"), legend=dict(font=dict(color="black")))
            st.plotly_chart(fig_gb, use_container_width=True, key="chart_gb_status")

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info(f"📭 Nenhum dado GEBEX encontrado em `{gebex_file_path}`. Verifique se o arquivo OCOREN existe.")
    st.markdown("</div>", unsafe_allow_html=True)

# ─── TAB: PARÂMETROS ───
with tab_params:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Parâmetros do Sistema")

    st.markdown("""
    <p style="color:#8899b8; font-size:0.85rem;">
        Esta aba reflete os parâmetros da planilha. Edite diretamente na planilha Google Sheets e clique em "Recarregar".
    </p>
    """, unsafe_allow_html=True)

    if st.button("🔄 Recarregar Parâmetros", type="secondary"):
        st.rerun()

    # Braspress block
    st.markdown("""
    <div class="block-config">
        <h4>🚛 Braspress</h4>
    </div>
    """, unsafe_allow_html=True)

    bcols = st.columns([1, 1, 1, 1])
    with bcols[0]:
        st.text_input("CNPJ", value=BR_CNPJ, key="p_cnpj", disabled=True)
    with bcols[1]:
        st.text_input("Usuário", value=BR_USUARIO, key="p_user", disabled=True)
    with bcols[2]:
        st.text_input("Senha", value="****" if BR_SENHA else "", key="p_pass", disabled=True, type="password")
    with bcols[3]:
        st.text_input("API URL", value="https://api.braspress.com", key="p_url", disabled=True)

    st.markdown("<br>", unsafe_allow_html=True)

    pcols = st.columns(2)
    with pcols[0]:
        nfs_str = ", ".join(BR_NFS) if BR_NFS else "(vazio)"
        st.text_area("NFs para Rastrear", value=nfs_str, key="p_nfs", disabled=True, height=80)
    with pcols[1]:
        ped_str = ", ".join(BR_PEDIDOS) if BR_PEDIDOS else "(vazio)"
        st.text_area("Pedidos para Rastrear", value=ped_str, key="p_pedidos", disabled=True, height=80)

    # GEBEX block
    gb_file_exists = os.path.exists(gebex_file_path)
    gb_status = "✅ Ativo (arquivo local)" if gb_file_exists else "⏳ Aguardando arquivo OCOREN"
    gb_color = "#27ae60" if gb_file_exists else "#f39c12"
    st.markdown(f"""
    <br>
    <div class="block-config">
        <h4>📦 GEBEX</h4>
        <p class="param">Status: <span style="color:{gb_color};">{gb_status}</span></p>
        <p class="param">Arquivo: <span>{gebex_file_path}</span></p>
        <p class="param">NFs: <span>{len(df_gb)}</span></p>
    </div>
    """, unsafe_allow_html=True)
    gcols = st.columns(3)
    with gcols[0]:
        st.text_input("Servidor FTP", value="", key="p_ftp", disabled=True, placeholder="Em breve")
    with gcols[1]:
        st.text_input("Usuário FTP", value="", key="p_ftp_user", disabled=True, placeholder="Em breve")
    with gcols[2]:
        st.text_input("Senha FTP", type="password", value="", key="p_ftp_pass", disabled=True, placeholder="Em breve")

    # DHL block
    st.markdown("""
    <br>
    <div class="block-config">
        <h4>📦 DHL</h4>
        <p class="param">Status: <span style="color:#f39c12;">⏳ A implementar</span></p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ─── TAB: DADOS EXPORTÁVEIS ───
with tab_export:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📋 Dados Exportáveis")

    ed_tabs = st.tabs(["📋 Braspress", "📦 GEBEX", "📦 DHL"])
    with ed_tabs[0]:
        if not df_br.empty:
            st.caption(f"{len(df_br)} registros")
            search_ed = st.text_input("🔎 Buscar", placeholder="Digite para filtrar...", key="ed_search_br")
            df_ed = df_br.copy()
            if search_ed:
                mask = df_ed.astype(str).apply(lambda row: row.str.contains(search_ed, case=False, na=False)).any(axis=1)
                df_ed = df_ed[mask]
            for c in df_ed.select_dtypes(include=["datetime64"]).columns:
                df_ed[c] = df_ed[c].dt.strftime("%d/%m/%Y")
            st.dataframe(df_ed, use_container_width=True, hide_index=True, height=450)

            ex1, ex2, ex3 = st.columns(3)
            csv_ed = df_ed.to_csv(index=False).encode("utf-8-sig")
            ex1.download_button("📥 CSV", csv_ed, f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="dl_br_csv", use_container_width=True)
            output_ed = io.BytesIO()
            with pd.ExcelWriter(output_ed, engine="openpyxl") as w:
                df_ed.to_excel(w, index=False, sheet_name="Braspress")
            ex2.download_button("📥 Excel", output_ed.getvalue(), f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_br_xlsx", use_container_width=True)
            ex3.download_button("📥 JSON", df_ed.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8-sig"), f"braspress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json", key="dl_br_json", use_container_width=True)
        else:
            st.info("Nenhum dado disponível.")
    with ed_tabs[1]:
        if not df_gb.empty:
            st.caption(f"{len(df_gb)} registros")
            search_ed_gb = st.text_input("🔎 Buscar", placeholder="Digite para filtrar...", key="ed_search_gb")
            df_ed_gb = df_gb.copy()
            if "dataOcorrencia" in df_ed_gb.columns:
                df_ed_gb["dataOcorrencia"] = df_ed_gb["dataOcorrencia"].apply(lambda x: str(x)[:10] if pd.notna(x) else "")
            if "emissao" in df_ed_gb.columns:
                df_ed_gb["emissao"] = df_ed_gb["emissao"].apply(lambda x: str(x)[:10] if pd.notna(x) else "")
            if search_ed_gb:
                mask = df_ed_gb.astype(str).apply(lambda row: row.str.contains(search_ed_gb, case=False, na=False)).any(axis=1)
                df_ed_gb = df_ed_gb[mask]
            st.dataframe(df_ed_gb, use_container_width=True, hide_index=True, height=450)
            egx1, egx2, egx3 = st.columns(3)
            csv_ed_gb = df_ed_gb.to_csv(index=False).encode("utf-8-sig")
            egx1.download_button("📥 CSV", csv_ed_gb, f"gebex_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="dl_gb_csv", use_container_width=True)
            output_ed_gb = io.BytesIO()
            with pd.ExcelWriter(output_ed_gb, engine="openpyxl") as w:
                df_ed_gb.to_excel(w, index=False, sheet_name="GEBEX")
            egx2.download_button("📥 Excel", output_ed_gb.getvalue(), f"gebex_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_gb_xlsx", use_container_width=True)
            egx3.download_button("📥 JSON", df_ed_gb.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8-sig"), f"gebex_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json", key="dl_gb_json", use_container_width=True)
        else:
            st.info("📦 GEBEX - Aguardando dados do arquivo OCOREN.")
    with ed_tabs[2]:
        st.info("📦 DHL - Aguardando configuração.")
    st.markdown("</div>", unsafe_allow_html=True)

# ─── FOOTER ───
st.sidebar.markdown("---")
st.sidebar.markdown('<div style="background:#16233a; border:1px solid #253e81; border-radius:10px; padding:0.7rem 1rem; margin-bottom:0.8rem;">'
    '<p style="margin:0; font-size:12px; font-style:italic; color:#ffd700; line-height:1.6;">'
    'Desenvolvido por <b>Rogerio Penha</b><br>'
    'rogeriopenha@gmail.com<br>'
    "(016)99798-2392<br>"
    'versão: 1.0 beta<br>'
    'Data: 07/07/2026'
    '</p></div>', unsafe_allow_html=True)
