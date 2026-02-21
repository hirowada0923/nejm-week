import os
import re
import struct
import logging
from google import genai
from google.genai import types

# --- Constants ---
TTS_MODEL = "gemini-2.5-flash-preview-tts" 
DEFAULT_VOICE_MALE = "Algieba"
DEFAULT_VOICE_FEMALE = "Autonoe"

class TTSEngine:
    def __init__(self, api_key, model_name=TTS_MODEL):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)

    def _convert_to_wav(self, audio_data: bytes, rate=24000) -> bytes:
        """Converts raw L16 PCM audio data to WAV format."""
        bits_per_sample = 16
        channels = 1
        bytes_per_sample = bits_per_sample // 8
        block_align = channels * bytes_per_sample
        avg_bytes_per_second = rate * block_align
        data_size = len(audio_data)

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE", b"fmt ",
            16, 1, channels, rate, avg_bytes_per_second,
            block_align, bits_per_sample, b"data", data_size
        )
        return header + audio_data

    def _parse_script_to_parts(self, script_text):
        """
        Parses the script and converts MaleHost/FemaleHost to Speaker 1/Speaker 2 tags
        that the Gemini TTS model understands.
        Joins everything into a single text block to prevent multi-turn confusion.
        """
        lines = []
        for line in script_text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            # Map roles to generic speaker names for the API
            male_match = re.match(r'(MaleHost|Speaker 1):\s*(.*)', line, re.IGNORECASE)
            female_match = re.match(r'(FemaleHost|Speaker 2):\s*(.*)', line, re.IGNORECASE)
            
            if male_match:
                lines.append(f'Speaker 1: {male_match.group(2).strip()}')
            elif female_match:
                lines.append(f'Speaker 2: {female_match.group(2).strip()}')
            else:
                # Default to Speaker 1 if no prefix
                lines.append(f'Speaker 1: {line}')
        
        full_text = "\n".join(lines)
        return [types.Part.from_text(text=full_text)]

    def generate_audio(self, script_text, output_path):
        try:
            self.logger.info("Generating multi-speaker audio with Gemini (google-genai SDK)...")
            
            contents_parts = self._parse_script_to_parts(script_text)
            
            speech_config = types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker="Speaker 1", 
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=DEFAULT_VOICE_MALE)
                            )
                        ),
                        types.SpeakerVoiceConfig(
                            speaker="Speaker 2", 
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=DEFAULT_VOICE_FEMALE)
                            )
                        ),
                    ]
                ),
            )
            
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["audio"],
                speech_config=speech_config,
            )

            audio_data_buffer = b''
            # Using stream for better handling of long scripts
            for chunk in self.client.models.generate_content_stream(
                model=self.model_name,
                contents=[types.Content(role="user", parts=contents_parts)],
                config=generate_content_config
            ):
                if chunk.candidates and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.inline_data:
                            audio_data_buffer += part.inline_data.data

            if not audio_data_buffer:
                self.logger.error("No audio content was generated.")
                return False

            self.logger.info(f"Received audio data: {len(audio_data_buffer)} bytes. Converting to WAV...")
            wav_data = self._convert_to_wav(audio_data_buffer)

            with open(output_path, "wb") as f:
                f.write(wav_data)
            
            self.logger.info(f"Audio saved to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error in TTS generation: {e}", exc_info=True)
            return False
