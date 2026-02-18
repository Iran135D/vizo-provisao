try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    from google_service import GoogleService
except Exception:
    GoogleService = None
try:
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs
except Exception:
    VoiceSettings = None
    ElevenLabs = None
from flask import Flask, jsonify, request, send_from_directory, send_file
from dotenv import load_dotenv
import os
import json
import logging
import io
import datetime
import sqlite3
import re
try:
    from edge_service import get_edge_audio_bytes, get_available_voices as get_edge_voices
except Exception:
    def get_edge_audio_bytes(*args, **kwargs):
        return b""
    def get_available_voices():
        return [
            {"voice_id": "pt-BR-FranciscaNeural", "name": "Francisca (Neural) - PT-BR", "category": "edge-free"},
            {"voice_id": "pt-BR-AntonioNeural", "name": "Antonio (Neural) - PT-BR", "category": "edge-free"},
            {"voice_id": "pt-PT-RaquelNeural", "name": "Raquel (Neural) - PT-PT", "category": "edge-free"},
            {"voice_id": "pt-PT-DuarteNeural", "name": "Duarte (Neural) - PT-PT", "category": "edge-free"},
            {"voice_id": "en-US-GuyNeural", "name": "Guy (Neural) - EN-US", "category": "edge-free"},
            {"voice_id": "en-US-JennyNeural", "name": "Jenny (Neural) - EN-US", "category": "edge-free"}
        ]
    get_edge_voices = get_available_voices

try:
    import requests
except Exception:
    requests = None

# --- CONFIGURAÇÃO DB ---
DB_NAME = "vizo_chat.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mentor_usage (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                must_change INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                company_name TEXT,
                cnpj TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                chat_uses TEXT,
                channels TEXT,
                volume TEXT,
                integrations TEXT,
                timeline TEXT,
                budget TEXT,
                source TEXT
            )
        ''')
        conn.commit()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            cols = [c[1] for c in cursor.fetchall()]
            if "must_change" not in cols:
                cursor.execute("ALTER TABLE users ADD COLUMN must_change INTEGER DEFAULT 1")
                conn.commit()
    except Exception:
        pass

init_db()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
SETTINGS_FILE = 'voice_settings.json'
CAMPAIGN_SETTINGS_FILE = 'campaign_settings.json'
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@localhost")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE_URL = os.getenv("ZAPI_BASE_URL", "https://api.z-api.io")
ZAPI_ENABLED = bool(ZAPI_INSTANCE_ID and ZAPI_TOKEN)

def _get_env_bool(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

def _read_key_from_file(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                key = f.read().strip()
                if key:
                    return key
    except Exception as e:
        logger.error(f"Não foi possível ler {filepath}: {e}")
    return None

# IA externa: tenta .env e, se vazio, arquivo local "key API.txt"
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or _read_key_from_file("key API.txt")
deepseek_enabled = _get_env_bool("DEEPSEEK_ENABLE", default=bool(deepseek_api_key))
deepseek_available = bool(deepseek_api_key) and deepseek_enabled
deepseek_client = None

def deepseek_chat(messages, max_tokens=1000, model="gemini-1.5-flash", stream=False):
    if not deepseek_available or not deepseek_api_key:
        raise RuntimeError("IA externa não configurada")
    if not requests:
        raise RuntimeError("IA externa requer requests")
    contents = []
    for m in messages:
        role = m.get("role") or "user"
        text = str(m.get("content") or "")
        if not text:
            continue
        if role == "system":
            role_name = "user"
            text = "Instrução do sistema: " + text
        elif role == "assistant":
            role_name = "model"
        else:
            role_name = "user"
        contents.append({
            "role": role_name,
            "parts": [{"text": text}]
        })
    payload = {"contents": contents}
    if max_tokens is not None:
        payload["generationConfig"] = {"maxOutputTokens": max_tokens}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    params = {"key": deepseek_api_key}
    resp = requests.post(url, params=params, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Resposta vazia da API Gemini")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    reply = "".join(texts).strip()
    if not reply:
        raise RuntimeError("Conteúdo vazio na resposta da API Gemini")
    return reply


# Initialize Google Service (Native Path A)
# Nota: O arquivo 'client_secret.json' deve estar presente na raiz.
try:
    google_service = GoogleService()
except Exception as e:
    logger.error(f"Google Service failed to init: {e}")
    google_service = None

# Planilhas e Drive configurados
SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "18VOultWSr7ee1IAxei8poYxMb-EdQKelyXSf6HXxFZE")
KNOWLEDGE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "digite_o_id_da_pasta_aqui")
# Planilha de Contatos do Vizô (padrão para o ID fornecido pelo usuário)
CONTACTS_SHEET_ID = os.getenv("GOOGLE_CONTACTS_SHEET_ID") or "1Imm13AnmD0xjmEowlAGC4qialmFDs-ikW7Y6H4NLojs"


api_key = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=api_key) if (api_key and ElevenLabs) else None

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        else:
            return {
                "provider": "edge_tts",
                "voice_id": "pt-BR-FranciscaNeural",
                "model_id": "eleven_multilingual_v2",
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
                "edge_rate": "+0%",
                "edge_pitch": "+0Hz"
            }
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def load_campaign_settings():
    try:
        if os.path.exists(CAMPAIGN_SETTINGS_FILE):
            with open(CAMPAIGN_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading campaign settings: {e}")
        return {}

def save_campaign_settings(settings):
    try:
        with open(CAMPAIGN_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving campaign settings: {e}")
        return False

# --- Auth helpers ---
import hashlib, secrets, smtplib
from email.message import EmailMessage

def _hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f"{salt}:{digest}"

def _verify_password(stored: str, password: str) -> bool:
    try:
        salt, digest = stored.split(":")
        return hashlib.sha256((salt + password).encode('utf-8')).hexdigest() == digest
    except Exception:
        return False

def _generate_provisional_password(length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def seed_default_user():
    try:
        flag = (os.getenv("SEED_FOUR_HANDS", "1").strip().lower() in ("1","true","yes","on","y"))
        if not flag:
            return
        email = os.getenv("SEED_FOUR_HANDS_EMAIL", "fourhands@provisao.com.br").strip()
        name = os.getenv("SEED_FOUR_HANDS_NAME", "Four Hands").strip() or "Four Hands"
        password = os.getenv("SEED_FOUR_HANDS_PASSWORD", "123456")
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            exists = cursor.fetchone() is not None
            pwd_hash = _hash_password(password)
            if exists:
                cursor.execute("UPDATE users SET name = ?, password_hash = ?, must_change = 0 WHERE email = ?", (name, pwd_hash, email))
            else:
                cursor.execute("INSERT INTO users (email, name, password_hash, must_change) VALUES (?, ?, ?, 0)", (email, name, pwd_hash))

            iran_email = "Iran Lima"
            iran_name = "Iran Lima"
            iran_password = "Iran3791"
            cursor.execute("SELECT email FROM users WHERE email = ?", (iran_email,))
            iran_exists = cursor.fetchone() is not None
            iran_pwd_hash = _hash_password(iran_password)
            if iran_exists:
                cursor.execute("UPDATE users SET name = ?, password_hash = ?, must_change = 0 WHERE email = ?", (iran_name, iran_pwd_hash, iran_email))
            else:
                cursor.execute("INSERT INTO users (email, name, password_hash, must_change) VALUES (?, ?, ?, 0)", (iran_email, iran_name, iran_pwd_hash))

            qd_email = "QD SYN"
            qd_name = "QD SYN"
            qd_password = "QD123"
            cursor.execute("SELECT email FROM users WHERE email = ?", (qd_email,))
            qd_exists = cursor.fetchone() is not None
            qd_pwd_hash = _hash_password(qd_password)
            if qd_exists:
                cursor.execute("UPDATE users SET name = ?, password_hash = ?, must_change = 0 WHERE email = ?", (qd_name, qd_pwd_hash, qd_email))
            else:
                cursor.execute("INSERT INTO users (email, name, password_hash, must_change) VALUES (?, ?, ?, 0)", (qd_email, qd_name, qd_pwd_hash))

            fh_email = "FOURHANDS"
            fh_name = "FOURHANDS"
            fh_password = "Bruneles"
            cursor.execute("SELECT email FROM users WHERE email = ?", (fh_email,))
            fh_exists = cursor.fetchone() is not None
            fh_pwd_hash = _hash_password(fh_password)
            if fh_exists:
                cursor.execute("UPDATE users SET name = ?, password_hash = ?, must_change = 0 WHERE email = ?", (fh_name, fh_pwd_hash, fh_email))
            else:
                cursor.execute("INSERT INTO users (email, name, password_hash, must_change) VALUES (?, ?, ?, 0)", (fh_email, fh_name, fh_pwd_hash))

            conn.commit()
        try:
            if google_service and CONTACTS_SHEET_ID and "digite_o_id" not in CONTACTS_SHEET_ID:
                google_service.add_lead_to_sheets(CONTACTS_SHEET_ID, [
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    name,
                    email,
                    "Seed de usuário",
                    "Criado/Atualizado"
                ], "Página1!A1")
        except Exception as e:
            logger.error(f"Falha ao registrar seed no Sheets: {e}")
        logger.info(f"Seed verificado para usuário {email}")
    except Exception as e:
        logger.error(f"Erro no seed de usuário: {e}")

seed_default_user()
def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        logger.warning("SMTP não configurado. E-mail não enviado.")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail: {e}")
        return False

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/chat')
def chat_page():
    return send_from_directory('.', 'chat.html')

@app.route('/register')
def register_page():
    return send_from_directory('.', 'register.html')

# Default voices fallback in case API fails or key has no list permission
DEFAULT_VOICES = [
    {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "category": "premade", "preview_url": ""},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "category": "premade", "preview_url": ""},
    {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "category": "premade", "preview_url": ""},
    {"voice_id": "VR6AewLTigWg4xSOukaG", "name": "Arnold", "category": "premade", "preview_url": ""},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "category": "premade", "preview_url": ""},
    {"voice_id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi", "category": "premade", "preview_url": ""},
    {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli", "category": "premade", "preview_url": ""},
    {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh", "category": "premade", "preview_url": ""},
    {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "category": "premade", "preview_url": ""},
    {"voice_id": "yoZ06aMxZJJ28mfd3POQ", "name": "Sam", "category": "premade", "preview_url": ""}
]

@app.route('/api/campaigns', methods=['GET', 'POST'])
def handle_campaigns():
    if request.method == 'GET':
        return jsonify(load_campaign_settings())
    
    elif request.method == 'POST':
        new_settings = request.json
        current_settings = load_campaign_settings()
        current_settings.update(new_settings)
        if save_campaign_settings(current_settings):
            return jsonify({"status": "success", "settings": current_settings})
        else:
            return jsonify({"error": "Failed to save campaign settings"}), 500

@app.route('/api/voices', methods=['GET'])
def get_voices():
    all_voices = []
    premium_enabled = bool(client)
    
    # 1. Tentar pegar vozes da ElevenLabs
    if client:
        try:
            response = client.voices.get_all()
            for voice in response.voices:
                all_voices.append({
                    "voice_id": voice.voice_id,
                    "name": f"{voice.name} (ElevenLabs)",
                    "category": voice.category,
                    "preview_url": voice.preview_url,
                    "provider": "elevenlabs",
                    "locked": False
                })
        except Exception as e:
            logger.warning(f"Error fetching ElevenLabs voices: {e}")
            # Se falhar, usa os defaults
            for v in DEFAULT_VOICES:
                v2 = dict(v)
                v2["provider"] = "elevenlabs"
                v2["locked"] = True
                all_voices.append(v2)
    else:
        for v in DEFAULT_VOICES:
            v2 = dict(v)
            v2["provider"] = "elevenlabs"
            v2["locked"] = True
            all_voices.append(v2)

    # 2. Adicionar vozes Edge TTS
    try:
        edge_voices = get_edge_voices()
        for v in edge_voices:
            v2 = dict(v)
            v2["provider"] = "edge_tts"
            v2["locked"] = False
            all_voices.append(v2)
    except Exception as e:
        logger.error(f"Error fetching Edge voices: {e}")

    return jsonify(all_voices)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        return jsonify(load_settings())
    
    elif request.method == 'POST':
        new_settings = request.json
        current_settings = load_settings()
        current_settings.update(new_settings)
        if save_settings(current_settings):
            return jsonify({"status": "success", "settings": current_settings})
        else:
            return jsonify({"error": "Failed to save settings"}), 500

@app.route('/api/preview', methods=['POST'])
def generate_preview():
    data = request.json
    text = data.get('text', 'Olá, eu sou o Vizô. Esta é uma demonstração da minha voz.')
    
    # Obter voice_id
    voice_id = data.get('voice_id')
    if not voice_id:
        settings = load_settings()
        voice_id = settings.get('voice_id', 'JBFqnCBsd6RMkjVDRZzb')

    # VERIFICAÇÃO 1: Se for uma voz do Edge TTS, usa direto
    if "Neural" in voice_id:
        try:
            edge_rate = data.get('edge_rate', '+0%')
            edge_pitch = data.get('edge_pitch', '+0Hz')
            logger.info(f"Generating Edge TTS audio with voice: {voice_id}, rate: {edge_rate}, pitch: {edge_pitch}")
            audio_bytes = get_edge_audio_bytes(text, voice=voice_id, rate=edge_rate, pitch=edge_pitch)
            if not audio_bytes or len(audio_bytes) == 0:
                raise RuntimeError("Edge TTS returned empty audio")
            return send_file(io.BytesIO(audio_bytes), mimetype="audio/mpeg", as_attachment=False, download_name="preview.mp3")
        except Exception as e:
            msg = str(e)
            hint = ""
            lm = msg.lower()
            if "não está instalado" in msg or "not installed" in lm:
                hint = " | Dependência ausente: instale com 'pip install edge-tts'"
            elif "empty audio" in lm:
                hint = " | Áudio vazio: verifique internet e tente outra voz (ex.: pt-BR-AntonioNeural)"
            return jsonify({"error": f"Edge TTS Error: {msg}{hint}"}), 500

    # VERIFICAÇÃO 2: Tenta ElevenLabs (Paga)
    if not client:
        # Se não tiver client configurado, fallback para Edge direto
        try:
            fallback_voice = "pt-BR-FranciscaNeural"
            audio_bytes = get_edge_audio_bytes(text, voice=fallback_voice)
            if not audio_bytes:
                raise RuntimeError("Edge TTS returned empty audio")
            return send_file(io.BytesIO(audio_bytes), mimetype="audio/mpeg")
        except:
             return jsonify({"error": "TucujuLabs API key not configured and Fallback failed"}), 500
    
    model_id = data.get('model_id', 'eleven_multilingual_v2')
    stability = data.get('stability', 0.5)
    similarity_boost = data.get('similarity_boost', 0.75)
    style = data.get('style', 0.0)
    use_speaker_boost = data.get('use_speaker_boost', True)

    try:
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                use_speaker_boost=use_speaker_boost
            )
        )
        
        audio_buffer = io.BytesIO()
        for chunk in audio_generator:
            audio_buffer.write(chunk)
        audio_buffer.seek(0)
        
        return send_file(
            audio_buffer,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="preview.mp3"
        )
        
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        
        # Tentar fallback automático para Edge TTS se for erro de cota/auth
        error_msg = str(e).lower()
        if "quota" in error_msg or "unauthorized" in error_msg or "permission" in error_msg or "billing" in error_msg:
            logger.warning("ElevenLabs Quota Exceeded/Auth Error. Falling back to Edge TTS.")
            try:
                fallback_voice = "pt-BR-FranciscaNeural"
                audio_bytes = get_edge_audio_bytes(text, voice=fallback_voice)
                if not audio_bytes:
                    raise RuntimeError("Edge TTS returned empty audio")
                
                # Retorna o áudio mas com um header avisando que foi fallback (opcional, mas bom para debug)
                response = send_file(
                    io.BytesIO(audio_bytes),
                    mimetype="audio/mpeg",
                    as_attachment=False,
                    download_name="preview_fallback.mp3"
                )
                response.headers['X-Viz-Fallback'] = 'True'
                return response
            except Exception as fallback_e:
                logger.error(f"Fallback failed: {fallback_e}")
        
        # Se não foi possível fallback, retorna o erro original detalhado
        detailed_msg = str(e)
        try:
            if hasattr(e, 'body') and isinstance(e.body, dict):
                detail = e.body.get('detail', {})
                if isinstance(detail, dict):
                    clean_msg = detail.get('message')
                    status = detail.get('status')
                    if clean_msg:
                        detailed_msg = f"{status}: {clean_msg}" if status else clean_msg
        except:
            pass
            
        return jsonify({"error": detailed_msg}), 500

# --- NOVOS ENDPOINTS GOOGLE ---

@app.route('/api/lead/save', methods=['POST'])
def save_lead():
    if not google_service:
        return jsonify({"error": "Google Service not available"}), 500
    
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    status = data.get('status', 'Em atendimento')
    
    # Salva na planilha (Banco de Dados)
    if SPREADSHEET_ID:
        try:
            google_service.add_lead_to_sheets(SPREADSHEET_ID, [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name, phone, "-", status
            ])
            return jsonify({"status": "success"})
        except Exception as e:
            logger.error(f"Failed to save lead: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "ignored", "reason": "No Spreadsheet ID"})

@app.route('/api/notify_attendant', methods=['POST'])
def notify_attendant():
    data = request.json
    name = data.get('name', 'Cliente Anônimo')
    phone = data.get('phone', 'Sem telefone')
    
    # Simula envio de mensagem para o atendente
    attendant_number = "96 99160-3396"
    
    logger.info(f"--- NOTIFICAÇÃO PARA ATENDENTE ({attendant_number}) ---")
    logger.info(f"Mensagem enviada: 'Cliente {name} ({phone}) está aguardando atendimento.'")
    logger.info(f"Opções enviadas para atendente: 1. Atender | 2. Não atender")
    logger.info("-------------------------------------------------------")
    
    # Se tivesse integração real (Twilio/WPPConnect), o código de envio estaria aqui.
    
    return jsonify({"status": "success", "message": "Atendente notificado"})

@app.route('/api/calendar/book', methods=['POST'])
def book_appointment():
    if not google_service:
        return jsonify({"error": "Google Service not available"}), 500
    
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    doctor = data.get('doctor', 'Qualquer especialista')
    date_str = data.get('date') # Format: YYYY-MM-DD
    time_str = data.get('time') # Format: HH:MM
    
    summary = f"Consulta Optométrica: {name}"
    description = f"Paciente: {name}\nWhatsApp: {phone}\nDoutor(a): {doctor}\nOrigem: Vizô Chatbot"
    
    # Define start time
    confirmed_date = date_str
    confirmed_time = time_str
    
    if date_str and time_str:
        try:
            # Parse provided date and time
            dt_str = f"{date_str} {time_str}"
            start_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            start_time = start_dt.isoformat() + 'Z' # UTC-ish (simple isoformat)
            
            # Formatação bonita para retorno
            confirmed_date = start_dt.strftime("%d/%m/%Y")
            confirmed_time = start_dt.strftime("%H:%M")
        except ValueError:
             # Fallback if parse fails
             start_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat() + 'Z'
             confirmed_time = "Horário a definir"
    else:
        # Simula agendamento para daqui a 1 hora se não especificado
        start_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat() + 'Z'
        confirmed_date = datetime.datetime.now().strftime("%d/%m/%Y")
        confirmed_time = "Horário a definir"
    
    link = google_service.create_appointment(summary, description, start_time)
    
    # Salva na planilha (Banco de Dados)
    if SPREADSHEET_ID:
        google_service.add_lead_to_sheets(SPREADSHEET_ID, [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name, phone, doctor, f"Confirmado via Google ({confirmed_date} {confirmed_time})"
        ])

    # Simula envio de relatório se solicitado (feature request)
    # "mande o relatorio para 96 991503360"
    report_number = "96 991503360" # Hardcoded for this specific request/test context or logic
    logger.info(f"--- RELATÓRIO ENVIADO PARA {report_number} ---")
    logger.info(f"Nova consulta agendada: {name} | {phone} | {doctor} | {start_time}")
    logger.info("-----------------------------------------------")

    if link:
        return jsonify({
            "status": "success", 
            "link": link,
            "date_formatted": confirmed_date,
            "time_formatted": confirmed_time
        })
    return jsonify({"error": "Failed to create appointment"}), 500

# --- CHAT LOGGING ENDPOINTS ---
@app.route('/api/log/message', methods=['POST'])
def log_message():
    try:
        data = request.json
        session_id = data.get('session_id')
        sender = data.get('sender')
        message = data.get('message')
        
        if not session_id or not sender or not message:
            return jsonify({"error": "Missing fields"}), 400
            
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_logs (session_id, sender, message) VALUES (?, ?, ?)",
                (session_id, sender, message)
            )
            conn.commit()
            
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Log Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<session_id>', methods=['GET'])
def get_chat_history(session_id):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sender, message, timestamp FROM chat_logs WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
            
        history = [dict(row) for row in rows]
        return jsonify(history)
    except Exception as e:
        logger.error(f"History Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/drive/knowledge', methods=['GET'])
def get_knowledge():
    if not google_service:
        return jsonify({"error": "Google Drive not connected"}), 500
    
    files = google_service.list_knowledge_files(KNOWLEDGE_FOLDER_ID)
    return jsonify(files)

@app.route('/api/sheets/report', methods=['GET'])
def trigger_report():
    if not google_service:
        return jsonify({"error": "Google Sheets not connected"}), 500
    
    report = google_service.get_morning_report(SPREADSHEET_ID)
    # Aqui dispararia para o WhatsApp real via Webhook ou similar
    return jsonify({"report": report})

@app.route('/api/sales_lead', methods=['POST'])
def save_sales_lead():
    try:
        data = request.json or {}
        company_name = data.get('company_name')
        cnpj = data.get('cnpj')
        contact_name = data.get('contact_name')
        email = data.get('email')
        phone = data.get('phone')
        chat_uses = data.get('chat_uses')
        channels = data.get('channels')
        volume = data.get('volume')
        integrations = data.get('integrations')
        timeline = data.get('timeline')
        budget = data.get('budget')
        source = data.get('source')
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sales_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    company_name TEXT,
                    cnpj TEXT,
                    contact_name TEXT,
                    email TEXT,
                    phone TEXT,
                    chat_uses TEXT,
                    channels TEXT,
                    volume TEXT,
                    integrations TEXT,
                    timeline TEXT,
                    budget TEXT,
                    source TEXT
                )
            ''')
            cursor.execute('''
                INSERT INTO sales_leads (company_name, cnpj, contact_name, email, phone, chat_uses, channels, volume, integrations, timeline, budget, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company_name, cnpj, contact_name, email, phone, chat_uses, channels, volume, integrations, timeline, budget, source))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Erro ao salvar sales_lead: {e}")
        return jsonify({"error": str(e)}), 500

def send_whatsapp_text(phone: str, message: str) -> bool:
    if not ZAPI_ENABLED:
        logger.warning("Z-API não configurado. Mensagem não enviada.")
        return False
    if not requests:
        logger.error("Biblioteca 'requests' não disponível para envio via Z-API.")
        return False

    def _normalize_phone(p: str) -> str:
        digits = re.sub(r"\D+", "", str(p or ""))
        if not digits:
            return ""
        if digits.startswith("55") and len(digits) >= 12:
            return digits
        if len(digits) in (10, 11) and not digits.startswith("55"):
            return "55" + digits
        if not digits.startswith("55"):
            digits = "55" + digits
        return digits

    try:
        norm_phone = _normalize_phone(phone)
        if not norm_phone:
            logger.error(f"Telefone inválido para Z-API: {phone!r}")
            return False

        base = (ZAPI_BASE_URL or "https://api.z-api.io").rstrip("/")
        url = f"{base}/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"
        payload = {
            "phone": norm_phone,
            "message": str(message or "")
        }
        safe_token_suffix = (ZAPI_TOKEN or "")[-4:]
        logger.info(
            "Enviando via Z-API",
        )
        logger.info(
            json.dumps(
                {
                    "instance": ZAPI_INSTANCE_ID,
                    "token_suffix": safe_token_suffix,
                    "payload": payload,
                },
                ensure_ascii=False,
            )
        )
        resp = requests.post(url, json=payload, timeout=20)
        logger.info(f"Resposta Z-API {resp.status_code}")
        if 200 <= resp.status_code < 300:
            return True
        logger.error(f"Falha Z-API {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem via Z-API: {e}")
        return False

@app.route('/api/exam/send', methods=['POST'])
def send_exam_result():
    data = request.json
    phone = data.get('phone')
    exam_link = data.get('link')
    
    if not phone:
        return jsonify({"error": "Phone number required"}), 400
    message = f"Aqui está o link para o seu exame: {exam_link}"

    enviado = send_whatsapp_text(phone, message)
    if not enviado:
        return jsonify({"error": "Falha ao enviar mensagem via WhatsApp (Z-API)."}), 500
    
    return jsonify({
        "status": "success",
        "channel": "z-api",
        "message": f"Exame enviado para {phone}"
    })


# --- ENDPOINT DEEPSEEK (Cérebro do Vizô) ---

@app.route('/api/chat', methods=['POST'])
def ai_chat():
    data = request.json
    user_message = data.get('message', '')
    history = data.get('history', []) # Opcional: para contexto de conversa
    
    system_prompt = (
        "Você é o Vizô, o assistente inteligente da Clínica Pró-Visão. "
        "Sua personalidade é amigável, técnica e empática. "
        "Use termos médicos simples para explicar condições oculares se solicitado. "
        "Sempre tente direcionar o usuário para um agendamento se ele demonstrar uma necessidade clínica. "
        "Responda em português do Brasil e mantenha o tom profissional mas acolhedor."
        "\n\n[INSTRUÇÃO ESPECIAL]"
        "\nSe o usuário solicitar 'resultados de exames' ou perguntar sobre 'meu exame', "
        "responda APENAS: 'Estou acessando nosso sistema de arquivos seguros para localizar seus exames. Por favor, aguarde um momento... {{SEARCH_EXAM}}' "
        "Não invente outros links."
    )

    # Verificar modo de voz para remover emojis se for Básico (Edge TTS)
    try:
        settings = load_settings()
        if settings.get('provider') == 'edge_tts':
            system_prompt += " IMPORTANTE: NÃO use emojis em nenhuma parte da sua resposta. Mantenha o texto limpo."
    except Exception as e:
        logger.error(f"Erro ao carregar settings no chat: {e}")

    # Injetar documentos disponíveis no contexto (Capability: Document Delivery)
    if google_service:
        try:
            docs = google_service.list_knowledge_files(KNOWLEDGE_FOLDER_ID)
            if docs:
                docs_list = "\n".join([f"- {d['name']}: {d.get('webViewLink')}" for d in docs])
                system_prompt += f"\n\n[DOCUMENTOS DISPONÍVEIS]\nVocê tem acesso aos seguintes arquivos no Google Drive. Se o usuário solicitar algum desses documentos, forneça o link correspondente:\n{docs_list}"
        except Exception as e:
            logger.error(f"Erro ao injetar docs do Drive: {e}")

    if not deepseek_available:
        text = user_message.lower()
        reply = "Olá! Sou o Vizô. Posso ajudar com agendamentos, exames e dúvidas sobre sua visão. Como posso te ajudar agora?"
        if any(k in text for k in ["agendar", "consulta", "marcar", "atendimento"]):
            reply = "Claro! Para agendarmos, me informe seu nome completo e WhatsApp com DDD. Posso sugerir horários disponíveis após isso."
        elif any(k in text for k in ["exame", "resultado", "laudo", "retinografia", "campo visual"]):
            reply = "Posso auxiliar com resultados de exames. Se desejar, posso encaminhar o relatório ao seu WhatsApp. Informe seu nome e número."
        elif any(k in text for k in ["convênio", "preço", "valor", "particular"]):
            reply = "Podemos verificar opções de convênio e valores. Me diga qual procedimento você precisa para eu orientar melhor."
        return jsonify({"reply": reply, "fallback": True})
    try:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        reply = deepseek_chat(messages, model="gemini-1.5-flash", max_tokens=None, stream=False)
        return jsonify({"reply": reply})
        
    except Exception as e:
        logger.error(f"DeepSeek Error: {e}")
        text = user_message.lower()
        reply = "Olá! Sou o Vizô. Posso ajudar com agendamentos, exames e dúvidas sobre sua visão. Como posso te ajudar agora?"
        if any(k in text for k in ["agendar", "consulta", "marcar", "atendimento"]):
            reply = "Claro! Para agendarmos, me informe seu nome completo e WhatsApp com DDD. Posso sugerir horários disponíveis após isso."
        elif any(k in text for k in ["exame", "resultado", "laudo", "retinografia", "campo visual"]):
            reply = "Posso auxiliar com resultados de exames. Se desejar, posso encaminhar o relatório ao seu WhatsApp. Informe seu nome e número."
        elif any(k in text for k in ["convênio", "preço", "valor", "particular"]):
            reply = "Podemos verificar opções de convênio e valores. Me diga qual procedimento você precisa para eu orientar melhor."
        return jsonify({"reply": reply, "fallback": True})

#

# --- AUTH & SUPER USERS ---
SUPER_USERS = {}

@app.route('/login')
def login_page():
    return send_file('login.html')

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Usuário e senha necessários"}), 400
        
    # Verifica Super Usuário
    if SUPER_USERS.get(username) == password:
        # Autenticado com sucesso. Agora verificar planilha.
        if google_service and SPREADSHEET_ID:
            try:
                exists = google_service.check_user_exists(SPREADSHEET_ID, username)
                
                if not exists:
                    # Adiciona na planilha
                    google_service.add_lead_to_sheets(SPREADSHEET_ID, [
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        username, 
                        "Super Usuário", 
                        "-", 
                        "Acesso Admin Liberado"
                    ])
                    logger.info(f"Super Usuário {username} registrado na planilha.")
                else:
                    logger.info(f"Super Usuário {username} já existe na planilha.")
            except Exception as e:
                logger.error(f"Erro ao verificar/registrar na planilha: {e}")
                
        # Retorna sucesso com redirecionamento
        # Simula o "acesso google automático" redirecionando para o sistema principal
        return jsonify({
            "status": "success",
            "redirect_url": "index.html" 
        })
    # Verifica usuários cadastrados
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email, password_hash, must_change, name FROM users WHERE email = ?", (username,))
            row = cursor.fetchone()
            if row and _verify_password(row[1], password):
                redirect = "change_password.html" if int(row[2] or 0) == 1 else "index.html"
                return jsonify({"status": "success", "redirect_url": redirect})
    except Exception as e:
        logger.error(f"Erro login users: {e}")
        return jsonify({"error": "Erro no serviço de autenticação"}), 500
    return jsonify({"error": "Credenciais inválidas"}), 401

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    google_token = data.get('google_token')  # opcional
    if not name or not email:
        return jsonify({"error": "Nome e e-mail são obrigatórios"}), 400
    # (Opcional) validar token Google
    if google_token and GOOGLE_CLIENT_ID:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as g_requests
            idinfo = id_token.verify_oauth2_token(google_token, g_requests.Request(), GOOGLE_CLIENT_ID)
            if idinfo.get("email") and idinfo.get("email").lower() != email.lower():
                return jsonify({"error": "E-mail do Google não confere com o informado"}), 400
        except Exception as e:
            logger.warning(f"Falha ao validar token Google: {e}")
            # segue mesmo assim (opcional)
    # Gera senha provisória
    provisional = _generate_provisional_password()
    password_hash = _hash_password(provisional)
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return jsonify({"error": "E-mail já cadastrado. Faça login ou recupere a senha."}), 409
            cursor.execute("INSERT INTO users (email, name, password_hash, must_change) VALUES (?, ?, ?, 1)", (email, name, password_hash))
            conn.commit()
        # Registrar também no Google Sheets de contatos
        try:
            if google_service and CONTACTS_SHEET_ID and "digite_o_id" not in CONTACTS_SHEET_ID:
                google_service.add_lead_to_sheets(CONTACTS_SHEET_ID, [
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    name,
                    email,
                    "Cadastro Vizô",
                    "Senha provisória enviada"
                ], "Página1!A1")
        except Exception as e:
            logger.error(f"Falha ao registrar contato no Sheets: {e}")
    except Exception as e:
        logger.error(f"Erro ao registrar usuário: {e}")
        return jsonify({"error": "Erro ao registrar usuário"}), 500
    # Envia e-mail com senha provisória
    sent = _send_email(
        email,
        "Vizô Admin - Sua senha provisória",
        f"Olá {name},\n\nSua senha provisória é: {provisional}\nAcesse o Vizô Admin e altere a senha após o primeiro login.\n\nAtenciosamente,\nEquipe Vizô"
    )
    # Resposta
    resp = {"status": "success", "sent_email": bool(sent), "message": "Cadastro realizado. Verifique seu e-mail para a senha provisória."}
    if not sent:
        resp["note"] = "SMTP não configurado; exiba a senha ao usuário de maneira segura."
        resp["provisional_password"] = provisional
    return jsonify(resp)

@app.route('/api/auth/config', methods=['GET'])
def auth_config():
    client_id = GOOGLE_CLIENT_ID or ""
    # Fallback: tenta extrair client_id do client_secret.json
    if not client_id and os.path.exists("client_secret.json"):
        try:
            with open("client_secret.json", "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
                if "web" in cfg and "client_id" in cfg["web"]:
                    client_id = cfg["web"]["client_id"]
                elif "installed" in cfg and "client_id" in cfg["installed"]:
                    client_id = cfg["installed"]["client_id"]
        except Exception as e:
            logger.error(f"Falha ao ler client_secret.json: {e}")
    return jsonify({ "google_client_id": client_id })

@app.route('/api/auth/forgot', methods=['POST'])
def auth_forgot():
    data = request.json
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"error": "E-mail é obrigatório"}), 400
    try:
        name = None
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                name = row[0]
                provisional = _generate_provisional_password()
                password_hash = _hash_password(provisional)
                cursor.execute("UPDATE users SET password_hash = ?, must_change = 1 WHERE email = ?", (password_hash, email))
                conn.commit()
                sent = _send_email(
                    email,
                    "Vizô Admin - Nova senha provisória",
                    f"Olá {name or email},\n\nSua nova senha provisória é: {provisional}\nFaça login e altere sua senha.\n\nAtenciosamente,\nEquipe Vizô"
                )
                try:
                    if google_service and CONTACTS_SHEET_ID and "digite_o_id" not in CONTACTS_SHEET_ID:
                        google_service.add_lead_to_sheets(CONTACTS_SHEET_ID, [
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            name or "",
                            email,
                            "Recuperação de senha",
                            "Senha provisória enviada" if sent else "Senha provisória gerada (sem envio)"
                        ], "Página1!A1")
                except Exception as e:
                    logger.error(f"Falha ao registrar recuperação no Sheets: {e}")
                resp = {"status": "success", "message": "Se o e-mail existe, a senha foi enviada."}
                if not sent:
                    resp["note"] = "SMTP não configurado; exiba a senha ao usuário de maneira segura."
                    resp["provisional_password"] = provisional
                return jsonify(resp)
        return jsonify({"status": "success", "message": "Se o e-mail existe, a senha foi enviada."})
    except Exception as e:
        logger.error(f"Erro em forgot password: {e}")
        return jsonify({"error": "Erro ao processar solicitação"}), 500

@app.route('/change_password')
def change_password_page():
    return send_from_directory('.', 'change_password.html')

@app.route('/api/auth/change_password', methods=['POST'])
def change_password():
    data = request.json
    email = data.get('email', '').strip()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    if not email or not current_password or not new_password:
        return jsonify({"error": "Campos obrigatórios faltando"}), 400
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash, name FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if not row or not _verify_password(row[0], current_password):
                return jsonify({"error": "Senha atual inválida"}), 401
            new_hash = _hash_password(new_password)
            cursor.execute("UPDATE users SET password_hash = ?, must_change = 0 WHERE email = ?", (new_hash, email))
            conn.commit()
        try:
            if google_service and CONTACTS_SHEET_ID and "digite_o_id" not in CONTACTS_SHEET_ID:
                google_service.add_lead_to_sheets(CONTACTS_SHEET_ID, [
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    row[1] if row else "",
                    email,
                    "Troca de senha",
                    "Concluída"
                ], "Página1!A1")
        except Exception as e:
            logger.error(f"Falha ao registrar troca no Sheets: {e}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Erro na troca de senha: {e}")
        return jsonify({"error": "Erro ao trocar a senha"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Iniciando servidor Vizô Dashboard em http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
