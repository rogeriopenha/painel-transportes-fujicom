"""
Backfill de 90 dias: consulta todas as NFs da Braspress e salva na planilha.
Uso: python backfill_braspress.py
"""
import json, re, gspread, os, sys, logging
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTAS_DIR = os.path.join(BASE_DIR, "..", "Fujicom", "BRASPRESS", "notas")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-pWMmfKCr3k4cl50mxyhp08C6qDZSTFlddmJYUpS3CU/edit"

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# ─── Extrair NFs dos nomes dos PDFs ───
def extrair_nfs():
    nfs = []
    if not os.path.isdir(NOTAS_DIR):
        logging.warning(f"Diretorio nao encontrado: {NOTAS_DIR}")
        return nfs

    for fname in sorted(os.listdir(NOTAS_DIR)):
        # "NF 21070 COLSAN INDIANOPOLIS SP 30.06.26.pdf"
        m = re.search(r'NF\s+(\d+)', fname)
        if m:
            nfs.append(m.group(1))
    return nfs

# ─── Conectar planilha ───
def conectar():
    sa_path = os.path.join(BASE_DIR, 'service_account.json')
    secrets_path = os.path.join(BASE_DIR, '.streamlit', 'secrets.toml')

    if os.path.exists(sa_path):
        with open(sa_path) as f:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(json.load(f), SCOPE)
    else:
        with open(secrets_path) as f:
            content = f.read()
        m = re.search(r"gcp_service_account_json\s*=\s*'(\{.*\})'", content, re.DOTALL)
        if not m:
            raise ValueError("Service account nao encontrada")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(m.group(1)), SCOPE)
    return gspread.authorize(creds)

# ─── Upsert em BR-Conhecimentos ───
def upsert_conhecimentos(ws, novos_dados):
    cabecalhos = [
        "numero", "origem", "emissao", "remetente", "destinatario",
        "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete",
        "previsaoEntrega", "dataEntrega", "status", "cidade", "uf",
        "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
        "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data",
        "data_consulta",
    ]

    # Ler dados existentes
    existentes = ws.get_all_values()
    indice_numero = cabecalhos.index("numero")

    mapa_existente = {}
    if len(existentes) > 1:
        for i, row in enumerate(existentes[1:], start=2):
            if len(row) > indice_numero and row[indice_numero].strip():
                mapa_existente[row[indice_numero]] = i

    # Preparar dados novos em formato de linha
    linhas_novas = []
    for item in novos_dados:
        linha = []
        for col in cabecalhos:
            val = item.get(col, "")
            linha.append(str(val) if val is not None else "")
        linhas_novas.append(linha)

    # Upsert
    upsertadas = 0
    adicionadas = 0
    for linha in linhas_novas:
        num_conhec = linha[indice_numero]
        if num_conhec in mapa_existente:
            # Atualizar linha existente
            idx = mapa_existente[num_conhec]
            for j, val in enumerate(linha):
                ws.update_cell(idx, j + 1, val)
            upsertadas += 1
        else:
            # Adicionar ao final
            ws.append_row(linha)
            adicionadas += 1

    logging.info(f"Conhecimentos: {upsertadas} atualizadas, {adicionadas} novas")
    return upsertadas + adicionadas

# ─── Main ───
def main():
    # 1. Extrair NFs
    nfs = extrair_nfs()
    logging.info(f"Encontradas {len(nfs)} NFs: {', '.join(nfs)}")
    if not nfs:
        print("Nenhuma NF encontrada em:", NOTAS_DIR)
        return

    # 2. Conectar planilha
    client = conectar()
    sheet = client.open_by_url(SHEET_URL)

    # 3. Atualizar Parametros com as NFs
    ws_params = sheet.worksheet("Parametros")
    dados = ws_params.get_all_values()
    for i, row in enumerate(dados, start=1):
        if len(row) >= 3 and row[0].strip() == "nfs" and row[2].strip() == "Braspress":
            ws_params.update_cell(i, 2, ",".join(nfs))
            logging.info(f"NFs salvas no Parametros (linha {i})")
            break

    # 4. Criar/atualizar BR-NFs
    try:
        ws_nfs = sheet.worksheet("BR-NFs")
    except:
        ws_nfs = sheet.add_worksheet(title="BR-NFs", rows=100, cols=6)
        ws_nfs.append_row(["NF", "Cliente", "Cidade", "UF", "Data Emissao", "Arquivo"])

    dados_nfs = ws_nfs.get_all_values()
    nfs_existentes = set()
    if len(dados_nfs) > 1:
        for row in dados_nfs[1:]:
            if row and row[0].strip():
                nfs_existentes.add(row[0].strip())

    for fname in sorted(os.listdir(NOTAS_DIR)):
        m = re.search(r'NF\s+(\d+)\s+(.+?)\s+(\d{2}\.\d{2}\.\d{2})\.pdf$', fname)
        if m:
            nf = m.group(1)
            if nf not in nfs_existentes:
                cliente = m.group(2).strip()
                data = m.group(3)
                ws_nfs.append_row([nf, cliente, "", "", data, fname])
                logging.info(f"  BR-NFs + NF {nf} - {cliente}")

    # 5. Consultar API Braspress
    from braspress_api import BraspressAPI, flatten_conhecimentos

    CNPJ = "2323120000236"
    USUARIO = "2323120000236_PRD"
    SENHA = "J27113flmAih0D8Q"

    api = BraspressAPI(CNPJ, USUARIO, SENHA)
    todos = []

    for nf in nfs:
        try:
            data = api.tracking_by_nf(nf)
            rows = flatten_conhecimentos(data)
            todos.extend(rows)
            logging.info(f"  NF {nf}: {len(rows)} conhecimentos")
        except Exception as e:
            logging.warning(f"  NF {nf}: erro - {e}")

    if not todos:
        logging.warning("Nenhum dado retornado da API")
        return

    # 6. Upsert em BR-Conhecimentos
    try:
        ws_br = sheet.worksheet("BR-Conhecimentos")
    except:
        ws_br = sheet.add_worksheet(title="BR-Conhecimentos", rows=100, cols=25)
        cabecalhos = [
            "numero", "origem", "emissao", "remetente", "destinatario",
            "tipoFrete", "volumes", "valorMercantil", "peso", "totalFrete",
            "previsaoEntrega", "dataEntrega", "status", "cidade", "uf",
            "cidadeColeta", "ufColeta", "dataOcorrencia", "ultimaOcorrencia",
            "nf_serie", "nf_numero", "nf_emissao", "ultimo_status", "ultimo_status_data",
            "data_consulta",
        ]
        ws_br.append_row(cabecalhos)

    total = upsert_conhecimentos(ws_br, todos)
    print(f"\nBackfill concluido! {total} conhecimentos salvos em BR-Conhecimentos.")

    # 7. Mostrar sheet final
    print(f"\nPlanilha: {SHEET_URL}")
    print("Abas:")
    for ws in sheet.worksheets():
        print(f"  - {ws.title}")

if __name__ == "__main__":
    main()
