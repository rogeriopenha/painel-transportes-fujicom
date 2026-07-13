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
SECRETS_PATH = os.path.join(PROJECT_DIR, "..", ".streamlit", "secrets.toml")
SHEET_URL_FILE = os.path.join(PROJECT_DIR, "config_sheet_url.txt")

def load_creds():
    with open(SECRETS_PATH, "r") as f:
        content = f.read()
    m = re.search(r"gcp_service_account_json\s*=\s*'(\{.*\})'", content, re.DOTALL)
    if not m:
        raise ValueError("Service account JSON not found")
    return json.loads(m.group(1))

def get_sheet_url():
    if os.path.exists(SHEET_URL_FILE):
        with open(SHEET_URL_FILE) as f:
            return f.read().strip()
    return None

def update_braspress():
    logging.info("Iniciando atualizacao Braspress...")

    creds_dict = load_creds()
    sheet_url = get_sheet_url()
    if not sheet_url:
        logging.error("Sheet URL not configured")
        return

    from gsheets_utils import conectar, obter_aba, df_from_ws
    from braspress_api import BraspressAPI, flatten_conhecimentos

    client = conectar(creds_dict)
    sheet = client.open_by_url(sheet_url)

    # Read parameters
    ws_params = obter_aba(sheet, "Parametros")
    if not ws_params:
        logging.error("Parametros sheet not found")
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

    if not nfs and not pedidos:
        # Try reading from BR-NFs sheet
        ws_nfs = obter_aba(sheet, "BR-NFs")
        if ws_nfs:
            df_nfs = df_from_ws(ws_nfs)
            if not df_nfs.empty and "NF" in df_nfs.columns:
                nfs = df_nfs["NF"].astype(str).str.strip().tolist()
                logging.info(f"Lidas {len(nfs)} NFs da aba BR-NFs")

            if "Pedido" in df_nfs.columns:
                ped = df_nfs["Pedido"].astype(str).str.strip().tolist()
                pedidos.extend([p for p in ped if p and p.lower() != "nan"])

    if not nfs and not pedidos:
        logging.warning("No NFs or Pedidos to track")
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
        logging.warning("No data returned")
        return

    # Write to BR-Conhecimentos sheet
    ws_br = obter_aba(sheet, "BR-Conhecimentos")
    if not ws_br:
        logging.error("BR-Conhecimentos sheet not found")
        return

    cabecalhos = [
        "numero", "origem", "emissao", "remetente", "destinatario",
        "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete",
        "previsaoEntrega", "dataEntrega", "status", "cidade", "uf",
        "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
        "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data",
        "data_consulta",
    ]

    # Clear and rewrite
    ws_br.clear()
    ws_br.append_row(cabecalhos)
    for row_data in todos:
        ws_br.append_row([str(v) if v is not None else "" for v in row_data.values()])

    logging.info(f"Atualizados {len(todos)} conhecimentos em BR-Conhecimentos")

def main():
    logging.info("=== Scheduler Painel Transportes ===")

    # Check if it's time to run (6, 10, 14, 18, 22)
    now = datetime.now()
    hour = now.hour
    allowed = [6, 10, 14, 18, 22]

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        logging.info("Forced run")
    elif hour not in allowed:
        logging.info(f"Hora {hour}:00 nao agendada. Agendado para: {allowed}")
        return

    try:
        update_braspress()
        logging.info("Atualizacao concluida com sucesso!")
    except Exception as e:
        logging.error(f"Erro na atualizacao: {e}", exc_info=True)

if __name__ == "__main__":
    main()
