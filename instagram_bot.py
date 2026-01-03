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

# Verifica se as variáveis de ambiente existem
if not USERNAME or not PASSWORD:
    print("❌ Erro: Variáveis de ambiente INSTAGRAM_USERNAME e INSTAGRAM_PASSWORD não definidas")
    print("💡 Configure no seu CI/CD:")
    print("GitHub: Settings → Secrets → Actions")
    print("GitLab: Settings → CI/CD → Variables")
    sys.exit(1)

MAX_UNFOLLOWS = int(os.environ.get('MAX_UNFOLLOWS', 50))
SLEEP_BETWEEN_ACTIONS = int(os.environ.get('SLEEP_BETWEEN_ACTIONS', 15))
DELAY_BETWEEN_SESSIONS = int(os.environ.get('DELAY_BETWEEN_SESSIONS', 86400))  # 24h

# =========================
# 🚀 CONFIGURAÇÃO DO CLIENTE
# =========================
def create_client():
    cl = Client()
    
    # Configurações para evitar bloqueios
    cl.delay_range = [SLEEP_BETWEEN_ACTIONS - 5, SLEEP_BETWEEN_ACTIONS + 5]
    
    # Configurações do dispositivo (pode precisar ajustar)
    cl.set_user_agent("Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36")
    
    # Desativa verificações se em ambiente CI
    if os.environ.get('CI'):
        cl.set_proxy(os.environ.get('INSTAGRAM_PROXY', ''))
    
    return cl

# =========================
# 📝 LOGGING MELHORADO
# =========================
def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    
    # Salva em arquivo de log (útil para CI/CD)
    with open("instagram_bot.log", "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

# =========================
# 🔐 LOGIN COM RETRY E BACKUP DE SESSÃO
# =========================
def login_with_backup(cl, username, password):
    session_file = "session.json"
    
    try:
        # Tenta carregar sessão salva
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            cl.login(username, password)
            log_message("✅ Login com sessão restaurada")
        else:
            cl.login(username, password)
            cl.dump_settings(session_file)
            log_message("✅ Novo login realizado")
            
    except (ChallengeRequired, LoginRequired) as e:
        log_message(f"⚠️ Desafio necessário: {e}")
        # Tenta login com 2FA se necessário
        cl.challenge_code_handler = lambda username, choice: input("Código 2FA: ")
        cl.login(username, password)
        cl.dump_settings(session_file)
        
    except Exception as e:
        log_message(f"❌ Erro no login: {e}")
        raise

# =========================
# 🚀 FUNÇÃO PRINCIPAL
# =========================
def main():
    log_message("🚀 Iniciando bot do Instagram")
    
    try:
        # Cria e configura cliente
        cl = create_client()
        
        # Login
        log_message("🔐 Efetuando login...")
        login_with_backup(cl, USERNAME, PASSWORD)
        
        # Obtendo dados
        log_message("📥 Obtendo listas...")
        
        user_id = cl.user_id
        followers = cl.user_followers(user_id)
        following = cl.user_following(user_id)
        
        log_message(f"✅ Seguidores: {len(followers)} | Seguindo: {len(following)}")
        
        # Identifica não-seguidores
        followers_ids = set(followers.keys())
        following_ids = set(following.keys())
        non_followers_ids = following_ids - followers_ids
        
        log_message(f"🔎 {len(non_followers_ids)} contas não te seguem de volta")
        
        if not non_followers_ids:
            log_message("✅ Nenhum unfollow necessário")
            return
        
        # Executa unfollows
        count = 0
        max_unfollows = min(MAX_UNFOLLOWS, len(non_followers_ids))
        
        log_message(f"🚀 Iniciando {max_unfollows} unfollows...")
        
        for uid in list(non_followers_ids)[:max_unfollows]:
            try:
                user = following[uid]
                cl.user_unfollow(user.pk)
                count += 1
                
                log_message(f"❌ Deixou de seguir: @{user.username} ({count}/{max_unfollows})")
                
                # Delay entre ações
                time.sleep(SLEEP_BETWEEN_ACTIONS)
                
            except PleaseWaitFewMinutes as e:
                log_message(f"⏳ Pausa solicitada: {e}")
                time.sleep(300)  # 5 minutos
                continue
                
            except Exception as e:
                log_message(f"⚠️ Erro ao unfollow: {e}")
                time.sleep(30)
                continue
        
        log_message(f"✅ Concluído! {count} unfollows realizados")
        
        # Salva sessão
        cl.dump_settings("session.json")
        
    except Exception as e:
        log_message(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
