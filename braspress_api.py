import requests
import base64
import json
from datetime import datetime
from typing import Optional

class BraspressAPI:
    BASE_URL = "https://api.braspress.com"

    def __init__(self, cnpj: str, usuario: str, senha: str):
        self.cnpj = cnpj
        self.usuario = usuario
        self.senha = senha
        self._auth_header = None

    @property
    def auth_header(self) -> dict:
        if not self._auth_header:
            raw = f"{self.usuario}:{self.senha}"
            encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
            self._auth_header = {"Authorization": f"Basic {encoded}"}
        return self._auth_header

    def tracking_by_nf(self, nota_fiscal: str, versao: int = 3) -> Optional[dict]:
        if versao == 3:
            url = f"{self.BASE_URL}/v3/tracking/byNf/{self.cnpj}/{nota_fiscal}/json"
        elif versao == 2:
            url = f"{self.BASE_URL}/v2/tracking/{self.cnpj}/{nota_fiscal}/json"
        else:
            url = f"{self.BASE_URL}/v1/tracking/{self.cnpj}/{nota_fiscal}/json"

        resp = requests.get(url, headers=self.auth_header, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def tracking_by_pedido(self, num_pedido: str) -> Optional[dict]:
        url = f"{self.BASE_URL}/v3/tracking/byNumPedido/{self.cnpj}/{num_pedido}/json"
        resp = requests.get(url, headers=self.auth_header, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def cotar_frete(self, dados: dict) -> Optional[dict]:
        url = f"{self.BASE_URL}/v1/cotacao/calcular/json"
        headers = {**self.auth_header, "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=dados, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def testar_conexao(self) -> bool:
        try:
            url = f"{self.BASE_URL}/v3/tracking/byNf/{self.cnpj}/99999999/json"
            resp = requests.get(url, headers=self.auth_header, timeout=15)
            return resp.status_code in (200, 404)
        except Exception:
            return False

def flatten_conhecimentos(data: dict) -> list[dict]:
    rows = []
    for doc in data.get("conhecimentos", []):
        row = {
            "numero": doc.get("numero"),
            "origem": doc.get("origem"),
            "emissao": doc.get("emissao"),
            "remetente": doc.get("remetente"),
            "destinatario": doc.get("destinatario"),
            "tipoFrete": doc.get("tipoFrete"),
            "volumes": doc.get("volumes"),
            "valorMercantil": doc.get("valorMercantil"),
            "peso": doc.get("peso"),
            "totalFrete": doc.get("totalFrete"),
            "previsaoEntrega": doc.get("previsaoEntrega"),
            "dataEntrega": doc.get("dataEntrega"),
            "status": doc.get("status"),
            "cidade": doc.get("cidade"),
            "uf": doc.get("uf"),
            "cidadeColeta": doc.get("cidadeColeta"),
            "ufColeta": doc.get("ufColeta"),
            "dataOcorrencia": doc.get("dataOcorrencia"),
            "ultimaOcorrencia": doc.get("ultimaOcorrencia"),
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

        nfs = doc.get("notasFiscais", [])
        row["nf_serie"] = nfs[0].get("serie") if nfs else None
        row["nf_numero"] = nfs[0].get("numero") if nfs else None
        row["nf_emissao"] = nfs[0].get("emissao") if nfs else None

        timeline = doc.get("timeLine", [])
        row["ultimo_status"] = timeline[-1].get("descricao") if timeline else doc.get("ultimaOcorrencia")
        row["ultimo_status_data"] = timeline[-1].get("data") if timeline else doc.get("dataOcorrencia")

        rows.append(row)

    return rows
