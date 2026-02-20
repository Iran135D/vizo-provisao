from elevenlabs import VoiceSettings
import json
import os
import subprocess
import time
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class VoiceService:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables.")
        
        try:
            self.client = ElevenLabs(api_key=self.api_key)
            self.settings_file = "voice_settings.json"
            self.load_settings()
        except Exception as e:
            logger.error(f"Failed to initialize TucujuLabs client: {e}")
            self.client = None

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.voice_id = settings.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
                    self.model_id = settings.get("model_id", "eleven_multilingual_v2")
                    self.stability = settings.get("stability", 0.5)
                    self.similarity_boost = settings.get("similarity_boost", 0.75)
                    self.style = settings.get("style", 0.0)
                    self.use_speaker_boost = settings.get("use_speaker_boost", True)
            else:
                logger.warning(f"Settings file {self.settings_file} not found. Using defaults.")
                self.voice_id = "JBFqnCBsd6RMkjVDRZzb"
                self.model_id = "eleven_multilingual_v2"
                self.stability = 0.5
                self.similarity_boost = 0.75
                self.style = 0.0
                self.use_speaker_boost = True
        except Exception as e:
            logger.error(f"Error loading voice settings: {e}")
            self.voice_id = "JBFqnCBsd6RMkjVDRZzb"
            self.model_id = "eleven_multilingual_v2"
            self.stability = 0.5
            self.similarity_boost = 0.75
            self.style = 0.0
            self.use_speaker_boost = True

    def play_audio_file(self, file_path):
        """
        Plays an audio file using PowerShell (Windows).
        """
        try:
            # Ensure absolute path
            abs_path = os.path.abspath(file_path)
            
            # PowerShell command to play audio using WPF MediaPlayer
            ps_script = f"""
            Add-Type -AssemblyName PresentationCore;
            $p = New-Object System.Windows.Media.MediaPlayer;
            $p.Open('{abs_path}');
            $duration = $null;
            
            # Wait for media to open and get duration
            for($i=0; $i -lt 10; $i++) {{
                if($p.NaturalDuration.HasTimeSpan) {{
                    $duration = $p.NaturalDuration.TimeSpan.TotalSeconds;
                    break;
                }}
                Start-Sleep -Milliseconds 100;
            }}
            
            $p.Play();
            
            if($duration) {{
                Start-Sleep -Seconds ($duration + 1);
            }} else {{
                # Fallback if duration not detected
                Start-Sleep -Seconds 5;
            }}
            $p.Close();
            """
            
            subprocess.run(["powershell", "-c", ps_script], check=True)
            
        except Exception as e:
            logger.error(f"Failed to play audio: {e}")

    def speak(self, text):
        """
        Converts text to speech and plays it.
        """
        if not self.client:
            logger.error("ElevenLabs client is not initialized.")
            return

        # Reload settings to ensure we use the latest configuration
        self.load_settings()

        try:
            logger.info(f"Generating audio for: {text[:50]}... (Voice: {self.voice_id})")
            
            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model_id,
                output_format="mp3_44100_128",
                voice_settings=VoiceSettings(
                    stability=self.stability,
                    similarity_boost=self.similarity_boost,
                    style=self.style,
                    use_speaker_boost=self.use_speaker_boost
                )
            )
            
            # Save to a temporary file
            output_file = "temp_speech.mp3"
            with open(output_file, "wb") as f:
                for chunk in audio_generator:
                    f.write(chunk)
            
            logger.info("Audio generated. Playing...")
            self.play_audio_file(output_file)
            
            # Cleanup
            try:
                os.remove(output_file)
            except:
                pass
                
            logger.info("Playback finished.")
        except Exception as e:
            logger.error(f"Error during text-to-speech generation or playback: {e}")

if __name__ == "__main__":
    # Test the service
    service = VoiceService()
    service.speak("Olá! Eu sou o Vizô, seu assistente virtual.")
