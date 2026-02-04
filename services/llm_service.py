"""LLM service for generating cloze deletion sentences using Ollama"""
import requests
from typing import Optional, Dict


class LLMService:
    """Service for generating contextual cloze sentences using Ollama"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        self.base_url = base_url
        self.model = model
    
    def generate_cloze_sentence(self, hanzi: str, pinyin: str, definition: str) -> Dict[str, str]:
        """
        Generate a cloze deletion sentence for a Chinese word
        
        Args:
            hanzi: Chinese characters
            pinyin: Pinyin with tone marks
            definition: English definition
        
        Returns:
            Dictionary with 'sentence' (Chinese with cloze) and 'translation' (English)
        """
        # Create a detailed prompt for the LLM
        prompt = f"""Generate a natural Chinese example sentence using the word "{hanzi}" ({pinyin}, meaning: {definition}).

Requirements:
1. The sentence should be simple and commonly used (HSK 1-3 level)
2. Format the target word with cloze deletion markers: {{{{c1::{hanzi}}}}}
3. Provide ONLY the Chinese sentence on the first line
4. Provide ONLY the English translation on the second line
5. Do not include any explanations, just the two lines

Example format:
我{{{{c1::喜欢}}}}吃中国菜。
I like to eat Chinese food.

Now generate for "{hanzi}"({pinyin}):{definition}:"""

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('response', '').strip()
                
                # Parse the response
                lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
                
                if len(lines) >= 2:
                    sentence = lines[0]
                    translation = lines[1]
                    
                    # Ensure cloze markers are present
                    if '{{c1::' not in sentence:
                        # Try to add cloze markers around the target word
                        sentence = sentence.replace(hanzi, f'{{{{c1::{hanzi}}}}}', 1)
                    
                    return {
                        'sentence': sentence,
                        'translation': translation
                    }
                else:
                    # Fallback if parsing fails
                    return self._generate_fallback_cloze(hanzi, definition)
            else:
                print(f"Ollama API error: {response.status_code}")
                return self._generate_fallback_cloze(hanzi, definition)
                
        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to Ollama: {e}")
            return self._generate_fallback_cloze(hanzi, definition)
        except Exception as e:
            print(f"Error generating cloze: {e}")
            return self._generate_fallback_cloze(hanzi, definition)
    
    def _generate_fallback_cloze(self, hanzi: str, definition: str) -> Dict[str, str]:
        """
        Generate a simple fallback cloze sentence when LLM is unavailable
        
        Args:
            hanzi: Chinese characters
            definition: English definition
        
        Returns:
            Dictionary with basic cloze sentence and translation
        """
        # Simple template-based fallback
        templates = {
            '1': {
                'sentence': f'这是{{{{c1::{hanzi}}}}}。',
                'translation': f'This is {definition}.'
            },
            '2': {
                'sentence': f'我{{{{c1::{hanzi}}}}}。',
                'translation': f'I {definition}.'
            },
            '3': {
                'sentence': f'他有{{{{c1::{hanzi}}}}}。',
                'translation': f'He has {definition}.'
            }
        }
        
        # Use first template as default
        return templates['1']
    
    def check_connection(self) -> bool:
        """Check if Ollama is running and the model is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(m.get('name', '').startswith(self.model) for m in models)
            return False
        except Exception:
            return False
