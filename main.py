import os
import sys
from datetime import datetime

# Garante suporte a UTF-8 no Windows mesmo quando executado em segundo plano
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from trackers.shopee import track_shopee
from trackers.cainiao import track_cainiao
from trackers.anjun import track_anjun
from emailer import enviar_email, str_to_bool

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()


def carregar_pacotes(caminho_arquivo: str = "pacotes.txt") -> list[dict]:
    """
    Lê o arquivo de pacotes suportando o formato com separador '|':
    CODIGO | DESCRICAO | ULTIMO_STATUS | ULTIMA_DATA_HORA | LOCALIDADE
    Também suporta os formatos legados com menos colunas.
    """
    if not os.path.exists(caminho_arquivo):
        print(f"Arquivo '{caminho_arquivo}' não encontrado.")
        return []

    pacotes = []
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue

            if "|" in linha:
                partes = [p.strip() for p in linha.split("|")]
                codigo = partes[0]
                descricao = partes[1] if len(partes) > 1 and partes[1] else "Sem descrição"
                ultimo_status = partes[2] if len(partes) > 2 else ""
                ultima_data_hora = partes[3] if len(partes) > 3 else ""
                ultimo_local = partes[4] if len(partes) > 4 else ""
            else:
                partes = linha.split(maxsplit=1)
                codigo = partes[0].strip()
                descricao = partes[1].strip() if len(partes) > 1 else "Sem descrição"
                ultimo_status = ""
                ultima_data_hora = ""
                ultimo_local = ""

            pacotes.append({
                "codigo": codigo,
                "descricao": descricao,
                "ultimo_status": ultimo_status,
                "ultima_data_hora": ultima_data_hora,
                "ultimo_local": ultimo_local,
            })

    return pacotes


def salvar_pacotes(caminho_arquivo: str, relatorios: list[dict]) -> None:
    """
    Salva os pacotes de volta no arquivo mantendo o formato com separador '|':
    CODIGO | DESCRICAO | ULTIMO_STATUS | ULTIMA_DATA_HORA | LOCALIDADE
    """
    linhas = [
        "# Arquivo de pacotes monitorados",
        "# Formato: CODIGO | DESCRICAO | ULTIMO_STATUS | ULTIMA_DATA_HORA | LOCALIDADE\n",
    ]

    for r in relatorios:
        codigo = r["codigo"]
        descricao = r["descricao"]
        status = r["status"] if r.get("sucesso") else r.get("status_antigo", "")
        data_hora = r["data_hora"] if r.get("sucesso") else r.get("data_hora_antiga", "")
        local = r.get("local", "") if r.get("sucesso") else r.get("local_antigo", "")

        linhas.append(f"{codigo} | {descricao} | {status} | {data_hora} | {local}")

    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def rastrear_pacote(pacote: dict) -> dict:
    """
    Identifica a transportadora adequada, realiza o rastreamento
    e detecta se houve alteração de status/data em relação ao registro anterior.
    """
    codigo = pacote["codigo"]
    desc = pacote["descricao"].lower()

    resultado = None

    # 1. Verificação por dica na descrição
    if "shopee" in desc or "spx" in desc:
        resultado = track_shopee(codigo)
    elif "anjun" in desc:
        resultado = track_anjun(codigo)
        if not resultado.get("sucesso"):
            resultado = track_cainiao(codigo)
    elif "ali" in desc or "cainiao" in desc:
        resultado = track_cainiao(codigo)

    # 2. Heurística pelo formato do código se não identificado pela descrição
    if not resultado or not resultado.get("sucesso"):
        if codigo.startswith("AJ"):
            resultado = track_anjun(codigo)
            if not resultado.get("sucesso"):
                resultado = track_cainiao(codigo)
        elif codigo.startswith("SPX") or (codigo.startswith("BR") and len(codigo) >= 14):
            resultado = track_shopee(codigo)
        else:
            resultado = track_cainiao(codigo)
            if not resultado.get("sucesso"):
                res_anjun = track_anjun(codigo)
                if res_anjun.get("sucesso"):
                    resultado = res_anjun
                else:
                    res_shopee = track_shopee(codigo)
                    if res_shopee.get("sucesso"):
                        resultado = res_shopee

    # Atributos de comparação
    status_antigo = pacote.get("ultimo_status", "").strip()
    data_antiga = pacote.get("ultima_data_hora", "").strip()
    local_antigo = pacote.get("ultimo_local", "").strip()

    status_novo = (resultado.get("status") or "").strip()
    data_nova = (resultado.get("data_hora") or "").strip()

    resultado["descricao"] = pacote["descricao"]
    resultado["status_antigo"] = status_antigo
    resultado["data_hora_antiga"] = data_antiga
    resultado["local_antigo"] = local_antigo

    # Detecta se houve atualização real
    if resultado.get("sucesso"):
        if status_antigo:
            resultado["atualizado"] = (status_novo != status_antigo) or (data_nova != data_antiga)
        else:
            resultado["atualizado"] = True
    else:
        resultado["atualizado"] = False

    return resultado


def main():
    print("==================================================")
    print("        MONITORAMENTO DE RASTREAMENTO            ")
    print("==================================================\n")

    caminho_pacotes = "pacotes.txt"
    pacotes = carregar_pacotes(caminho_pacotes)
    if not pacotes:
        print("Nenhum pacote para rastrear.")
        return

    print(f"Encontrados {len(pacotes)} pacote(s) para verificar.\n")

    relatorios = []
    for item in pacotes:
        print(f"Consultando [{item['codigo']}] - {item['descricao']}...")
        res = rastrear_pacote(item)
        relatorios.append(res)

    # Atualiza o arquivo pacotes.txt com status e localidade
    salvar_pacotes(caminho_pacotes, relatorios)

    print("\n" + "=" * 50)
    print("              RESUMO DO STATUS                    ")
    print("=" * 50)

    for r in relatorios:
        simbolo = "✓" if r["sucesso"] else "✗"
        flag_up = " [NOVO!]" if r.get("atualizado") else ""
        print(f"\n[{simbolo}] {r['descricao']}{flag_up}")
        print(f"    Código        : {r['codigo']}")
        print(f"    Transportadora: {r['transportadora']}")
        print(f"    Status        : {r['status']}")
        print(f"    Localização   : {r.get('local', 'Não informada')}")
        print(f"    Última Atualiz: {r['data_hora']}")
        print(f"    Detalhes      : {r['detalhes']}")

    # Verificação das regras de envio de e-mail
    agora = datetime.now()
    hora_atual = agora.hour
    hoje_str = agora.strftime("%Y-%m-%d")

    arquivo_daily = ".last_daily_report"
    ultimo_daily = ""
    if os.path.exists(arquivo_daily):
        try:
            with open(arquivo_daily, "r", encoding="utf-8") as f:
                ultimo_daily = f.read().strip()
        except Exception:
            pass

    houve_atualizacao = any(r.get("atualizado") for r in relatorios)
    forcar_envio = "--force" in sys.argv

    deve_enviar = False
    motivo_envio = ""

    if forcar_envio:
        deve_enviar = True
        motivo_envio = "diario"
        print("\n[Modo Force] Disparo forçado via argumento de linha de comando.")
    elif hora_atual >= 8 and ultimo_daily != hoje_str:
        deve_enviar = True
        motivo_envio = "diario"
        print(f"\n[Regra 8h+] Primeiro envio diário do dia ({hoje_str}).")
    elif houve_atualizacao:
        deve_enviar = True
        motivo_envio = "atualizacao"
        print("\n[Regra Atualização] Encomenda(s) com status atualizado detectada(s).")
    else:
        print("\n[Info] Nenhuma alteração de status detectada e o resumo das 08h já foi enviado hoje.")
        print("       Nenhum e-mail necessário nesta verificação.")

    # Disparo do e-mail (caso a regra tenha sido satisfeita)
    if deve_enviar:
        host = os.getenv("EMAIL_HOST", "").strip()
        port_str = os.getenv("EMAIL_PORT", "587").strip()
        port = int(port_str) if port_str.isdigit() else 587
        user = os.getenv("EMAIL_HOST_USER", "").strip()
        password = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
        use_tls = str_to_bool(os.getenv("EMAIL_USE_TLS"), default=True)
        use_ssl = str_to_bool(os.getenv("EMAIL_USE_SSL"), default=False)
        destinatario = os.getenv("EMAIL_DESTINATARIO", "").strip()
        remetente = (os.getenv("EMAIL_FROM") or os.getenv("EMAIL_REMETENTE") or "").strip()

        # Fallback para o padrão legado do Gmail se EMAIL_HOST não estiver presente
        if not host and os.getenv("GMAIL_REMETENTE"):
            host = "smtp.gmail.com"
            port = 587
            user = os.getenv("GMAIL_REMETENTE", "").strip()
            password = os.getenv("GMAIL_SENHA_APP", "").strip()
            use_tls = True
            use_ssl = False

        if host:
            enviou = enviar_email(
                relatorios=relatorios,
                host=host,
                port=port,
                user=user,
                password=password,
                destinatario=destinatario,
                use_tls=use_tls,
                use_ssl=use_ssl,
                remetente=remetente,
                motivo=motivo_envio,
            )
            if enviou and motivo_envio == "diario":
                try:
                    with open(arquivo_daily, "w", encoding="utf-8") as f:
                        f.write(hoje_str)
                except Exception as e:
                    print(f"[Aviso] Não foi possível salvar arquivo de controle diário: {e}")
        else:
            print("\n[Nota] Para enviar o e-mail automaticamente, preencha as variáveis de SMTP no arquivo '.env'.")


if __name__ == "__main__":
    main()
