"""Gemini API service for generating example sentences"""
import google.generativeai as genai
from typing import Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for generating contextual Chinese sentences using Gemini"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            # Pin to a specific stable model version (avoid surprise breaking changes)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None
            logger.warning("No Gemini API key provided")
    
    def generate_sentence(self, hanzi: str, pinyin: str, definition: str, 
                         hsk_level: int = 3) -> Dict[str, str]:
        """
        Generate a contextual example sentence for a Chinese word
        
        Args:
            hanzi: Chinese characters
            pinyin: Pinyin romanization
            definition: English definition
            hsk_level: Target HSK level (1-6)
        
        Returns:
            Dictionary with 'sentence_simplified' and 'sentence_english'
        """
        if not self.model:
            return self._fallback_sentence(hanzi, definition)
        
        prompt = f"""Create 1 natural example sentence in Chinese using the word "{hanzi}" ({pinyin}).

Requirements:
- The sentence should be at HSK level {hsk_level} difficulty
- Use simplified Chinese characters
- The sentence should clearly demonstrate the meaning: {definition}
- Keep it simple and natural
- Format the target word as a cloze deletion: {{{{c1::{hanzi}}}}}

Return ONLY a JSON object with this format:
{{
  "sentence_simplified": "The Chinese sentence with {{{{c1::{hanzi}}}}}",
  "sentence_english": "The English translation"
}}

Do not include any explanation, just the JSON."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Extract JSON (remove markdown code blocks if present)
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(text)
            
            # Validate response
            if 'sentence_simplified' in result and 'sentence_english' in result:
                # Ensure cloze markers are present
                if '{{c1::' not in result['sentence_simplified']:
                    result['sentence_simplified'] = result['sentence_simplified'].replace(
                        hanzi, f'{{{{c1::{hanzi}}}}}', 1
                    )
                
                logger.info(f"Generated sentence for {hanzi}")
                return result
            else:
                logger.warning("Invalid Gemini response format")
                return self._fallback_sentence(hanzi, definition)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON: {e}")
            return self._fallback_sentence(hanzi, definition)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._fallback_sentence(hanzi, definition)
    
    def _fallback_sentence(self, hanzi: str, definition: str) -> Dict[str, str]:
        """
        Generate a simple fallback sentence when Gemini is unavailable
        
        Args:
            hanzi: Chinese characters
            definition: English definition
        
        Returns:
            Dictionary with basic sentence and translation
        """
        templates = [
            {
                'sentence_simplified': f'这是{{{{c1::{hanzi}}}}}。',
                'sentence_english': f'This is {definition}.'
            },
            {
                'sentence_simplified': f'我喜欢{{{{c1::{hanzi}}}}}。',
                'sentence_english': f'I like {definition}.'
            },
            {
                'sentence_simplified': f'他有{{{{c1::{hanzi}}}}}。',
                'sentence_english': f'He has {definition}.'
            }
        ]
        
        logger.info(f"Using fallback sentence for {hanzi}")
        return templates[0]
    
    def generate_sentences(self, hanzi: str, pinyin: str = '', definition: str = '', hsk_level: int = 3) -> list:
        """
        Generate 3 distinct, natural Chinese sentences using the word.

        Each sentence includes a 'hint' field — a short EN→ZH production aid
        (mnemonic, collocations, usage note, or memory trick).

        Returns:
            List of dicts with keys: 'hanzi', 'pinyin', 'english', 'hint'
        """
        if not self.model:
            logger.warning("Gemini model not initialized")
            return [{"error": "Connect Gemini to generate sentences."}]

        prompt = self._sentences_prompt(hanzi, pinyin, definition, hsk_level or 3)

        try:
            response = self.model.generate_content(prompt)
            return self._parse_sentences_response(response)
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return [{"error": "Error connecting to Gemini."}]

    async def generate_sentences_async(self, hanzi: str, pinyin: str, definition: str,
                                       hsk_level: int = 3):
        """
        Async variant of generate_sentences.

        Yields the same shape (list of {hanzi, pinyin, english, hint} dicts)
        but uses google-generativeai's native async path so the FastAPI
        worker isn't blocked on the 1-3s round-trip.
        """
        if not self.model:
            logger.warning("Gemini model not initialized")
            return [{"error": "Connect Gemini to generate sentences."}]

        prompt = self._sentences_prompt(hanzi, pinyin, definition, hsk_level or 3)

        try:
            response = await self.model.generate_content_async(prompt)
            return self._parse_sentences_response(response)
        except Exception as e:
            logger.error(f"Gemini async generation error: {e}")
            return [{"error": "Error connecting to Gemini."}]

    async def generate_sentences_stream(self, hanzi: str, pinyin: str, definition: str,
                                        hsk_level: int = 3):
        """
        Async generator yielding one sentence dict at a time.

        Uses NDJSON output (one JSON object per line, no array wrapper) so
        each sentence can be parsed and yielded as soon as Gemini finishes
        its line — first sentence in <1s instead of waiting 2-3s for the
        full array. Buffers partial lines across stream chunks.
        """
        if not self.model:
            yield {"error": "Connect Gemini to generate sentences."}
            return

        prompt = self._sentences_stream_prompt(hanzi, pinyin, definition, hsk_level or 3)

        try:
            response = await self.model.generate_content_async(prompt, stream=True)
            buffer = ""
            async for chunk in response:
                buffer += (chunk.text or "")
                # Strip a leading markdown fence if Gemini emits one despite the prompt
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
            logger.error(f"Gemini stream error: {e}")
            yield {"error": "Error connecting to Gemini."}

    @staticmethod
    def _sentences_stream_prompt(hanzi: str, pinyin: str, definition: str, hsk_level: int) -> str:
        """NDJSON variant — one JSON object per line, no array, no fences."""
        context = f" ({pinyin}, meaning: {definition})" if definition else ""
        return f"""Generate 3 distinct, natural Chinese sentences using the word {hanzi}{context} at HSK Level {hsk_level}.

Requirements:
- Use simplified Chinese characters
- Each sentence must naturally demonstrate the word's meaning
- Vary sentence structure and context across the 3 examples
- HSK {hsk_level} vocabulary difficulty
- Include a short EN→ZH production hint per sentence (1-2 sentences: useful collocations, a memory trick, or a usage note that helps a learner recall {hanzi})

Output format: exactly 3 lines, each a single complete JSON object on its own line. NO surrounding array brackets. NO markdown code fences. NO explanation. Each line has this shape:
{{"hanzi":"Chinese sentence","pinyin":"pinyin with tone marks","english":"English translation","hint":"Short EN→ZH production hint"}}"""

    @staticmethod
    def _try_parse_sentence_line(line: str):
        """Parse a single NDJSON line, return dict or None on malformed input."""
        line = line.strip()
        if not line or line.startswith("```"):
            return None
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

    @staticmethod
    def _sentences_prompt(hanzi: str, pinyin: str, definition: str, hsk_level: int) -> str:
        """Shared prompt body for sync + async sentence generation."""
        context = f" ({pinyin}, meaning: {definition})" if definition else ""
        return f"""Generate 3 distinct, natural Chinese sentences using the word {hanzi}{context} at HSK Level {hsk_level}.

Requirements:
- Use simplified Chinese characters
- Each sentence must naturally demonstrate the word's meaning
- Vary sentence structure and context across the 3 examples
- HSK {hsk_level} vocabulary difficulty
- Include a short EN→ZH production hint per sentence (1-2 sentences: useful collocations, a memory trick, or a usage note that helps a learner recall {hanzi})

Return ONLY a JSON array, no explanation:
[{{"hanzi": "Chinese sentence", "pinyin": "pinyin with tone marks", "english": "English translation", "hint": "Short EN→ZH production hint"}}]"""

    @staticmethod
    def _parse_sentences_response(response):
        """Strip markdown fences, parse JSON, validate shape. Shared sync/async."""
        text = response.text.strip()
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0].strip()
        elif '```' in text:
            text = text.split('```')[1].split('```')[0].strip()

        sentences = json.loads(text)
        valid = []
        if isinstance(sentences, list):
            for s in sentences:
                if all(k in s for k in ['hanzi', 'pinyin', 'english']):
                    s.setdefault('hint', '')
                    valid.append(s)

        if not valid:
            logger.warning("Gemini returned invalid JSON structure")
            return [{"error": "Failed to generate valid sentences."}]
        return valid

    def check_connection(self) -> bool:
        """Check if Gemini API is configured and working"""
        if not self.model:
            return False
        
        try:
            # Simple test query
            response = self.model.generate_content("Say 'OK'")
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
    
    def define_word(self, term: str) -> Optional[Dict[str, str]]:
        """
        Define a term in Chinese using Gemini (for AI fallback search)
        
        Args:
            term: English or other language term to define
        
        Returns:
            Dictionary with hanzi, pinyin, definition, part_of_speech
        """
        if not self.model:
            return None
        
        prompt = f"""Define the term "{term}" in Chinese.

Return ONLY a JSON object with this exact format:
{{
  "hanzi": "The Chinese characters",
  "pinyin": "The pinyin with tone numbers",
  "definition": "English definition",
  "part_of_speech": "noun/verb/adjective/etc."
}}

Do not include any explanation, just the JSON."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Extract JSON
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            
            result = json.loads(text)
            
            if all(k in result for k in ['hanzi', 'pinyin', 'definition']):
                logger.info(f"AI defined: {term} → {result['hanzi']}")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"AI definition failed for '{term}': {e}")
            return None
