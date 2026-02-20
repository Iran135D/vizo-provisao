import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

# Import modules to test
# Note: We need to mock some imports if they have side effects on import (like dotenv loading or API inits)
# But based on the code read, most side effects happen in __init__ or global scope but caught with try/except or safe defaults.

class TestVizoBot(unittest.TestCase):
    
    def setUp(self):
        # Patch external services before importing/instantiating
        self.google_patcher = patch('vizo_bot.GoogleService')
        self.openai_patcher = patch('vizo_bot.OpenAI')
        self.voice_patcher = patch('vizo_bot.VoiceService')
        
        self.MockGoogle = self.google_patcher.start()
        self.MockOpenAI = self.openai_patcher.start()
        self.MockVoice = self.voice_patcher.start()
        
        from vizo_bot import VizoBot
        self.bot = VizoBot()
        # Disable voice to speed up tests and avoid side effects
        self.bot.voice_enabled = False 

    def tearDown(self):
        self.google_patcher.stop()
        self.openai_patcher.stop()
        self.voice_patcher.stop()

    def test_initial_state(self):
        self.assertEqual(self.bot.state, "MENU")
        self.assertEqual(self.bot.user_data, {})

    def test_start_flow(self):
        self.bot.start()
        self.assertEqual(self.bot.state, "START_DATA")

    def test_menu_selection_agendamento(self):
        self.bot.state = "MENU"
        self.bot.process_input("1")
        self.assertEqual(self.bot.state, "AGENDAMENTO_NOME")

    def test_menu_selection_exames(self):
        self.bot.state = "MENU"
        self.bot.process_input("2")
        self.assertEqual(self.bot.state, "EXAMES")

    def test_agendamento_flow(self):
        self.bot.state = "AGENDAMENTO_NOME"
        self.bot.process_input("João Silva")
        self.assertEqual(self.bot.user_data['nome'], "João Silva")
        self.assertEqual(self.bot.state, "AGENDAMENTO_ZAP")
        
        self.bot.process_input("96999999999")
        self.assertEqual(self.bot.user_data['whatsapp'], "96999999999")
        self.assertEqual(self.bot.state, "AGENDAMENTO_MEDICO")

class TestAppFlask(unittest.TestCase):
    
    def setUp(self):
        # Patch dependencies for app.py
        self.google_patcher = patch('app.GoogleService')
        self.eleven_patcher = patch('app.ElevenLabs')
        self.openai_patcher = patch('app.OpenAI')
        
        self.MockGoogle = self.google_patcher.start()
        self.MockEleven = self.eleven_patcher.start()
        self.MockOpenAI = self.openai_patcher.start()
        
        from app import app
        self.app = app
        self.client = self.app.test_client()

    def tearDown(self):
        self.google_patcher.stop()
        self.eleven_patcher.stop()
        self.openai_patcher.stop()

    def test_index(self):
        # Ensure index.html exists or mock send_from_directory
        if os.path.exists('index.html'):
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
        else:
            print("Skipping index test (file not found)")

    def test_api_voices_default(self):
        # Mock client to be None to test fallback
        with patch('app.client', None):
            response = self.client.get('/api/voices')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertTrue(isinstance(data, list))
            self.assertEqual(data[0]['name'], "George")

    def test_api_chat_mock(self):
        # Mock DeepSeek client response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Olá, sou o Vizô!"
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('app.deepseek_client', mock_client):
            response = self.client.post('/api/chat', json={"message": "Oi"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.data)['reply'], "Olá, sou o Vizô!")

if __name__ == '__main__':
    unittest.main()
