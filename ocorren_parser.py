import re
import os
from datetime import datetime
from typing import Optional

CODIGOS_GBEX = {
    0: "Processo de Transporte ja Iniciado",
    1: "Entrega Realizada Normalmente",
    2: "Entrega Fora da Data Programada",
    3: "Recusa por Falta de Pedido de Compra",
    4: "Recusa por Pedido de Compra Cancelado",
    5: "Falta de Espaco Fisico no Deposito do Cliente",
    6: "Endereco do Cliente nao Localizado",
    7: "Devolucao nao Autorizada pelo Cliente",
    8: "Preco Mercadoria em Desacordo com o Pedido",
    9: "Mercadoria em Desacordo com o Pedido",
    10: "Destinatario so Recebe Mercadoria com Frete Pago",
    11: "Recusa por Deficiencia da Embalagem",
    12: "Redespacho nao Indicado",
    13: "Transportadora nao Atende Cidade Destino",
    14: "Mercadoria Sinistrada",
    15: "Embalagem Sinistrada",
    16: "Pedido de Compra em Duplicidade",
    17: "Embalagem Fora do Padrao",
    18: "Mercadoria Trocada",
    19: "Reentrega Solicitada pelo Cliente",
    20: "Entrega Prejudicada por Horario",
    21: "Cliente Fechado",
    22: "Reentrega sem Cobranca do Cliente",
    23: "Extravio de Mercadoria em Transito",
    24: "Mercadoria Reentregue ao Cliente Destino",
    25: "Mercadoria Devolvida ao Cliente Origem",
    26: "Nota Fiscal Retida pela Fiscalizacao",
    27: "Roubo de Carga",
    28: "Mercadoria Retida ate Segunda Ordem",
    29: "Aguardando Cliente Retirar em Deposito",
    30: "Extravio ou Problemas com Documentos",
    31: "Entrega com Indenizacao Efetuada",
    32: "Falta com Solicitacao de Reposicao",
    33: "Falta de Volume/Mercadoria/Reconferencia",
    34: "Cliente Fechado para Balanco",
    35: "Quantidade de Produtos em Desacordo NF",
    39: "Corte de carga na pista",
    41: "Pedido de Compra Incompleto",
    42: "NF com Produtos de Setores Diferentes",
    43: "Feriado Local/Nacional",
    44: "Excesso de Veiculos",
    45: "Cliente Destino Encerrou Atividades",
    46: "Responsavel do Recebimento Ausente",
    47: "Cliente Destino em Greve",
    50: "Greve Nacional",
    51: "Mercadoria Vencida",
    52: "Mercadoria Redespachada",
    53: "Mercadoria nao foi Embarcada",
    54: "Conhecimento nao Embarcado",
    55: "Endereco do Redespacho nao Informado",
    56: "Cliente nao Aceita Pagamento de Reembolso",
    57: "Nao Atende Cidade da Redespachadora",
    58: "Quebra do Veiculo",
    59: "Cliente sem Verba para Pagar o Frete",
    60: "Endereco de Entrega Errado",
    61: "Cliente sem Verba para Reembolso",
    62: "Recusa da Carga por Valor de Frete Errado",
    63: "Identificacao do Cliente nao Informada",
    65: "Entrar em Contato com o Comprador",
    66: "Troca Nao Disponivel",
    67: "Fins Estatisticos",
    68: "Data de Entrega Diferente do Pedido",
    69: "Substituicao Tributaria",
    70: "Sistema Fora do Ar",
    71: "Cliente Destino nao Recebe Pedido Parcial",
    72: "Cliente Destino so Recebe Pedido Parcial",
    73: "Redespacho somente com Frete Pago",
    74: "Funcionario nao Autorizado a Receber Mercadoria",
    75: "Mercadoria Embarcada para Rota Indevida",
    76: "Estrada/Acesso Interditado",
    77: "Cliente Mudou de Endereco",
    78: "Avaria Total",
    79: "Avaria Parcial",
    80: "Extravio Total",
    81: "Extravio Parcial",
    82: "Sobra de Mercadoria sem Nota Fiscal",
    83: "Mercadoria em poder da SUFRAMA",
    84: "Mercadoria Retirada para Conferencia",
    85: "Apreensao Fiscal da Mercadoria",
    86: "Excesso de Carga/Peso",
    87: "Ferias Coletivas",
    88: "Recusado, aguardando negociacao",
    89: "Aguardando refaturamento das mercadorias",
    90: "Recusado pelo Redespachante",
    91: "Entrega Programada",
    92: "Problemas Fiscais",
    93: "Aguardando carta de correcao",
    94: "Recusa por divergencia nas condicoes de pagamento",
    98: "Chegada na cidade ou filial de destino",
    99: "Outros tipos de ocorrencia nao especificados",
    100: "Devolucao por nao cumprimento do agendamento",
    101: "Devolucao/nao entrega a pedido do embarcador",
    102: "Devolucao/nao entrega a pedido do destinatario",
    103: "Devolucao/nao entrega a pedido transportadora de redespacho",
    104: "Entrega efetuada na Transportadora de Redespacho",
    105: "Entrega efetuada no cliente pela Transportadora de Redespacho",
    107: "Atraso na Liberacao do Posto Fiscal",
    131: "Entrega Realizada - CTE Retido para Conferencia",
    140: "Vicio de Embalagem",
    142: "Sinistro Parcial",
    143: "Sinistro Total",
    146: "Problemas com Frete Negociado",
    151: "Mercadoria Retirada em Deposito",
    155: "Sistema SEFAZ com Instabilidade",
    182: "NF em Analise na Central NFS/UVT",
    183: "NF Liberada na Central NFS/UVT",
    201: "Aguardando Agendamento",
    202: "Chegada na cidade ou filial de transbordo",
    203: "Mercadoria Saiu para Entrega",
    204: "Motorista Chegou no Local de Entrega",
    207: "ICMS Pago, Mercadoria Liberada",
    208: "Destinatario nao Localizado no Endereco",
    211: "TDE (Cremer)",
    212: "Descarga - Cremer",
    213: "Veiculo Dedicado",
    214: "Paletizacao",
    215: "Diaria - Cremer",
    221: "Sistema SEFAZ Instavel - Enchentes RS",
    226: "Em Transferencia entre Filiais",
    245: "Em Devolucao",
    260: "NF em Transferencia para Filial Destino",
    281: "CTE Emitido - Processo Transp Iniciado",
    290: "Entrega somente com Cobranca Extra/Compl",
    291: "Cobranca Extra Autorizada. Entrega Liberada",
    302: "Saida de Unidade",
    303: "Carga em Tratamento na Transportadora",
    308: "Em Transf entre Unidades",
    313: "Pre Baixa - CTE Entregue via Redespacho",
    324: "Nova Previsao de Entrega",
    327: "Malote em Tratamento pela SEFAZ",
    328: "Malote Liberado pela SEFAZ",
    331: "Recusa - Frete",
    333: "Volume com Etiquetamento Errado",
    367: "Aguardando Confirmacao Endereco Correto",
    373: "Carta Correcao Enviada pelo Embarcador",
    393: "Pernoite",
}

class OcorrenParser:
    """
    Parser para arquivo Ocorren (Ocorrencia de Entrega) formato 5.0.
    Layout GBEX - tamanho fixo de 250 caracteres por registro.
    """

    REGISTRO_TAMANHO = 250

    def __init__(self):
        self.transportadora = ""
        self.cnpj_transportadora = ""
        self.remetente = ""
        self.destinatario = ""
        self.data_arquivo = ""
        self.hora_arquivo = ""
        self.ocorrencias: list[dict] = []

    def parse_file(self, filepath: str) -> list[dict]:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self._parse_content(content)

    def parse_text(self, text: str) -> list[dict]:
        return self._parse_content(text)

    def _parse_content(self, content: str) -> list[dict]:
        self.ocorrencias = []
        lines = content.splitlines()
        current_ocorrencia = {}
        current_transportadora = {}

        for line in lines:
            if len(line) < 3:
                continue
            line = line.ljust(self.REGISTRO_TAMANHO)[:self.REGISTRO_TAMANHO]
            tipo = line[:3]

            if tipo == "000":
                self._parse_header(line)
            elif tipo == "540":
                current_transportadora = {}
            elif tipo == "541":
                current_transportadora = self._parse_transportadora(line)
                self.cnpj_transportadora = current_transportadora.get("cnpj", "")
                self.transportadora = current_transportadora.get("razao_social", "")
            elif tipo == "542":
                ocor = self._parse_ocorrencia(line)
                ocor["transportadora"] = self.transportadora
                ocor["cnpj_transportadora"] = self.cnpj_transportadora
                self.ocorrencias.append(ocor)

        return self.ocorrencias

    def _parse_header(self, line: str):
        self.remetente = line[3:38].strip()
        self.destinatario = line[38:73].strip()
        data_raw = line[73:79].strip()
        hora_raw = line[79:83].strip()
        self.data_arquivo = f"{data_raw[:2]}/{data_raw[2:4]}/{data_raw[4:6]}" if len(data_raw) == 6 else ""
        self.hora_arquivo = f"{hora_raw[:2]}:{hora_raw[2:]}" if len(hora_raw) == 4 else ""

    def _parse_transportadora(self, line: str) -> dict:
        return {
            "cnpj": line[3:17].strip(),
            "razao_social": line[17:67].strip(),
        }

    def _parse_ocorrencia(self, line: str) -> dict:
        cnpj_emissor = line[3:17].strip()
        serie_nf = line[17:20].strip()
        numero_nf = line[20:29].strip()
        codigo_raw = line[29:32].strip()
        codigo = int(codigo_raw) if codigo_raw.isdigit() else 0
        data_ocorrencia_raw = line[32:40].strip()
        sequencial = line[40:46].strip()

        return {
            "cnpj_emissor": cnpj_emissor,
            "serie_nf": serie_nf,
            "numero_nf": numero_nf.lstrip("0") or "0",
            "codigo_ocorrencia": codigo,
            "descricao_ocorrencia": CODIGOS_GBEX.get(codigo, f"Codigo {codigo}"),
            "data_ocorrencia": self._format_date(data_ocorrencia_raw),
            "data_ocorrencia_dt": self._parse_date_dt(data_ocorrencia_raw),
            "sequencial": sequencial,
            "texto_complementar": "",
        }

    def _format_date(self, raw: str) -> str:
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:2]}/{raw[2:4]}/{raw[4:]}"
        return raw

    def _parse_date_dt(self, raw: str):
        if len(raw) == 8 and raw.isdigit():
            try:
                return datetime(int(raw[4:8]), int(raw[2:4]), int(raw[:2]))
            except:
                return None
        return None


def agregar_ocorrencias(ocorrencias: list[dict]) -> list[dict]:
    from collections import defaultdict

    nfs: dict[str, list[dict]] = defaultdict(list)
    for ocor in ocorrencias:
        nf = ocor.get("numero_nf", "")
        nfs[nf].append(ocor)

    resultado = []
    for nf, ocor_list in nfs.items():
        ocor_list.sort(key=lambda x: x.get("sequencial", "0"))
        ultima = ocor_list[-1]
        primeira = ocor_list[0]

        def is_entregue(c):
            return c in (1, 24, 104, 105, 131, 313)

        def is_em_transito(c):
            return c in (0, 98, 202, 203, 204, 281, 302, 308, 226, 260)

        ultimo_codigo = ultima.get("codigo_ocorrencia", 0)

        if is_entregue(ultimo_codigo):
            status = "Entregue"
        elif is_em_transito(ultimo_codigo):
            status = "Em Trânsito"
        else:
            status = ultima.get("descricao_ocorrencia", "?")

        resultado.append({
            "nf_numero": nf,
            "status": status,
            "ultimaOcorrencia": ultima.get("descricao_ocorrencia", ""),
            "dataOcorrencia": ultima.get("data_ocorrencia", ""),
            "dataOcorrencia_dt": ultima.get("data_ocorrencia_dt"),
            "dataEmissao": primeira.get("data_ocorrencia", ""),
            "dataEmissao_dt": primeira.get("data_ocorrencia_dt"),
            "codigo_ocorrencia": ultimo_codigo,
            "sequencial": ultima.get("sequencial", ""),
            "transportadora": "GEBEX",
            "cnpj_emissor": ultima.get("cnpj_emissor", ""),
            "serie_nf": ultima.get("serie_nf", ""),
            "ocorrencias": ocor_list,
        })

    resultado.sort(key=lambda x: x.get("dataOcorrencia_dt") or datetime.min, reverse=True)
    return resultado


def processar_arquivo_ocorren(filepath: str, destino_mover: str = None) -> Optional[list[dict]]:
    parser = OcorrenParser()
    ocorrencias = parser.parse_file(filepath)
    agregadas = agregar_ocorrencias(ocorrencias)

    if destino_mover and os.path.exists(filepath):
        import shutil
        basename = os.path.basename(filepath)
        name, ext = os.path.splitext(basename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{name}_processado_{timestamp}{ext}"
        destino = os.path.join(destino_mover, novo_nome)
        shutil.move(filepath, destino)

    return agregadas


def sync_ocorrencias_to_gsheet(ocorrencias: list[dict], ws) -> int:
    headers = ["nf_numero", "status", "ultima_ocorrencia", "data_ocorrencia",
               "data_emissao", "codigo_ocorrencia", "sequencial", "transportadora",
               "cnpj_emissor", "serie_nf"]

    new_rows = []
    for occ in ocorrencias:
        new_rows.append([
            str(occ.get("nf_numero", "")),
            str(occ.get("status", "")),
            str(occ.get("ultimaOcorrencia", "")),
            str(occ.get("dataOcorrencia_dt") or occ.get("dataOcorrencia", "")),
            str(occ.get("dataEmissao_dt") or occ.get("dataEmissao", "")),
            str(occ.get("codigo_ocorrencia", "")),
            str(occ.get("sequencial", "")),
            str(occ.get("transportadora", "")),
            str(occ.get("cnpj_emissor", "")),
            str(occ.get("serie_nf", "")),
        ])

    # Read existing data from sheet
    existing = ws.get_all_values()
    has_header = existing and existing[0] == headers

    if has_header and len(existing) > 1:
        # Build lookup by nf_numero (col 0)
        data_rows = existing[1:]  # skip header
        nf_map = {}
        for i, row in enumerate(data_rows):
            nf = row[0].strip() if row else ""
            if nf:
                nf_map[nf] = i

        # Merge: update existing or append new
        for new_row in new_rows:
            nf = new_row[0].strip()
            if nf in nf_map:
                data_rows[nf_map[nf]] = new_row
            else:
                data_rows.append(new_row)
                if nf:
                    nf_map[nf] = len(data_rows) - 1
    else:
        data_rows = list(new_rows)

    # Single batch write
    ws.clear()
    all_data = [headers] + data_rows
    ws.update(all_data, value_input_option="USER_ENTERED")
    return len(data_rows)
