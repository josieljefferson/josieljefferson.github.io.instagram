"""
Script exemplo com instagrapi usando sessão (session.json).

Fluxo:
1. Ler USERNAME e PASSWORD de variáveis de ambiente.
2. Tentar login usando sessão salva (session.json).
3. Se sessão inválida/não existir, fazer login novo e salvar nova sessão.
4. Executar uma ação simples (listar seguidores recentes).
"""

import os
import sys
from datetime import datetime

from instagrapi import Client
from instagrapi.exceptions import LoginRequired


# =========================
# ⚙️ CONFIGURAÇÕES BÁSICAS
# =========================

# Pega usuário e senha do ambiente
USERNAME = os.environ.get("INSTAGRAM_USERNAME")
PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")

# Caminho do arquivo de sessão
SESSION_FILE = os.environ.get("INSTAGRAM_SESSION_FILE", "session.json")


def log(msg: str) -> None:
    """Log simples com timestamp no console."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def create_client() -> Client:
    """Cria o cliente Instagrapi com configuração mínima."""
    cl = Client()

    # Pequeno delay aleatório entre requisições (boa prática)
    cl.delay_range = [1, 3]

    return cl


def login_with_session(cl: Client, username: str, password: str, session_path: str) -> None:
    """
    Faz login usando sessão se existir, senão faz login novo.
    Padrão baseado no guia oficial de boas práticas do instagrapi.[web:31][web:37][web:40]
    """
    # Se tiver arquivo de sessão, tenta usá-lo
    if os.path.exists(session_path):
        log(f"📂 Encontrado arquivo de sessão: {session_path}")
        cl.load_settings(session_path)
        log("🔐 Tentando login usando sessão salva...")

        try:
            # Usa login com sessão (não envia user/pass direto, mas reaproveita cookies)[web:31][web:37]
            cl.login(username, password)

            # Checa se sessão é válida
            cl.get_timeline_feed()
            log("✅ Sessão válida. Login concluído usando session.json")
            return

        except LoginRequired:
            log("⚠️ Sessão inválida ou expirada. Será feito novo login com usuário/senha.")
        except Exception as e:
            log(f"⚠️ Erro ao usar sessão salva: {e}. Tentando login novo.")

    # Se chegou aqui, não tem sessão ou ela é inválida → login “do zero”
    log("🔐 Fazendo login novo com usuário e senha...")
    cl.set_settings({})  # limpa qualquer configuração antiga
    cl.login(username, password)
    cl.dump_settings(session_path)
    log(f"✅ Login novo realizado e sessão salva em {session_path}")


def main():
    # 1. Verifica se USERNAME e PASSWORD foram definidos
    if not USERNAME or not PASSWORD:
        print("❌ Erro: defina as variáveis de ambiente INSTAGRAM_USERNAME e INSTAGRAM_PASSWORD.")
        sys.exit(1)

    log("🚀 Iniciando script Instagrapi com sessão")

    try:
        # 2. Cria cliente
        cl = create_client()

        # 3. Login com uso de sessão
        login_with_session(cl, USERNAME, PASSWORD, SESSION_FILE)

        # 4. AÇÃO DE EXEMPLO: listar 10 últimos seguidores
        log("📥 Buscando seus seguidores mais recentes...")
        user_id = cl.user_id  # ID do usuário logado[web:38]
        followers = cl.user_followers(user_id, amount=10)  # últimos 10 seguidores[web:37]

        log(f"✅ Encontrados {len(followers)} seguidores recentes. Listando:")

        for pk, user in followers.items():
            # user.username / user.full_name são campos básicos do objeto UserShort[web:37]
            log(f"👤 @{user.username}  |  nome: {user.full_name}  |  id: {pk}")

        # 5. Garante que sessão atualizada é salva
        cl.dump_settings(SESSION_FILE)
        log("💾 Sessão atualizada salva com sucesso.")

    except Exception as e:
        log(f"❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
