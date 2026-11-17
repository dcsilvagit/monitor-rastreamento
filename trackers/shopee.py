import hashlib
import time
import re
from datetime import datetime
import requests


def extrair_localizacao_shopee(mensagem: str) -> str:
    """
    Extrai cidade, estado e país da mensagem de rastreamento do SPX Express.
    Exemplo: '[LM Hub_MG_Belo Horizonte_02] ...' -> 'Belo Horizonte - MG (Brasil)'
    """
    if not mensagem:
        return "Brasil"

    match = re.search(r"\[(?:[A-Za-z\s]+_)?([A-Z]{2})_([^\]]+)\]", mensagem)
    if match:
        uf = match.group(1)
        cidade_raw = match.group(2)
        cidade = re.sub(r"_\d+$", "", cidade_raw).replace("_", " ").strip()
        return f"{cidade} - {uf} (Brasil)"

    match_simples = re.search(r"\[([A-Za-zÀ-ÿ\s]+)\]", mensagem)
    if match_simples:
        return f"{match_simples.group(1).strip()} (Brasil)"

    return "Brasil"


def track_shopee(tracking_code: str) -> dict:
    """
    Rastreia pacotes da Shopee (SPX Express).
    Gera a assinatura dinâmica exigida pela API do SPX e extrai a localização.
    """
    code = tracking_code.strip().upper()
    timestamp = int(time.time())
    secret = "MGViZmZmZTYzZDJhNDgxY2Y1N2ZlN2Q1ZWJkYzlmZDY="

    # Cálculo da assinatura de segurança do SPX
    signature = hashlib.sha256(f"{code}{timestamp}{secret}".encode("utf-8")).hexdigest()
    sls_param = f"{code}|{timestamp}{signature}"

    url = f"https://spx.com.br/api/v2/fleet_order/tracking/search?sls_tracking_number={sls_param}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-language": "pt-BR",
        "Referer": f"https://spx.com.br/track?{code}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            payload = response.json()
            data = payload.get("data", {})
            logs = data.get("tracking_list", [])

            if logs:
                ultimo_evento = logs[0]
                evento_ts = ultimo_evento.get("timestamp")
                data_hora = (
                    datetime.fromtimestamp(evento_ts).strftime("%d/%m/%Y %H:%M")
                    if evento_ts
                    else "N/D"
                )
                mensagem = ultimo_evento.get("message", "")
                localizacao = extrair_localizacao_shopee(mensagem)

                return {
                    "codigo": code,
                    "transportadora": "Shopee (SPX)",
                    "status": ultimo_evento.get("status", data.get("current_status", "Desconhecido")),
                    "data_hora": data_hora,
                    "detalhes": mensagem,
                    "local": localizacao,
                    "link": f"https://spx.com.br/track?{code}",
                    "sucesso": True,
                }
            elif data.get("current_status"):
                return {
                    "codigo": code,
                    "transportadora": "Shopee (SPX)",
                    "status": data.get("current_status"),
                    "data_hora": "N/D",
                    "detalhes": "Sem histórico detalhado disponível",
                    "local": "Brasil",
                    "link": f"https://spx.com.br/track?{code}",
                    "sucesso": True,
                }

        return {
            "codigo": code,
            "transportadora": "Shopee (SPX)",
            "status": "Não encontrado",
            "data_hora": "-",
            "detalhes": "Nenhum registro encontrado no SPX Express",
            "local": "-",
            "sucesso": False,
        }
    except Exception as e:
        return {
            "codigo": code,
            "transportadora": "Shopee (SPX)",
            "status": "Erro na consulta",
            "data_hora": "-",
            "detalhes": str(e),
            "local": "-",
            "sucesso": False,
        }
