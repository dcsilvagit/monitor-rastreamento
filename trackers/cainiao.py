import re
import urllib.parse
import requests
from .anjun import track_anjun


def extrair_cidade_destino(code: str, headers: dict) -> str:
    """
    Consulta o endpoint getCity da Cainiao para obter o nome da cidade de destino final.
    Exemplo: retorna 'Belo+Horizonte' -> decodifica para 'Belo Horizonte'.
    """
    try:
        url = f"https://global.cainiao.com/global/getCity.json?mailNo={code}&lang=pt-BR"
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            payload = resp.json()
            raw_city = payload.get("module") or ""
            if raw_city:
                return urllib.parse.unquote_plus(raw_city).strip()
    except Exception:
        pass
    return ""


def extrair_localizacao_cainiao(item_module: dict, evento: dict, dest_city: str = "") -> str:
    """
    Extrai cidade e país do evento de rastreamento do AliExpress/Cainiao.
    Se o pacote já chegou ao Brasil, prioriza a cidade de destino se identificada.
    """
    dest_country = item_module.get("destCountry") or "Brasil"
    orig_country = item_module.get("originCountry") or "China"

    tz = evento.get("timeZone", "")
    desc = (
        evento.get("standerdDesc")
        or evento.get("desc")
        or item_module.get("statusDesc", "")
    )

    # Identifica se o pacote já está em solo brasileiro
    no_brasil = ("GMT-3" in tz or "-03" in tz or "Brasil" in desc or "país/região de trânsito" in desc)

    if no_brasil:
        # Se temos a cidade de destino confirmada (ex: Belo Horizonte)
        if dest_city:
            return f"{dest_city} ({dest_country})"

        # Procura formato de cidade e estado brasileiro Cidade/UF no texto
        match_uf = re.search(
            r"\b([A-Z][a-zÀ-ÿ]+(?:\s+[A-Z][a-zÀ-ÿ]+)*)/(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b",
            desc,
        )
        if match_uf:
            return f"{match_uf.group(1).strip()} - {match_uf.group(2)} ({dest_country})"

        return dest_country

    # Ainda no exterior / país de origem
    match_bracket = re.search(r"\[([A-Za-zÀ-ÿ\s/]+)\]", desc)
    if match_bracket:
        cidade = match_bracket.group(1).strip()
        return f"{cidade} ({orig_country})"

    return orig_country


def track_cainiao(tracking_code: str) -> dict:
    """
    Rastreia pacotes do AliExpress / Cainiao / Anjun.
    Identifica automaticamente a transportadora da última milha (ex: Correios BR)
    e a cidade de destino no Brasil.
    """
    code = tracking_code.strip().upper()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    # 1. Obtém cidade de destino final no Brasil se disponível
    cidade_destino = extrair_cidade_destino(code, headers)

    # 2. Obtém histórico de rastreamento completo
    url = f"https://global.cainiao.com/global/detail.json?mailNos={code}&lang=pt-BR"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            payload = response.json()
            modules = payload.get("module", [])
            if modules:
                item = modules[0]
                status_desc = item.get("statusDesc") or "Em transporte"

                # Identifica a transportadora parceira da última milha (ex: Correios BR)
                cp_info = (
                    item.get("globalCombinedLogisticsTraceDTO", {}).get("currentStatusCpInfo", {})
                    or {}
                )
                cp_name = cp_info.get("cpName", "")

                if "correios" in cp_name.lower():
                    transportadora = "Correios (BR) / AliExpress"
                elif cp_name:
                    transportadora = f"{cp_name} / AliExpress"
                else:
                    transportadora = "AliExpress (Cainiao)"

                # Obtém o evento mais recente
                latest = item.get("latestTrace")
                if not latest:
                    detail_list = item.get("detailList", [])
                    if detail_list:
                        latest = detail_list[0]

                if latest:
                    data_hora = latest.get("timeStr", "N/D")
                    detalhes_base = latest.get("standerdDesc") or latest.get("desc") or status_desc
                    localizacao = extrair_localizacao_cainiao(item, latest, dest_city=cidade_destino)

                    # Se a última milha for pela Anjun Express, verifica se há rastreamento mais detalhado no Brasil
                    eh_anjun = "anjun" in cp_name.lower() or "anjun" in (cp_info.get("url") or "").lower()
                    if eh_anjun:
                        res_anjun = track_anjun(code)
                        if res_anjun.get("sucesso"):
                            anjun_data = res_anjun.get("data_hora", "")
                            if not data_hora or anjun_data >= data_hora:
                                return {
                                    "codigo": code,
                                    "transportadora": "Anjun Express / AliExpress",
                                    "status": res_anjun["status"],
                                    "data_hora": anjun_data,
                                    "detalhes": f"{res_anjun['detalhes']} (Rastreamento Anjun Express Brasil)",
                                    "local": res_anjun["local"] or (f"{cidade_destino} (Brasil)" if cidade_destino else "Brasil"),
                                    "link": res_anjun["link"],
                                    "sucesso": True,
                                }

                    detalhes = detalhes_base
                    if cp_name:
                        detalhes = f"{detalhes_base} (Última milha por {cp_name})"

                    link_rastreio = cp_info.get("url") or (
                        f"https://rastreamento.correios.com.br/app/index.php"
                        if "correios" in cp_name.lower()
                        else (
                            f"https://anjunexpress.com/trackPackage?tracking={code}"
                            if eh_anjun
                            else f"https://global.cainiao.com/newDetail.htm?mailNoList={code}"
                        )
                    )

                    return {
                        "codigo": code,
                        "transportadora": transportadora,
                        "status": status_desc,
                        "data_hora": data_hora,
                        "detalhes": detalhes,
                        "local": localizacao,
                        "link": link_rastreio,
                        "sucesso": True,
                    }

        # Fallback: Se não encontrou na Cainiao, tenta consultar na Anjun
        res_anjun = track_anjun(code)
        if res_anjun.get("sucesso"):
            return res_anjun

        return {
            "codigo": code,
            "transportadora": "AliExpress (Cainiao)",
            "status": "Não encontrado",
            "data_hora": "-",
            "detalhes": "Nenhum evento registrado ainda",
            "local": "-",
            "sucesso": False,
        }
    except Exception as e:
        # Fallback também em caso de erro na Cainiao
        try:
            res_anjun = track_anjun(code)
            if res_anjun.get("sucesso"):
                return res_anjun
        except Exception:
            pass

        return {
            "codigo": code,
            "transportadora": "AliExpress (Cainiao)",
            "status": "Erro na consulta",
            "data_hora": "-",
            "detalhes": str(e),
            "local": "-",
            "sucesso": False,
        }

