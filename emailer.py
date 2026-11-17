import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def str_to_bool(val: str, default: bool = False) -> bool:
    """Converte valores textuais de variáveis de ambiente para booleano."""
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip().lower() in ("true", "1", "t", "yes", "sim")


def gerar_corpo_texto(relatorios: list[dict], motivo: str = "diario") -> str:
    """
    Gera o relatório em formato de texto simples e organizado com cidade/país.
    """
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    linhas = [
        "=" * 55,
        f"     RELATÓRIO DE RASTREAMENTO - {agora}",
        "=" * 55,
        "",
    ]

    total = len(relatorios)
    sucessos = sum(1 for r in relatorios if r.get("sucesso"))
    atualizados = sum(1 for r in relatorios if r.get("atualizado"))

    if motivo == "atualizacao":
        linhas.append("🚨 NOTIFICAÇÃO: Atualização de status detectada!")
        linhas.append(f"Pacotes com novidades: {atualizados} de {total}")
    else:
        linhas.append("📅 RESUMO MATINAL: Status de todas as suas encomendas.")
        linhas.append(f"Total de encomendas: {total} | Consultadas com sucesso: {sucessos}")

    linhas.append("-" * 55)
    linhas.append("")

    for r in relatorios:
        simbolo = "[✓]" if r.get("sucesso") else "[✗]"
        tag_up = " [NOVA ATUALIZAÇÃO!]" if r.get("atualizado") else ""
        linhas.append(f"{simbolo} {r.get('descricao', 'Sem descrição')}{tag_up}")
        linhas.append(f"    Código        : {r.get('codigo')}")
        linhas.append(f"    Transportadora: {r.get('transportadora')}")

        if r.get("atualizado") and r.get("status_antigo"):
            linhas.append(f"    Status Novo   : {r.get('status')}")
            linhas.append(f"    Status Antigo : {r.get('status_antigo')} ({r.get('data_hora_antiga')})")
        else:
            linhas.append(f"    Status        : {r.get('status')}")

        linhas.append(f"    Localização   : {r.get('local', 'Não informada')}")
        linhas.append(f"    Data/Hora     : {r.get('data_hora')}")
        linhas.append(f"    Detalhes      : {r.get('detalhes')}")
        if r.get("link"):
            linhas.append(f"    Rastreamento  : {r.get('link')}")
        linhas.append("-" * 55)

    linhas.append("\nEmail enviado automaticamente pelo seu monitor de rastreamento.")
    return "\n".join(linhas)


def enviar_email(
    relatorios: list[dict],
    host: str = None,
    port: int = 587,
    user: str = None,
    password: str = None,
    destinatario: str = None,
    use_tls: bool = True,
    use_ssl: bool = False,
    remetente: str = None,
    motivo: str = "diario",
) -> bool:
    """
    Envia o relatório por e-mail utilizando qualquer servidor SMTP configurado.
    Suporta TLS (STARTTLS), SSL direto ou conexões sem criptografia.
    """
    remetente_final = remetente or os.getenv("EMAIL_FROM") or os.getenv("EMAIL_REMETENTE") or user
    destinatario_final = destinatario or os.getenv("EMAIL_DESTINATARIO") or user

    if not host or not destinatario_final:
        print("[Aviso] Configurações de SMTP incompletas no .env (EMAIL_HOST ou EMAIL_DESTINATARIO ausente).")
        return False

    agora_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
    if motivo == "atualizacao":
        assunto = f"🔔 [Atualização] Status de Encomendas - {agora_str}"
    else:
        assunto = f"📦 [Relatório Diário] Status das Encomendas - {agora_str}"

    corpo = gerar_corpo_texto(relatorios, motivo=motivo)

    msg = MIMEMultipart()
    msg["From"] = remetente_final
    msg["To"] = destinatario_final
    msg["Subject"] = assunto

    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    try:
        protocolo = "SSL" if use_ssl else ("TLS" if use_tls else "Sem criptografia")
        print(f"\nConectando ao servidor SMTP ({host}:{port} via {protocolo})...")

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        # Autenticação (caso usuário e senha tenham sido informados)
        if user and password:
            server.login(user, password)

        server.send_message(msg)
        server.quit()

        print(f"✓ E-mail ({motivo}) enviado com sucesso para {destinatario_final}!")
        return True
    except Exception as e:
        print(f"✗ Falha ao enviar e-mail: {e}")
        return False
