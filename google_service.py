import os
import datetime
import logging
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scopes: Calendar, Sheets (Database), Drive (Knowledge Base)
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

from google.oauth2 import service_account

class GoogleService:
    def __init__(self):
        self.creds = None
        self.token_file = 'token.json'
        # Prioriza Service Account se existir, pois é mais estável para backend
        self.service_account_file = 'service_account.json' 
        self.client_secret_file = 'client_secret.json'
        self.authenticate()

    def authenticate(self):
        """Autentica via Service Account (preferencial) ou OAuth User."""
        # 1. Tenta Service Account (Melhor para servidor/bot)
        if os.path.exists(self.service_account_file):
            try:
                self.creds = service_account.Credentials.from_service_account_file(
                    self.service_account_file, scopes=SCOPES)
                logger.info("Autenticado via Service Account ✅")
                return
            except Exception as e:
                logger.error(f"Erro Service Account: {e}")

        # 2. Fallback para OAuth User (Tokens salvos)
        if os.path.exists(self.token_file):
            self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        # 3. Fluxo de Login Manual (apenas se não houver SA)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if os.path.exists(self.client_secret_file):
                    flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    with open(self.token_file, 'w') as token:
                        token.write(self.creds.to_json())
                else:
                    logger.warning("Nenhuma credencial Google encontrada (SA ou OAuth).")

    # --- GOOGLE CALENDAR (Agendamento) ---
    def create_appointment(self, summary, description, start_time, doctor_email=None):
        """Cria um agendamento no Google Calendar."""
        if not self.creds: return False
        try:
            service = build('calendar', 'v3', credentials=self.creds)
            
            # Formato esperado: 2026-02-13T10:00:00Z
            event = {
                'summary': summary,
                'description': description,
                'start': {'dateTime': start_time, 'timeZone': 'America/Fortaleza'},
                'end': {'dateTime': (datetime.datetime.fromisoformat(start_time.replace('Z', '')) + 
                                   datetime.timedelta(minutes=30)).isoformat() + 'Z', 
                        'timeZone': 'America/Fortaleza'},
            }
            if doctor_email:
                event['attendees'] = [{'email': doctor_email}]

            event = service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Evento criado: {event.get('htmlLink')}")
            return event.get('htmlLink')
        except HttpError as error:
            logger.error(f'Um erro ocorreu ao criar evento: {error}')
            return None

    # --- GOOGLE SHEETS (Banco de Dados e Relatórios) ---
    def add_lead_to_sheets(self, spreadsheet_id, data, sheet_range="A1"):
        if not self.creds: return False
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            body = {'values': [data]}
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id, range=sheet_range,
                valueInputOption="RAW", body=body).execute()
            return True
        except HttpError as error:
            logger.error(f'Erro no Sheets: {error}')
            return False

    def get_morning_report(self, spreadsheet_id):
        """Lê os atendimentos do dia para gerar o relatório do WhatsApp."""
        if not self.creds: return "Erro na autenticação"
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            range_name = 'Sheet1!A2:E' # Ignora o cabeçalho
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name).execute()
            rows = result.get('values', [])
            
            if not rows:
                return "Nenhum agendamento encontrado para hoje."
            
            # Filtro simples por data (exemplo)
            today = datetime.date.today().strftime("%Y-%m-%d")
            today_tasks = [row for row in rows if row[0].startswith(today)]
            
            report = f"*Relatório Vizô - {today}*\n\n"
            for task in today_tasks:
                report += f"📍 {task[1]} - {task[3]} ({task[2]})\n"
            
            return report
        except HttpError as error:
            return f"Erro ao gerar relatório: {error}"

    def check_user_exists(self, spreadsheet_id, identifier):
        """Verifica se um usuário já existe na planilha (por Nome ou Email/Telefone)."""
        if not self.creds: return False
        try:
            service = build('sheets', 'v4', credentials=self.creds)
            range_name = 'Sheet1!A:E' # Busca em toda a planilha
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_name).execute()
            rows = result.get('values', [])
            
            if not rows: return False
            
            # Procura o identificador em qualquer coluna da linha
            for row in rows:
                if any(identifier.lower() in str(cell).lower() for cell in row):
                    return True
            return False
        except HttpError as error:
            logger.error(f"Erro ao verificar usuário: {error}")
            return False

    # --- GOOGLE DRIVE (Knowledge Base) ---
    def list_knowledge_files(self, folder_id):
        """Lista PDFs de uma pasta específica do Drive para consulta do bot."""
        if not self.creds: return []
        try:
            service = build('drive', 'v3', credentials=self.creds)
            # Ensure folder_id is safe or handle specific placeholder
            if "digite_o_id" in folder_id:
                return []
                
            query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
            results = service.files().list(
                q=query, spaces='drive', fields='files(id, name, webViewLink, webContentLink)').execute()
            return results.get('files', [])
        except HttpError as error:
            logger.error(f'Erro ao acessar Drive: {error}')
            return []

    def search_file_by_name(self, folder_id, name_query):
        """Busca um arquivo específico por nome (parcial)."""
        if not self.creds: return None
        try:
            service = build('drive', 'v3', credentials=self.creds)
            query = f"'{folder_id}' in parents and name contains '{name_query}' and mimeType='application/pdf' and trashed=false"
            results = service.files().list(
                q=query, spaces='drive', fields='files(id, name, webViewLink, webContentLink)').execute()
            files = results.get('files', [])
            return files[0] if files else None
        except HttpError as error:
            logger.error(f'Erro ao buscar arquivo no Drive: {error}')
            return None

if __name__ == "__main__":
    # Teste de inicialização
    gs = GoogleService()
    print("Serviço Google Inicializado.")
