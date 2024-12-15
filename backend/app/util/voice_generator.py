from typing import Optional
import requests
import os
from datetime import datetime
from app.config import constants
import hashlib

class VoiceGenerator:
    def __init__(self):
        self.eleven_labs_api_key = constants.ELEVEN_LABS_API_KEY
        self.voice_id = constants.ELEVEN_LABS_VOICE_ID
        self.static_dir = os.path.join('app', 'static', 'audio')
        os.makedirs(self.static_dir, exist_ok=True)
        self.audio_cache = {}

    def _get_filename_for_text(self, text: str) -> str:
        """Generate a consistent filename for given text"""
        # Create a hash of the text to use as filename
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"voice_{text_hash}.mp3"

    async def generate_speech(self, text: str) -> Optional[str]:
        """Generate speech using ElevenLabs and save to static directory"""
        try:
            # Check cache first
            if text in self.audio_cache:
                return self.audio_cache[text]

            # Generate filename based on text content
            filename = self._get_filename_for_text(text)
            filepath = os.path.join(self.static_dir, filename)

            print(filepath)
            # Check if file already exists
            if os.path.exists(filepath):
                audio_url = f"{constants.BASE_URL}/static/audio/{filename}"
                self.audio_cache[text] = audio_url
                return audio_url

            # If not exists, generate new audio
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "xi-api-key": self.eleven_labs_api_key,
                "Content-Type": "application/json"
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.3,  # Reduced for faster generation
                    "similarity_boost": 0.5,  # Reduced for faster generation
                    "style": 0.0,
                    "use_speaker_boost": True
                },
                "optimize_streaming_latency": 4
            }

            response = requests.post(
                url, 
                json=data, 
                headers=headers,
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"ElevenLabs error: {response.text}")
                return None

            # Save the audio file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            audio_url = f"{constants.BASE_URL}/static/audio/{filename}"
            self.audio_cache[text] = audio_url
            
            return audio_url

        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return None

    def _cleanup_old_files(self, keep_last: int = 50):
        """Clean up old audio files"""
        try:
            # Only clean up dynamic files (ones without text hash)
            files = sorted([
                os.path.join(self.static_dir, f) 
                for f in os.listdir(self.static_dir) 
                if f.endswith('.mp3') and not f.startswith('voice_')
            ], key=os.path.getctime)
            
            for file in files[:-keep_last]:
                os.remove(file)
        except Exception as e:
            print(f"Error cleaning up files: {str(e)}")