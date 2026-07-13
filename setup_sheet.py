import json, re, gspread, os
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Read service account JSON from secrets.toml
with open(os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml"), "r") as f:
    secrets_content = f.read()

m = re.search(r"gcp_service_account_json\s*=\s*'(\{.*\})'", secrets_content, re.DOTALL)
if not m:
    print("ERRO: Service account JSON not found in secrets.toml")
    exit(1)

creds_dict = json.loads(m.group(1))

# Authenticate
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
client = gspread.authorize(creds)

# Create new spreadsheet
sheet = client.create("Painel Transportes - Fujicom")
sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet.id}/edit"
print(f"Planilha criada: {sheet_url}")

# Rename default sheet
ws_default = sheet.get_worksheet(0)
ws_default.update_title("Parametros")

# --- Populate Parametros ---
params_headers = ["Parametro", "Valor", "Transportadora", "Grupo", "Descricao"]
ws_params = sheet.worksheet("Parametros")
ws_params.clear()
ws_params.append_row(params_headers)

# Braspress section
br_params = [
    ["cnpj", "2323120000236", "Braspress", "api", "CNPJ do tomador"],
    ["usuario", "2323120000236_PRD", "Braspress", "api", "Usuário API Braspress"],
    ["senha", "J27113flmAih0D8Q", "Braspress", "api", "Senha API Braspress"],
    ["api_url", "https://api.braspress.com", "Braspress", "api", "URL base da API"],
    ["nfs", "", "Braspress", "tracking", "NFs para rastrear (separadas por vírgula)"],
    ["pedidos", "", "Braspress", "tracking", "Nº Pedidos para rastrear (separados por vírgula)"],
]
for p in br_params:
    ws_params.append_row(p)

# Gbex section (FTP)
gb_params = [
    ["ftp_server", "", "Gbex", "ftp", "Servidor FTP GEBEX"],
    ["ftp_user", "", "Gbex", "ftp", "Usuário FTP GEBEX"],
    ["ftp_pass", "", "Gbex", "ftp", "Senha FTP GEBEX"],
    ["ftp_path", "/", "Gbex", "ftp", "Diretório raiz no FTP"],
    ["ftp_ocoren_pattern", "OCOREN*.TXT", "Gbex", "ftp", "Padrão do arquivo OCOREN"],
    ["ftp_conemb_pattern", "CONEMB*.TXT", "Gbex", "ftp", "Padrão do arquivo CONEMB"],
    ["layout_versao", "5.0", "Gbex", "ftp", "Versão do layout Ocorren/Conemb"],
]
for p in gb_params:
    ws_params.append_row(p)

# DHL section (API)
dh_params = [
    ["api_key", "", "DHL", "api", "Chave da API DHL"],
    ["api_url", "", "DHL", "api", "URL base da API DHL"],
]
for p in dh_params:
    ws_params.append_row(p)

# LATAM section (API)
la_params = [
    ["cnpj", "", "LATAM", "api", "CNPJ do tomador"],
    ["usuario", "", "LATAM", "api", "Usuário API LATAM"],
    ["senha", "", "LATAM", "api", "Senha API LATAM"],
    ["api_key", "", "LATAM", "api", "Chave da API LATAM"],
    ["api_url", "", "LATAM", "api", "URL base da API LATAM"],
]
for p in la_params:
    ws_params.append_row(p)

# --- Create BR-Conhecimentos ---
br_headers = [
    "numero", "origem", "emissao", "remetente", "destinatario",
    "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete",
    "previsaoEntrega", "dataEntrega", "status", "cidade", "uf",
    "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
    "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data",
    "data_consulta"
]
ws_br = sheet.add_worksheet(title="BR-Conhecimentos", rows=100, cols=len(br_headers))
ws_br.append_row(br_headers)

# --- Create BR-NFs (for manual NF entry) ---
ws_nfs = sheet.add_worksheet(title="BR-NFs", rows=100, cols=6)
ws_nfs.append_row(["NF", "Serie", "Cliente", "Cidade", "UF", "Data Emissao"])

# --- Create BR-Pedidos (for manual order entry) ---
ws_ped = sheet.add_worksheet(title="BR-Pedidos", rows=100, cols=3)
ws_ped.append_row(["Pedido", "Cliente", "Observacao"])

# --- Create GB-Ocorrencias for GEBEX ---
gb_headers = [
    "cnpj_emissor", "serie_nf", "numero_nf", "data_emissao",
    "codigo_ocorrencia", "descricao_ocorrencia", "data_ocorrencia",
    "cidade", "uf", "numero_conhecimento", "data_arquivo"
]
ws_gb = sheet.add_worksheet(title="GB-Ocorrencias", rows=100, cols=len(gb_headers))
ws_gb.append_row(gb_headers)

print("Abas criadas:")
for ws in sheet.worksheets():
    print(f"  - {ws.title}")

# Update secrets.toml with the new sheet URL
new_secret = f'\ngcp_service_account_json = \'{m.group(1)}\'\n\nsheet_url_transportes = "{sheet_url}"\n'
with open(os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml"), "a") as f:
    f.write(new_secret)

print(f"\nURL adicionada ao secrets.toml")
print(f"\nAbra a planilha e compartilhe com o email da service account:")
print(f"  {creds_dict['client_email']}")
print(f"  (Role: Editor)")
