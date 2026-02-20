from google_service import GoogleService
import logging

# Configure logging to show us what's happening
logging.basicConfig(level=logging.INFO)

def test_connection():
    print("--- Testando Conexão Google (Service Account) ---")
    
    try:
        # Tenta inicializar o serviço
        gs = GoogleService()
        
        if gs.creds:
            print("✅ Autenticação realizada com sucesso!")
            print(f"   Tipo de Credencial: {type(gs.creds)}")
            print(f"   Conta de Serviço: {gs.creds.service_account_email if hasattr(gs.creds, 'service_account_email') else 'N/A'}")
        else:
            print("❌ Falha na autenticação.")
            return

        # Teste 1: Drive (Listar arquivos)
        # Nota: Só vai funcionar se você tiver compartilhado a pasta com o email da conta de serviço!
        print("\n[Teste Drive] Tentando listar arquivos...")
        files = gs.list_knowledge_files("root") # Tenta listar da raiz se não tiver ID específico
        print(f"   Arquivos encontrados: {len(files)}")
        for f in files[:3]:
            print(f"   - {f['name']}")

        # Teste 2: Calendar (Criar evento teste)
        # Nota: Só vai funcionar se você tiver compartilhado o calendário com o email da conta de serviço!
        print("\n[Teste Calendar] O teste de criação de evento requer compartilhamento prévio.")
        print(f"   ⚠️ IMPORTANTE: Compartilhe seu Calendário e Pasta do Drive com: \n      {gs.creds.service_account_email}")

    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if __name__ == "__main__":
    test_connection()
