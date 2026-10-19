import os
import re
import struct
import logging
from google import genai
from google.genai import types

# --- Constants ---
TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
DEFAULT_VOICE_MALE = "Algieba"
DEFAULT_VOICE_FEMALE = "Autonoe"

class TTSEngine:
    def __init__(self, api_key, model_name=None):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name or TTS_MODEL
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
        Parses script lines into individual types.Part objects with speech_metadata.speaker
        set to Speaker 1 or Speaker 2 for modern Gemini TTS models (e.g. gemini-3.8-flash-tts).
        Falls back to text block if using legacy 2.5 models.
        """
        parsed_dialogues = []
        for line in script_text.splitlines():
            line = line.strip()
            if not line:
                continue
            
            male_match = re.match(r'(MaleHost|Speaker 1):\s*(.*)', line, re.IGNORECASE)
            female_match = re.match(r'(FemaleHost|Speaker 2):\s*(.*)', line, re.IGNORECASE)
            
            if male_match:
                speaker = "Speaker 1"
                text = male_match.group(2).strip()
            elif female_match:
                speaker = "Speaker 2"
                text = female_match.group(2).strip()
            else:
                speaker = "Speaker 1"
                text = line

            if text:
                parsed_dialogues.append((speaker, text))

        # Check if running a legacy 2.5 TTS model
        if "2.5" in self.model_name:
            full_text = "\n".join([f"{spk}: {txt}" for spk, txt in parsed_dialogues])
            return [types.Part.from_text(text=full_text)]

        # Modern 3.8+ TTS models require speech_metadata on each Part
        parts = []
        for speaker, text in parsed_dialogues:
            parts.append(
                types.Part(
                    text=text,
                    speech_metadata=types.SpeechMetadata(speaker=speaker)
                )
            )
        return parts

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
