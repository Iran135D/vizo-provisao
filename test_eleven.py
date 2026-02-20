from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")
print(f"API Key found: {bool(api_key)}")

try:
    client = ElevenLabs(api_key=api_key)
    response = client.voices.get_all()
    print("Voices fetched successfully")
    print(f"Type of response: {type(response)}")
    print(f"First voice: {response.voices[0] if response.voices else 'None'}")
except Exception as e:
    print(f"Error: {e}")
