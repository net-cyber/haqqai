"""Hasab AI voice provider for STT and TTS.

Hasab AI (https://hasab.ai) provides speech intelligence for low-resource
African languages — Amharic (`am`), Afaan Oromoo (`oro`), English (`eng`) and
Tigrinya (`tir`).

- **STT**: `POST /upload-audio` (multipart). Accepts MP3 / WAV / M4A and returns
  the transcript synchronously in the JSON `transcription` field. The browser
  capture path sends raw PCM16, so we wrap it in a WAV container first.
- **TTS**: `POST /tts/synthesize` (JSON `{text, language, speaker_name}`) returns
  the generated audio in the response body. Streamed back to the caller in
  chunks. Hasab has no playback-speed parameter, so `speed` is accepted but
  ignored.

Auth is a bearer token: `Authorization: Bearer <api_key>`.

See https://developer.hasab.ai for the full API reference.
"""

import asyncio
import json
import struct
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from onyx.tracing.flows import LLMFlow
from onyx.tracing.llm_utils import traced_llm_call
from onyx.voice.interface import StreamingTranscriberProtocol
from onyx.voice.interface import TranscriptResult
from onyx.voice.interface import VoiceProviderInterface

# Default Hasab API base URL (includes the versioned `/api/v1` prefix).
DEFAULT_HASAB_API_BASE = "https://api.hasab.ai/api/v1"

# Default language used when none is configured (Hasab's primary market).
DEFAULT_HASAB_LANGUAGE = "am"

# Default speaker for TTS.
DEFAULT_HASAB_SPEAKER = "Selam"

# Sample rate of the PCM16 audio captured by the browser frontend.
BROWSER_PCM16_SAMPLE_RATE = 24000


# Named TTS speakers, tagged with the language they belong to. The public
# `get_available_voices` view only exposes id/name; the language tag is used
# internally to pick the right `language` for a synthesis request.
HASAB_SPEAKERS: list[dict[str, str]] = [
    {"id": "Selam", "name": "Selam (Amharic)", "language": "am"},
    {"id": "Aster", "name": "Aster (Amharic)", "language": "am"},
    {"id": "Hanna", "name": "Hanna (Amharic)", "language": "am"},
    {"id": "Yared", "name": "Yared (Amharic)", "language": "am"},
    {"id": "Haile", "name": "Haile (Amharic)", "language": "am"},
    {"id": "Tigist", "name": "Tigist (Amharic)", "language": "am"},
    {"id": "Lemlem", "name": "Lemlem (Afaan Oromoo)", "language": "oro"},
]

_SPEAKER_LANGUAGE: dict[str, str] = {s["id"]: s["language"] for s in HASAB_SPEAKERS}

# Hasab does not expose selectable STT/TTS model variants, so we surface a
# single representative entry for each so the admin UI has something to show.
HASAB_STT_MODELS = [{"id": "hasab-stt", "name": "Hasab Transcription"}]
HASAB_TTS_MODELS = [{"id": "hasab-tts", "name": "Hasab Text-to-Speech"}]

# Map audio formats to the MIME types Hasab's multipart upload expects.
_AUDIO_MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
}


def _create_wav_header(
    data_length: int,
    sample_rate: int = BROWSER_PCM16_SAMPLE_RATE,
    channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """Create a 44-byte WAV header for raw PCM audio data."""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        36 + data_length,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size (PCM)
        1,  # AudioFormat (1 = PCM)
        channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_length,  # Subchunk2Size
    )


class HasabStreamingTranscriber(StreamingTranscriberProtocol):
    """Buffering transcriber for Hasab's batch `/upload-audio` API.

    Hasab has no real-time streaming STT endpoint and rejects sub-second clips,
    so transcribing every incoming chunk would waste tokens (one charge per
    call) and emit garbage single-character partials. Instead we buffer the
    whole utterance and transcribe it once when the client signals end-of-speech
    — a single API call per utterance, with the result returned from `close()`.
    """

    def __init__(self, provider: "HasabVoiceProvider", audio_format: str = "pcm16"):
        self._provider = provider
        self._audio_format = audio_format
        self._buffer = bytearray()
        self._final = ""
        self._closed = False

    async def send_audio(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)

    async def receive_transcript(self) -> TranscriptResult | None:
        # No partials — Hasab can't transcribe incrementally. Throttle the
        # handler's poll loop so it doesn't busy-spin while we buffer audio.
        await asyncio.sleep(0.1)
        return TranscriptResult(text="", is_vad_end=False)

    async def close(self) -> str:
        if self._closed:
            return self._final
        self._closed = True
        if not self._buffer:
            return self._final
        try:
            transcript = await self._provider.transcribe(
                bytes(self._buffer), self._audio_format
            )
            if transcript and transcript.strip():
                self._final = transcript.strip()
        except Exception:
            from onyx.utils.logger import setup_logger

            setup_logger().error(
                "Hasab streaming transcription failed on close", exc_info=True
            )
        return self._final

    def reset_transcript(self) -> None:
        self._buffer = bytearray()
        self._final = ""


class HasabVoiceProvider(VoiceProviderInterface):
    """Hasab AI voice provider using `/upload-audio` for STT and `/tts/synthesize`
    for speech synthesis."""

    def __init__(
        self,
        api_key: str | None,
        api_base: str | None = None,
        custom_config: dict[str, Any] | None = None,
        stt_model: str | None = None,
        tts_model: str | None = None,
        default_voice: str | None = None,
    ):
        self.api_key = api_key
        self.api_base = (api_base or DEFAULT_HASAB_API_BASE).rstrip("/")
        self.stt_model = stt_model or "hasab-stt"
        self.tts_model = tts_model or "hasab-tts"
        self.default_voice = default_voice or DEFAULT_HASAB_SPEAKER
        # Language used for transcription (and as a TTS fallback) when it can't
        # be derived from the selected speaker. Configurable via custom_config.
        self.language = (custom_config or {}).get("language") or DEFAULT_HASAB_LANGUAGE

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _language_for_speaker(self, speaker: str | None) -> str:
        """Resolve the synthesis language from the speaker, falling back to the
        configured default language."""
        if speaker and speaker in _SPEAKER_LANGUAGE:
            return _SPEAKER_LANGUAGE[speaker]
        return self.language

    async def transcribe(self, audio_data: bytes, audio_format: str) -> str:
        """Transcribe audio via `POST /upload-audio`."""
        if not self.api_key:
            raise ValueError("Hasab API key required for transcription")

        from onyx.utils.logger import setup_logger

        logger = setup_logger()

        # `/upload-audio` accepts MP3 / WAV / M4A — not raw PCM. The browser
        # capture path sends PCM16 at 24kHz mono, so wrap it as WAV.
        audio_format = audio_format.lower()
        if audio_format == "pcm16":
            audio_data = _create_wav_header(len(audio_data)) + audio_data
            audio_format = "wav"

        mime_type = _AUDIO_MIME_TYPES.get(audio_format, f"audio/{audio_format}")

        form_data = aiohttp.FormData()
        form_data.add_field(
            "audio",
            audio_data,
            filename=f"audio.{audio_format}",
            content_type=mime_type,
        )
        form_data.add_field("transcribe", "true")
        form_data.add_field("translate", "false")
        form_data.add_field("summarize", "false")
        form_data.add_field("timestamps", "false")
        form_data.add_field("source_language", self.language)
        form_data.add_field("language", self.language)

        url = f"{self.api_base}/upload-audio"

        logger.info(
            "Hasab transcribe: sending %s bytes, format=%s, language=%s",
            len(audio_data),
            audio_format,
            self.language,
        )

        with traced_llm_call(
            flow=LLMFlow.STT,
            model=self.stt_model,
            provider="hasab",
        ):
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, headers=self._auth_headers(), data=form_data
                ) as response:
                    status = response.status
                    body = await response.text()

        # Surface auth/permission problems as hard errors.
        if status in (401, 403):
            logger.error("Hasab transcribe unauthorized (%s): %s", status, body)
            raise RuntimeError(f"Hasab transcription unauthorized: {body}")

        try:
            result = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error("Hasab transcribe failed (%s): %s", status, body)
            raise RuntimeError(f"Hasab transcription failed ({status}): {body}") from e

        # Hasab signals the real outcome via the `success` field, not the HTTP
        # status (a successful transcription can come back with a non-200 code).
        # Short clips from the real-time chunker frequently return
        # `success: false` ("API processing failed") — that's an empty result,
        # not a fatal error, so the caller keeps accumulating for the final pass.
        if result.get("success") is False:
            logger.info(
                "Hasab transcribe: no transcript for clip (%s)",
                result.get("message"),
            )
            return ""

        text = result.get("transcription", "") or ""
        logger.info("Hasab transcribe: got result: %s...", text[:50])
        return text

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,  # noqa: ARG002 — Hasab has no playback-speed control
    ) -> AsyncIterator[bytes]:
        """Convert text to audio via `POST /tts/synthesize`.

        `speed` is accepted for interface compatibility but Hasab has no
        playback-speed control, so it is ignored.
        """
        from onyx.utils.logger import setup_logger

        logger = setup_logger()

        if not self.api_key:
            raise ValueError("Hasab API key required for TTS")

        speaker = voice or self.default_voice
        language = self._language_for_speaker(speaker)

        url = f"{self.api_base}/tts/synthesize"
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "language": language,
            "speaker_name": speaker,
        }

        logger.info(
            "Hasab TTS: starting synthesis, text='%s...', speaker=%s, language=%s",
            text[:50],
            speaker,
            language,
        )

        with traced_llm_call(
            flow=LLMFlow.TTS,
            model=self.tts_model,
            provider="hasab",
            input_messages=[{"role": "user", "content": text}],
        ):
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    status = response.status
                    content_type = response.headers.get("content-type", "")
                    # Read the whole response inside the span. Hasab returns the
                    # full audio in one response (not a progressive model stream),
                    # and buffering here keeps the tracing context manager's
                    # enter/exit on the same async task. Yielding across the
                    # `with` boundary corrupts the span's ContextVar token once
                    # Starlette resumes this generator in its streaming task.
                    audio = await response.read()

        if status != 200:
            detail = audio.decode("utf-8", errors="replace")[:500]
            logger.error("Hasab TTS failed (%s): %s", status, detail)
            raise RuntimeError(f"Hasab TTS failed ({status}): {detail}")

        logger.info(
            "Hasab TTS: received %s bytes, content-type=%s, magic=%s",
            len(audio),
            content_type,
            audio[:4].hex(),
        )

        # Stream the buffered audio to the caller in chunks.
        for start in range(0, len(audio), 8192):
            yield audio[start : start + 8192]

    async def validate_credentials(self) -> None:
        """Validate the Hasab API key with a lightweight `GET /tts/speakers`."""
        if not self.api_key:
            raise ValueError("Hasab API key required")

        url = f"{self.api_base}/tts/speakers"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._auth_headers()) as response:
                if response.status == 200:
                    return
                if response.status in (401, 403):
                    raise RuntimeError("Invalid Hasab API key.")
                error_text = await response.text()
                raise RuntimeError(f"Hasab credential validation failed: {error_text}")

    def get_available_voices(self) -> list[dict[str, str]]:
        """Return Hasab's named TTS speakers."""
        return [{"id": s["id"], "name": s["name"]} for s in HASAB_SPEAKERS]

    def get_available_stt_models(self) -> list[dict[str, str]]:
        return [model.copy() for model in HASAB_STT_MODELS]

    def get_available_tts_models(self) -> list[dict[str, str]]:
        return [model.copy() for model in HASAB_TTS_MODELS]

    def tts_output_mime_type(self) -> str:
        # Hasab's /tts/synthesize returns a WAV (RIFF) payload, not MP3.
        return "audio/wav"

    def supports_streaming_stt(self) -> bool:
        # Routes through the streaming handler so we can buffer the full
        # utterance and make a single batch call on close — instead of the
        # chunked fallback that hits the API on every sub-second fragment.
        return True

    async def create_streaming_transcriber(  # ty: ignore[invalid-method-override]
        self, _audio_format: str = "webm"
    ) -> HasabStreamingTranscriber:
        if not self.api_key:
            raise ValueError("Hasab API key required for transcription")
        # The browser streams raw PCM16 over the WebSocket; transcribe() wraps
        # it as WAV before upload.
        return HasabStreamingTranscriber(self, audio_format="pcm16")
