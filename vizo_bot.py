import time
import sys
import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
from voice_service import VoiceService
from google_service import GoogleService
from openai import OpenAI

load_dotenv()

class MetricsLogger:
    def __init__(self, api_url="http://localhost:5000/api/metrics"):
        self.api_url = api_url
        self.session_start = None

    def log_event(self, event_type, details=None):
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "details": details or {}
        }
        # Em produção, descomentar o envio real:
        # try:
        #     requests.post(self.api_url, json=payload, timeout=2)
        # except:
        #     pass # Falha silenciosa para não travar o bot
        
        # Para debug local:
        print(f"\n[METRICS] Event: {event_type} | Data: {json.dumps(details)}")

class VizoBot:
    def __init__(self):
        self.state = "MENU"
        self.user_data = {}
        self.metrics = MetricsLogger()
        self.start_time = None
        self.especialistas = [
            "Dr. Lucas Rezende", "Dra. Ana Catarina", "Dr. Tarcísio Guerra",
            "Dr. Augusto Almeida", "Dra. Nabila Demachki", "Dra. Roseni Lopes",
            "Dra. Michele Gonçalves"
        ]

        # Initialize Google Service
        try:
            self.google_service = GoogleService()
        except:
            self.google_service = None
            
        # Initialize DeepSeek
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.deepseek_client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com") if deepseek_key else None
        
        # Initialize Voice Service
        self.voice_service = VoiceService()
        self.voice_enabled = True


    def print_slow(self, text):
        print(text)
        if self.voice_enabled:
            # Clean text for speech (remove emojis if needed, though TucujuLabs handles some well or ignores them)
            # Remove markdown bolding **
            clean_text = text.replace("**", "")
            self.voice_service.speak(clean_text)
        
        # Simula digitação (removido delay real para UX local ser mais fluida)
        # for char in text:
        #     sys.stdout.write(char)
        #     sys.stdout.flush()
        #     time.sleep(0.01)
        # print()

    def disclaimer(self):
        return "\nℹ️ Este é um atendimento automatizado pela Pró-Visão Saúde Ocular Macapá. As informações são educativas e não substituem avaliação médica presencial."

    def start(self, source="local_terminal"):
        self.metrics.log_event("SESSION_START", {"source": source})
        self.start_time = time.time()
        self.print_slow("\n👁️ Olá! Eu sou o Vizô, seu assistente virtual da Pró-Visão Saúde Ocular Macapá. 🌿")
        self.print_slow("Para iniciarmos seu atendimento, por favor, me informe seu Nome Completo e seu número de WhatsApp.")
        self.state = "START_DATA"

    def load_campaign_settings(self):
        try:
            if os.path.exists('campaign_settings.json'):
                with open('campaign_settings.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}

    def show_menu(self):
        self.metrics.log_event("VIEW_MENU")
        
        # Campaign Check
        settings = self.load_campaign_settings()
        if settings.get('active_campaign'):
            print(f"\n📢 DESTAQUE: {settings.get('campaign_message')}")

        print("\n1️⃣ Agendar consulta")
        print("2️⃣ Saber sobre exames")
        print("3️⃣ Conhecer nossos especialistas")
        print("4️⃣ Falar com atendente humano")
        print("5️⃣ Capacidades Técnicas (QD Synapse)")
        print("0️⃣ Sair")
        print(self.disclaimer())
        self.state = "MENU"

    def process_input(self, user_input):
        if self.state == "WAITING_HUMAN":
            # Neste modo, o input do usuário pode ser ignorado ou tratado como "cancelar espera"
            if user_input.lower() == "cancelar":
                self.print_slow("\nSolicitação de atendente cancelada. Voltando ao menu.")
                self.show_menu()
            else:
                self.print_slow("... Por favor, aguarde. Estamos conectando você a um humano (ou digite 'cancelar')...")
            return True

        if user_input == "0":
            duration = time.time() - self.start_time if self.start_time else 0
            self.metrics.log_event("SESSION_END", {"duration_seconds": round(duration, 2)})
            print("\n👁️ Obrigado por falar com a Pró-Visão! Até logo. 🌿")
            return False

        if self.state == "START_DATA":
            self.user_data['info_inicial'] = user_input
            self.metrics.log_event("START_DATA_CAPTURED", {"input": user_input})
            self.print_slow("Obrigado! Recebi suas informações. Como posso ajudar agora?")
            self.show_menu()
            return True

        if self.state == "MENU":
            if user_input == "1":
                self.metrics.log_event("CLICK_AGENDAMENTO")
                self.print_slow("\nÉ pra já! Vamos cuidar da saúde dos seus olhos. 👁️")
                self.print_slow("Para prosseguirmos com o agendamento, por favor, me informe seu **Nome Completo**.")
                self.print_slow("\nImportante (LGPD): Precisamos desses dados apenas para identificar você e confirmar sua consulta. Eles serão armazenados com segurança. Você concorda?")
                self.state = "AGENDAMENTO_NOME"
            elif user_input == "2":
                self.metrics.log_event("CLICK_EXAMES")
                self.show_exames()
            elif user_input == "3":
                self.metrics.log_event("CLICK_ESPECIALISTAS")
                self.show_especialistas()
            elif user_input == "4":
                self.metrics.log_event("CLICK_HUMANO")
                self.initiate_handover()
            elif user_input == "5":
                self.metrics.log_event("CLICK_TECH_CAPABILITIES")
                self.show_tech_capabilities()
            else:
                # Fallback para DeepSeek Inteligente se não for comando numérico
                if self.deepseek_client and not user_input.isdigit():
                    self.print_slow("\n🤖 Pensando...")
                    try:
                        resp = self.deepseek_client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": "Você é o Vizô da Pró-Visão Macapá. Responda curto e amigável."},
                                {"role": "user", "content": user_input}
                            ]
                        )
                        self.print_slow(resp.choices[0].message.content)
                        print("\nComo mais posso ajudar?")
                    except:
                        self.print_slow("\nEstou com dificuldades para pensar... Vamos usar o menu?")
                        self.show_menu()
                else:
                    self.print_slow("\nOpção não reconhecida. Use os números do menu.")
                    self.show_menu()


        elif self.state == "AGENDAMENTO_NOME":
            self.user_data['nome'] = user_input
            self.metrics.log_event("INPUT_NAME_CAPTURED")
            self.print_slow(f"\nObrigado, {user_input}! É um prazer receber o senhor aqui na Pró-Visão. 🌿")
            self.print_slow("Por gentileza, me informe seu **número de WhatsApp com DDD**.")
            self.state = "AGENDAMENTO_ZAP"

        elif self.state == "AGENDAMENTO_ZAP":
            self.user_data['whatsapp'] = user_input
            self.metrics.log_event("LEAD_CONVERTED", {"name": self.user_data.get('nome'), "phone": user_input})
            self.print_slow(f"\nTudo anotado! 👁️")
            self.print_slow(f"Recebi seu contato **{user_input}**. Agora, escolha o especialista:")
            self.show_especialistas_list()
            self.state = "AGENDAMENTO_MEDICO"


        elif self.state == "AGENDAMENTO_MEDICO":
            try:
                choice = int(user_input)
                if 1 <= choice <= len(self.especialistas) or choice == 8:
                    medico = self.especialistas[choice-1] if choice != 8 else "Qualquer especialista"
                    self.metrics.log_event("APPOINTMENT_SCHEDULED", {"doctor": medico})
                    self.print_slow(f"\nÓtima escolha! Agendamento pré-confirmado com {medico}. 👩‍⚕️✨")
                    
                    # Sincronização Google REAL
                    if self.google_service:
                        summary = f"Cons. Terminal: {self.user_data.get('nome')}"
                        desc = f"Fone: {self.user_data.get('whatsapp')}\nVia Terminal Vizo"
                        now = datetime.now().isoformat() + 'Z'
                        self.google_service.create_appointment(summary, desc, now)
                        self.print_slow("✅ Sincronizado com Google Calendar.")
                    
                    self.print_slow("Nossa equipe entrará em contato em breve!")
                else:
                    self.print_slow("\nOpção inválida. Registramos seu interesse geral.")
            except ValueError: # Catch specific exception for invalid int conversion
                self.print_slow("\nEntendido. Registramos seu interesse.")
            
            self.show_menu()

        elif self.state == "EXAMES":
            if user_input == "1":
                 self.print_slow("\nPor favor, inicie o processo de agendamento (Opção 1 no menu principal).")
                 self.show_menu()
            else:
                self.show_menu()

        elif self.state == "ESPECIALISTAS":
             if user_input == "1":
                 self.print_slow("\nIniciando agendamento...")
                 self.state = "AGENDAMENTO_NOME"
                 self.print_slow("Por favor, me informe seu **Nome Completo**.")
             else:
                 self.show_menu()

        return True

    def initiate_handover(self):
        now = datetime.now()
        hour = now.hour
        if hour < 7 or hour >= 18:
            self.print_slow("\nNeste momento estamos fora do nosso horário de atendimento humano (7h00 às 18h00).")
            self.print_slow("Posso continuar te ajudando aqui pelo Vizô agora mesmo, mas a equipe humana só retomará o contato no próximo horário comercial.")
            self.print_slow("\nAbaixo está o menu principal para você escolher outra opção:")
            self.show_menu()
            return

        self.print_slow("\n🔄 Buscando um especialista disponível...")
        self.state = "WAITING_HUMAN"
        
        atendente_numero = "96 99160-3396"
        self.print_slow("Um de nossos atendentes humanos irá assumir em breve. Por favor, aguarde... ⏳")
        
        time.sleep(2)
        
        link_whatsapp = "https://wa.me/5596991603396?text=Olá,%20vim%20pelo%20site%20e%20gostaria%20de%20atendimento."
        
        self.print_slow(f"\n🔔 *Atendente notificado!*\n")
        self.print_slow(f"Caso prefira agilizar, copie e acesse o link abaixo no seu navegador para chamar diretamente no WhatsApp:")
        self.print_slow(f"\n👉 {link_whatsapp}\n")
        self.print_slow("(Copie e cole este link no seu navegador para iniciar a conversa real)")
        
        self.print_slow("\nPressione Enter para voltar ao menu principal...")
        self.state = "MENU"

    def show_exames(self):
        self.print_slow("\nAqui na Pró-Visão, nós cuidamos de tudo em um só lugar! 👁️✨")
        self.print_slow("Dispomos de equipamentos novos de altíssima precisão. Realizamos:")
        print("- Topografia de Córnea")
        print("- Mapeamento de Retina")
        print("- Campimetria Computadorizada")
        print("- Biometria Óptica")
        print("- Tomografia de Coerência Óptica (OCT)")
        self.print_slow("\nDeseja agendar exames? (1=Sim / 2=Voltar)")
        self.state = "EXAMES"

    def show_especialistas(self):
        self.print_slow("\nConheça nossos especialistas:")
        for medico in self.especialistas:
            print(f"👨‍⚕️ {medico}")
        self.print_slow("\nDeseja agendar? (1=Sim / 2=Voltar)")
        self.state = "ESPECIALISTAS"

    def show_especialistas_list(self):
        print("\nEscolha o especialista:")
        for i, medico in enumerate(self.especialistas):
            print(f"{i+1}️⃣ {medico}")
        print("8️⃣ Qualquer especialista")

    def show_tech_capabilities(self):
        self.print_slow("\n🚀 **Capacidades Técnicas do Vizô (QD Synapse)** 🌿")
        self.print_slow("A QD Synapse é uma startup orgulhosamente amazônida! 🇧🇷")
        self.print_slow("O Vizô pode ser personalizado para atender diversas necessidades, como:")
        print("- Integração com sistemas de agendamento e prontuários (ERP/CRM)")
        print("- Dashboards de métricas em tempo real para gestão")
        print("- Personalização avançada de fluxos de conversa (NLP/IA)")
        print("- Suporte Omnichannel (WhatsApp, Web, Instagram, Telegram)")
        print("- Automação de follow-up e pesquisa de satisfação")
        self.print_slow("\nEntre em contato conosco para transformar o atendimento da sua clínica!")
        self.print_slow("\nPressione Enter para voltar ao menu principal...")
        self.state = "MENU"

if __name__ == "__main__":
    bot = VizoBot()
    
    # Captura source de argumento de linha de comando (simulando URL param)
    source = "local_terminal"
    if len(sys.argv) > 1:
        source = sys.argv[1]

    bot.start(source=source)
    running = True
    while running:
        try:
            user_in = input("\n[Você]: ")
            running = bot.process_input(user_in)
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            break
