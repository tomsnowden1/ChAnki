"""
OpenAI service for sentence generation, word definitions, and health checks.

Replaces the previous GeminiService — same public API surface so callers
in sentence_service / dictionary / anki / health don't need logic changes.

Pinned to gpt-4o-mini: ~$0.0002 per sentence-batch request, fast, and
fully capable for HSK-level Chinese sentence generation.
"""
from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel
from typing import Optional, Dict, AsyncIterator, List
import json
import logging

logger = logging.getLogger(__name__)

# Pinned model — change here if a future model becomes cheaper/better.
MODEL = "gpt-4o-mini"


# ---------- Structured-output schemas (used with chat.completions.parse) ----------

class _SentenceItem(BaseModel):
    hanzi: str
    pinyin: str
    english: str
    hint: str


class _SentenceList(BaseModel):
    sentences: List[_SentenceItem]


class _Definition(BaseModel):
    hanzi: str
    pinyin: str
    definition: str
    part_of_speech: Optional[str] = None


# ---------- Service ----------

class AIService:
    """Service for AI-generated Chinese sentences and definitions via OpenAI."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.aclient = AsyncOpenAI(api_key=api_key)
        else:
            self.client = None
            self.aclient = None
            logger.warning("No OpenAI API key provided")

    # ------------------------------------------------------------------
    # Public API — signatures match the old GeminiService 1:1
    # ------------------------------------------------------------------

    def generate_sentences(self, hanzi: str, pinyin: str = '', definition: str = '',
                           hsk_level: int = 3) -> list:
        """Generate 3 distinct, natural Chinese sentences using the word.

        Returns a list of dicts with keys: hanzi, pinyin, english, hint.
        Uses Structured Outputs so the JSON shape is guaranteed valid.
        """
        if not self.client:
            logger.warning("OpenAI client not initialized")
            return [{"error": "Connect OpenAI to generate sentences."}]

        try:
            completion = self.client.beta.chat.completions.parse(
                model=MODEL,
                messages=self._sentences_messages(hanzi, pinyin, definition, hsk_level or 3),
                response_format=_SentenceList,
                max_tokens=600,
                temperature=0.7,
            )
            parsed = completion.choices[0].message.parsed
            return [s.model_dump() for s in parsed.sentences] if parsed else \
                [{"error": "OpenAI returned no sentences."}]
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            return [{"error": "Error connecting to OpenAI."}]

    async def generate_sentences_async(self, hanzi: str, pinyin: str, definition: str,
                                       hsk_level: int = 3) -> list:
        """Async variant of generate_sentences — same return shape."""
        if not self.aclient:
            logger.warning("OpenAI async client not initialized")
            return [{"error": "Connect OpenAI to generate sentences."}]

        try:
            completion = await self.aclient.beta.chat.completions.parse(
                model=MODEL,
                messages=self._sentences_messages(hanzi, pinyin, definition, hsk_level or 3),
                response_format=_SentenceList,
                max_tokens=600,
                temperature=0.7,
            )
            parsed = completion.choices[0].message.parsed
            return [s.model_dump() for s in parsed.sentences] if parsed else \
                [{"error": "OpenAI returned no sentences."}]
        except Exception as e:
            logger.error(f"OpenAI async generation error: {e}")
            return [{"error": "Error connecting to OpenAI."}]

    async def generate_sentences_stream(self, hanzi: str, pinyin: str, definition: str,
                                        hsk_level: int = 3) -> AsyncIterator[Dict]:
        """Async generator yielding one sentence dict at a time.

        Uses NDJSON output (one JSON object per line, no array wrapper) so
        each sentence can be parsed and yielded as soon as the model
        finishes its line — first sentence visible in <1s instead of
        waiting 2-3s for the full array. Buffers partial lines across
        stream chunks.
        """
        if not self.aclient:
            yield {"error": "Connect OpenAI to generate sentences."}
            return

        try:
            stream = await self.aclient.chat.completions.create(
                model=MODEL,
                messages=self._sentences_stream_messages(hanzi, pinyin, definition, hsk_level or 3),
                max_tokens=600,
                temperature=0.7,
                stream=True,
            )
            buffer = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if not delta:
                    continue
                buffer += delta
                # Strip a leading markdown fence if the model emits one despite the prompt
                if buffer.startswith("```"):
                    nl = buffer.find("\n")
                    if nl == -1:
                        continue  # waiting for the rest of the fence line
                    buffer = buffer[nl + 1:]

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    obj = self._try_parse_sentence_line(line)
                    if obj is not None:
                        yield obj

            # Final remainder (no trailing newline + possible closing fence)
            tail = buffer.strip().rstrip("`").strip()
            if tail:
                obj = self._try_parse_sentence_line(tail)
                if obj is not None:
                    yield obj
        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            yield {"error": "Error connecting to OpenAI."}

    def define_word(self, term: str) -> Optional[Dict[str, str]]:
        """
        Define a term in Chinese using OpenAI (for AI fallback search).

        Returns a dict with hanzi, pinyin, definition, part_of_speech, or None.
        """
        if not self.client:
            return None

        try:
            completion = self.client.beta.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a Chinese language assistant. Respond with valid JSON only."},
                    {"role": "user", "content": (
                        f'Define the term "{term}" in Chinese. '
                        "Provide the simplified Chinese characters (hanzi), pinyin with tone numbers, "
                        "an English definition, and the part of speech (noun/verb/adjective/etc.)."
                    )},
                ],
                response_format=_Definition,
                max_tokens=200,
                temperature=0.3,
            )
            parsed = completion.choices[0].message.parsed
            if parsed and parsed.hanzi:
                logger.info(f"AI defined: {term} → {parsed.hanzi}")
                return parsed.model_dump()
            return None
        except Exception as e:
            logger.error(f"AI definition failed for '{term}': {e}")
            return None

    def check_connection(self) -> bool:
        """
        Check if OpenAI API is configured and the key is valid.

        Uses models.list() (a read-only metadata call) instead of
        chat.completions.create() so the health check never burns tokens.
        """
        if not self.client:
            return False

        try:
            models = list(self.client.models.list())
            return len(models) > 0
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sentences_messages(hanzi: str, pinyin: str, definition: str, hsk_level: int):
        """Shared messages array for sync + async non-streaming sentence generation."""
        context = f" ({pinyin}, meaning: {definition})" if definition else ""
        return [
            {"role": "system", "content": (
                "You generate natural, level-appropriate example sentences for a "
                "Chinese-language learning app. Always respond with the requested JSON shape."
            )},
            {"role": "user", "content": (
                f"Generate 3 distinct, natural Chinese sentences using the word "
                f"{hanzi}{context} at HSK Level {hsk_level}.\n\n"
                f"Requirements:\n"
                f"- Use simplified Chinese characters\n"
                f"- Each sentence must naturally demonstrate the word's meaning\n"
                f"- Vary sentence structure and context across the 3 examples\n"
                f"- HSK {hsk_level} vocabulary difficulty\n"
                f"- Include a short EN→ZH production hint per sentence (1-2 sentences: "
                f"useful collocations, a memory trick, or a usage note that helps a "
                f"learner recall {hanzi})"
            )},
        ]

    @staticmethod
    def _sentences_stream_messages(hanzi: str, pinyin: str, definition: str, hsk_level: int):
        """NDJSON-format streaming messages — one JSON object per line, no array, no fences."""
        context = f" ({pinyin}, meaning: {definition})" if definition else ""
        return [
            {"role": "system", "content": (
                "You generate natural, level-appropriate example sentences for a "
                "Chinese-language learning app. Output strict NDJSON: one JSON object per line, "
                "no surrounding array brackets, no markdown code fences, no explanation."
            )},
            {"role": "user", "content": (
                f"Generate 3 distinct, natural Chinese sentences using the word "
                f"{hanzi}{context} at HSK Level {hsk_level}.\n\n"
                f"Requirements:\n"
                f"- Use simplified Chinese characters\n"
                f"- Each sentence must naturally demonstrate the word's meaning\n"
                f"- Vary sentence structure and context across the 3 examples\n"
                f"- HSK {hsk_level} vocabulary difficulty\n"
                f"- Include a short EN→ZH production hint per sentence\n\n"
                f"Output exactly 3 lines, each a single complete JSON object on its own line, "
                f"with this shape:\n"
                f'{{"hanzi":"Chinese sentence","pinyin":"pinyin with tone marks",'
                f'"english":"English translation","hint":"Short EN→ZH production hint"}}'
            )},
        ]

    @staticmethod
    def _try_parse_sentence_line(line: str):
        """Parse a single NDJSON line, return dict or None on malformed input."""
        line = line.strip()
        if not line or line.startswith("```"):
            return None
        # Trim trailing comma if model emits comma-separated rather than NL-separated
        if line.endswith(","):
            line = line[:-1].rstrip()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        if not all(k in obj for k in ("hanzi", "pinyin", "english")):
            return None
        obj.setdefault("hint", "")
        return obj
