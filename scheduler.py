import os, sys, json, re, time, logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "scheduler.log")),
        logging.StreamHandler(),
    ],
)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_PATH = os.path.join(PROJECT_DIR, ".streamlit", "secrets.toml")
SHEET_URL_FILE = os.path.join(PROJECT_DIR, "config_sheet_url.txt")

# ─── HELPERS ───

def load_creds():
    """Lê service account: tenta service_account.json local, depois secrets.toml."""
    sa_local = os.path.join(PROJECT_DIR, "service_account.json")
    if os.path.exists(sa_local):
        with open(sa_local) as f:
            return json.load(f)

    with open(SECRETS_PATH, "r") as f:
        content = f.read()
    m = re.search(r"gcp_service_account_json\s*=\s*'(\{.*\})'", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))

    raise ValueError("Service account nao encontrada (nem local, nem secrets.toml)")

def get_sheet_url():
    """Lê URL da planilha: config_sheet_url.txt (fallback) ou secrets.toml."""
    if os.path.exists(SHEET_URL_FILE):
        with open(SHEET_URL_FILE) as f:
            url = f.read().strip()
            if url:
                return url
    # Fallback: ler do secrets.toml
    with open(SECRETS_PATH, "r") as f:
        content = f.read()
    m = re.search(r'sheet_url\s*=\s*"(https://[^"]+)"', content)
    if m:
        return m.group(1)
    return None

# ─── UPSERT EM BR-CONHECIMENTOS ───

CABECALHOS_BR = [
    "numero", "origem", "emissao", "remetente", "destinatario",
    "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete",
    "previsaoEntrega", "dataEntrega", "status", "cidade", "uf",
    "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
    "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data",
    "data_consulta",
]

def upsert_conhecimentos(ws, novos_dados):
    """Merge em memoria das linhas existentes com novos dados, depois rewrite."""
    indice_numero = CABECALHOS_BR.index("numero")

    # Ler existentes
    existentes = ws.get_all_values()
    mapa = {}
    if len(existentes) > 1:
        for row in existentes[1:]:
            if len(row) > indice_numero and row[indice_numero].strip():
                mapa[row[indice_numero]] = row

    # Merge: novos sobrescrevem ou adicionam
    for item in novos_dados:
        linha = [str(item.get(col, "")) if item.get(col) is not None else "" for col in CABECALHOS_BR]
        num_conhec = item.get("numero", "")
        if num_conhec:
            mapa[num_conhec] = linha

    # Rewrite completo
    ws.clear()
    ws.append_row(CABECALHOS_BR)
    for linha in mapa.values():
        ws.append_row(linha)

    return len(mapa)


# ─── BUSCA BRASPRESS ───

def update_braspress():
    logging.info("Iniciando atualizacao Braspress...")

    creds_dict = load_creds()
    sheet_url = get_sheet_url()
    if not sheet_url:
        logging.error("URL da planilha nao configurada")
        return

    from gsheets_utils import conectar, obter_aba, df_from_ws
    from braspress_api import BraspressAPI, flatten_conhecimentos

    client = conectar(creds_dict)
    sheet = client.open_by_url(sheet_url)

    # Ler Parametros
    ws_params = obter_aba(sheet, "Parametros")
    if not ws_params:
        logging.error("Aba Parametros nao encontrada")
        return

    df_params = df_from_ws(ws_params)
    param_map = {}
    for _, row in df_params.iterrows():
        key = str(row.iloc[0]).strip() if len(row) > 0 else ""
        val = str(row.iloc[1]).strip() if len(row) > 1 else ""
        transp = str(row.iloc[2]).strip() if len(row) > 2 else ""
        if key and transp:
            param_map[f"{transp}|{key}"] = val

    cnpj = param_map.get("Braspress|cnpj", "2323120000236")
    usuario = param_map.get("Braspress|usuario", "2323120000236_PRD")
    senha = param_map.get("Braspress|senha", "J27113flmAih0D8Q")
    nfs = [nf.strip() for nf in param_map.get("Braspress|nfs", "").split(",") if nf.strip()]
    pedidos = [p.strip() for p in param_map.get("Braspress|pedidos", "").split(",") if p.strip()]

    # Fallback: ler BR-NFs
    if not nfs and not pedidos:
        ws_nfs = obter_aba(sheet, "BR-NFs")
        if ws_nfs:
            df_nfs = df_from_ws(ws_nfs)
            if not df_nfs.empty and "NF" in df_nfs.columns:
                nfs = df_nfs["NF"].astype(str).str.strip().tolist()
                logging.info(f"Lidas {len(nfs)} NFs da aba BR-NFs")

    if not nfs and not pedidos:
        logging.warning("Nenhuma NF ou Pedido para rastrear")
        return

    api = BraspressAPI(cnpj, usuario, senha)
    todos = []

    for nf in nfs:
        try:
            data = api.tracking_by_nf(nf)
            rows = flatten_conhecimentos(data)
            todos.extend(rows)
            logging.info(f"NF {nf}: {len(rows)} conhecimentos")
        except Exception as e:
            logging.error(f"Erro NF {nf}: {e}")

    for ped in pedidos:
        try:
            data = api.tracking_by_pedido(ped)
            rows = flatten_conhecimentos(data)
            todos.extend(rows)
            logging.info(f"Pedido {ped}: {len(rows)} conhecimentos")
        except Exception as e:
            logging.error(f"Erro Pedido {ped}: {e}")

    if not todos:
        logging.warning("Nenhum dado retornado da API")
        return

    # Upsert em BR-Conhecimentos
    ws_br = obter_aba(sheet, "BR-Conhecimentos")
    if not ws_br:
        logging.error("Aba BR-Conhecimentos nao encontrada")
        return

    total = upsert_conhecimentos(ws_br, todos)
    logging.info(f"Atualizacao concluida: {total} conhecimentos")


# ─── MAIN ───

def main():
    logging.info("=== Scheduler Painel Transportes ===")

    now = datetime.now()
    hour = now.hour
    allowed = [6, 10, 14, 18, 22]

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        logging.info("Execucao forcada")
    elif hour not in allowed:
        logging.info(f"Hora {hour}:00 nao agendada. Proximas: {allowed}")
        return

    try:
        update_braspress()
        logging.info("OK")
    except Exception as e:
        logging.error(f"Erro: {e}", exc_info=True)


if __name__ == "__main__":
    main()
