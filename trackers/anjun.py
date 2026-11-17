import base64
import os
import re
import requests
from datetime import datetime, timezone, timedelta

# Chave pública RSA da Anjun Express (extraída do bundle oficial Nuxt)
# Modulus (1024 bits) e Exponente 65537
ANJUN_RSA_N = 0xcca6457f1145f7e4ba79ed8680277e034dcee729f0e3cc25ffbe301da88e7b09069da0c0c1ce7f816ca90b11b1b8e43e76235928da02cc100feba58fea430d7ee26be2bc1025ebcab749477f73d1e7aa166328677f7dcb0b9de6cc0e7b3465e1b7df5ab4acd126c21641e201b08f334c2d0d6756dd584902e8b20578b74f0fd3
ANJUN_RSA_E = 65537


def _gerar_token_anjun() -> str:
    """
    Gera o token de autenticação da Anjun Express.
    O token é o horário atual de Pequim (UTC+8) no formato 'YYYY-MM-DD HH:mm:ss',
    criptografado com RSA PKCS#1 v1.5 (implementação pura em Python, sem dependências externas).
    """
    now_beijing = datetime.now(timezone(timedelta(hours=8)))
    ts_str = now_beijing.strftime("%Y-%m-%d %H:%M:%S")

    msg_bytes = ts_str.encode("utf-8")
    k = 128  # 1024 bits / 8
    ps_len = k - 3 - len(msg_bytes)

    # Preenchimento pseudo-aleatório não nulo (PKCS#1 v1.5 block type 2)
    ps = bytearray()
    while len(ps) < ps_len:
        b = os.urandom(1)
        if b[0] != 0:
            ps.extend(b)

    em = b"\x00\x02" + ps + b"\x00" + msg_bytes
    m_int = int.from_bytes(em, "big")
    c_int = pow(m_int, ANJUN_RSA_E, ANJUN_RSA_N)
    c_bytes = c_int.to_bytes(k, "big")

    return base64.b64encode(c_bytes).decode("ascii")


def extrair_localizacao_anjun(item: dict, latest_node: dict) -> str:
    """
    Extrai a localização geográfica do pacote Anjun.
    Prioriza informações do nó atual (siteName, address) ou destino/origem do pacote.
    """
    site = (latest_node.get("siteName") or "").strip()
    next_site = (latest_node.get("nextSiteName") or "").strip()
    addr = (latest_node.get("address") or "").strip()
    destination = (item.get("destination") or "").strip()
    origin = (item.get("origin") or "").strip()

    # Tenta encontrar formato de Cidade/UF ou Cidade - UF no site ou endereço
    texto_busca = f"{site} {next_site} {addr} {destination}"
    match_uf = re.search(
        r"\b([A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+)*)[/\s-]+(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b",
        texto_busca,
    )
    if match_uf:
        return f"{match_uf.group(1).strip()} - {match_uf.group(2)} (Brasil)"

    if site:
        return f"{site} (Brasil)"
    if destination:
        return f"{destination} (Brasil)" if "brasil" not in destination.lower() else destination
    if origin:
        return origin

    return "Brasil"


def track_anjun(tracking_code: str) -> dict:
    """
    Rastreia pacotes na Anjun Express Brasil / Internacional.
    Endpoint: POST https://track.anjunexpress.com/track/open/website/query
    """
    code = tracking_code.strip().upper()
    url = "https://track.anjunexpress.com/track/open/website/query"

    try:
        token = _gerar_token_anjun()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt",
            "Content-Type": "application/json",
            "token": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        payload = {"trackNos": code}

        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data") or []
            if items:
                item = items[0]
                node_list = item.get("nodeDataList") or []

                if node_list:
                    latest = node_list[0]
                    status = (
                        latest.get("status")
                        or item.get("lastTrackStatus")
                        or "Em transporte"
                    ).strip()
                    data_hora = (latest.get("dateTime") or "").strip()

                    content = (latest.get("content") or "").strip()
                    site_name = (latest.get("siteName") or "").strip()
                    next_site = (latest.get("nextSiteName") or "").strip()

                    detalhes_partes = []
                    if content:
                        detalhes_partes.append(content)
                    if site_name and next_site:
                        detalhes_partes.append(f"[{site_name} ➔ {next_site}]")
                    elif site_name:
                        detalhes_partes.append(f"[{site_name}]")

                    detalhes = " ".join(detalhes_partes) if detalhes_partes else status

                    local = extrair_localizacao_anjun(item, latest)
                    link = f"https://anjunexpress.com/trackPackage?tracking={code}"

                    return {
                        "codigo": code,
                        "transportadora": "Anjun Express",
                        "status": status,
                        "data_hora": data_hora,
                        "detalhes": detalhes,
                        "local": local,
                        "link": link,
                        "sucesso": True,
                        "eventos": node_list,
                    }

        return {
            "codigo": code,
            "transportadora": "Anjun Express",
            "status": "Não encontrado",
            "data_hora": "-",
            "detalhes": "Nenhum evento registrado na Anjun Express",
            "local": "-",
            "sucesso": False,
        }
    except Exception as e:
        return {
            "codigo": code,
            "transportadora": "Anjun Express",
            "status": "Erro na consulta",
            "data_hora": "-",
            "detalhes": str(e),
            "local": "-",
            "sucesso": False,
        }
