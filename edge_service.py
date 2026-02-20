import asyncio
import os
import logging
import importlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _edge_mod():
    try:
        return importlib.import_module("edge_tts")
    except Exception:
        raise RuntimeError("edge-tts não está instalado")

async def _generate_audio_bytes_stream(text, voice, rate="+0%", pitch="+0Hz"):
    edge_tts = _edge_mod()
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    chunks = bytearray()
    async for chunk in communicate.stream():
        t = None
        data = None
        try:
            t = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)
            data = chunk.get("data") if isinstance(chunk, dict) else getattr(chunk, "data", None)
        except Exception:
            t = getattr(chunk, "type", None)
            data = getattr(chunk, "data", None)
        if t == "audio" and data:
            chunks.extend(data)
    return bytes(chunks)

def get_edge_audio_bytes(text, voice="pt-BR-FranciscaNeural", rate="+0%", pitch="+0Hz"):
    if text:
        text = text.replace("Vizô", "Vizôô")
    try:
        for _ in range(2):
            audio = asyncio.run(_generate_audio_bytes_stream(text, voice, rate, pitch))
            if audio:
                return audio
        edge_tts = _edge_mod()
        tmp = f"temp_edge_{os.getpid()}.mp3"
        try:
            async def _save():
                communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                await communicate.save(tmp)
            asyncio.run(_save())
            if os.path.exists(tmp):
                with open(tmp, "rb") as f:
                    data = f.read()
                if not data:
                    raise RuntimeError("Edge TTS returned empty audio")
                return data
            raise RuntimeError("Edge TTS did not create output file")
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"EdgeTTS Generation Error: {e}")
        raise e

def get_available_voices():
    return [
        {"voice_id": "pt-BR-FranciscaNeural", "name": "Francisca (Neural) - PT-BR", "category": "edge-free"},
        {"voice_id": "pt-BR-AntonioNeural", "name": "Antonio (Neural) - PT-BR", "category": "edge-free"},
        {"voice_id": "pt-PT-RaquelNeural", "name": "Raquel (Neural) - PT-PT", "category": "edge-free"},
        {"voice_id": "pt-PT-DuarteNeural", "name": "Duarte (Neural) - PT-PT", "category": "edge-free"},
        {"voice_id": "fr-FR-DeniseNeural", "name": "Denise (Neural) - FR-FR", "category": "edge-free"},
        {"voice_id": "fr-FR-HenriNeural", "name": "Henri (Neural) - FR-FR", "category": "edge-free"},
        {"voice_id": "en-US-GuyNeural", "name": "Guy (Neural) - EN-US", "category": "edge-free"},
        {"voice_id": "en-US-JennyNeural", "name": "Jenny (Neural) - EN-US", "category": "edge-free"}
    ]
