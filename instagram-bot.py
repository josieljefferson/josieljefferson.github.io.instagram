from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes
)
import time
import sys
import os
from datetime import datetime

# =========================
# ⚙️ CONFIGURAÇÕES POR VARIÁVEIS DE AMBIENTE
# =========================
USERNAME = os.environ.get('INSTAGRAM_USERNAME')
PASSWORD = os.environ.get('INSTAGRAM_PASSWORD')

if not USERNAME or not PASSWORD:
    print("❌ Erro: Variáveis de ambiente INSTAGRAM_USERNAME e INSTAGRAM_PASSWORD não definidas")
    print("💡 Configure no seu CI/CD (GitHub: Settings → Secrets → Actions)")
    sys.exit(1)

# Limites e tempos (com valores padrão)
MAX_UNFOLLOWS = int(os.environ.get('MAX_UNFOLLOWS', 50))
SLEEP_BETWEEN_ACTIONS = int(os.environ.get('SLEEP_BETWEEN_ACTIONS', 15))
DELAY_BETWEEN_SESSIONS = int(os.environ.get('DELAY_BETWEEN_SESSIONS', 86400))  # 24h

SESSION_FILE = os.environ.get('INSTAGRAM_SESSION_FILE', 'session.json')

# =========================
# 📝 LOGGING MELHORADO
# =========================
def log_message(message: str):
    """Imprime mensagem com data/hora e salva em arquivo de log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)

    with open("instagram_bot.log", "a", encoding="utf-8") as log_file:
        log_file.write(line + "
")

# =========================
# 🚀 CONFIGURAÇÃO DO CLIENTE
# =========================
def create_client() -> Client:
    """
    Cria e configura o cliente Instagrapi simulando um dispositivo Android estável.
    Isso ajuda a reduzir bloqueios e erros de sessão/CSRF.
    """
    cl = Client()

    # Intervalo de atraso entre requisições (random dentro do range)
    cl.delay_range = [SLEEP_BETWEEN_ACTIONS - 5, SLEEP_BETWEEN_ACTIONS + 5]

    # User-Agent parecido com app do Instagram Android
    cl.set_user_agent(
        "Instagram 261.0.0.21.111 Android (30/11; 420dpi; 1080x2088; "
        "samsung; SM-G973F; beyond1; exynos9820; pt_BR; 432024009)"
    )

    # Dispositivo Android "fixo" (para não parecer um aparelho novo a cada login)
    cl.set_device({
        "manufacturer": "samsung",
        "model": "SM-G973F",
        "android_version": 30,
        "android_release": "11.0"
    })

    # Se estiver em CI, opcionalmente usar proxy (residencial) se fornecido
    if os.environ.get('CI'):
        proxy = os.environ.get('INSTAGRAM_PROXY', '')
        if proxy:
            cl.set_proxy(proxy)

    return cl

# =========================
# 🔐 LOGIN COM USO DE SESSÃO
# =========================
def login_with_session(cl: Client, username: str, password: str):
    """
    Tenta login usando sessão salva (session.json).
    Se a sessão estiver inválida ou não existir, faz login novo e salva.
    Esse fluxo segue as boas práticas recomendadas pelo Instagrapi.
    """
    try:
        if os.path.exists(SESSION_FILE):
            log_message(f"📂 Carregando sessão de {SESSION_FILE}")
            cl.load_settings(SESSION_FILE)

            try:
                # Login usando sessão; a lib reaproveita cookies e tokens
                cl.login(username, password)
                # Testa se sessão realmente está válida
                cl.get_timeline_feed()
                log_message("✅ Login via sessão existente concluído com sucesso")
                return
            except LoginRequired:
                log_message("⚠️ Sessão inválida, será feito novo login com usuário e senha")

        # Se chegou aqui, sessão não existe ou é inválida → login novo
        cl.set_settings({})  # limpa configurações velhas
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        log_message("✅ Novo login realizado e sessão salva")

    except ChallengeRequired as e:
        log_message(f"⚠️ ChallengeRequired (desafio de segurança / 2FA): {e}")
        # Em ambiente CI, não há como digitar 2FA manualmente.
        # Recomendado: gerar SESSION_FILE localmente e enviar pronto ao CI.
        raise

    except Exception as e:
        log_message(f"❌ Erro no login: {e}")
        raise

# =========================
# 🧹 FUNÇÃO DE UNFOLLOW
# =========================
def perform_unfollows(cl: Client):
    """
    Lê seguidores e seguindo, identifica quem não segue de volta e faz unfollow
    respeitando o limite diário e pausas entre ações.
    """
    log_message("📥 Obtendo listas de seguidores e seguindo...")

    user_id = cl.user_id
    followers = cl.user_followers(user_id)
    following = cl.user_following(user_id)

    log_message(f"✅ Seguidores: {len(followers)} | Seguindo: {len(following)}")

    followers_ids = set(followers.keys())
    following_ids = set(following.keys())
    non_followers_ids = following_ids - followers_ids

    log_message(f"🔎 {len(non_followers_ids)} contas não te seguem de volta")

    if not non_followers_ids:
        log_message("✅ Nenhum unfollow necessário")
        return

    max_unfollows = min(MAX_UNFOLLOWS, len(non_followers_ids))
    log_message(f"🚀 Iniciando até {max_unfollows} unfollows...")

    count = 0

    for uid in list(non_followers_ids)[:max_unfollows]:
        try:
            user = following[uid]
            cl.user_unfollow(user.pk)
            count += 1

            log_message(f"❌ Deixou de seguir: @{user.username} ({count}/{max_unfollows})")

            # Pausa entre ações (já existe delay interno, mas aqui reforça)
            time.sleep(SLEEP_BETWEEN_ACTIONS)

        except PleaseWaitFewMinutes as e:
            log_message(f"⏳ Instagram pediu pausa: {e}")
            time.sleep(300)  # 5 minutos
            continue

        except FeedbackRequired as e:
            log_message(f"🚫 FeedbackRequired (possível bloqueio temporário): {e}")
            break  # parar para não piorar o bloqueio

        except Exception as e:
            log_message(f"⚠️ Erro ao dar unfollow: {e}")
            time.sleep(30)
            continue

    log_message(f"✅ Concluído! {count} unfollows realizados")

# =========================
# 🚀 FUNÇÃO PRINCIPAL
# =========================
def main():
    log_message("🚀 Iniciando bot do Instagram")

    try:
        cl = create_client()

        log_message("🔐 Efetuando login...")
        login_with_session(cl, USERNAME, PASSWORD)

        perform_unfollows(cl)

        # Salva sessão atualizada (cookies, tokens, etc.)
        cl.dump_settings(SESSION_FILE)
        log_message("💾 Sessão atualizada salva com sucesso")

    except Exception as e:
        log_message(f"❌ Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
