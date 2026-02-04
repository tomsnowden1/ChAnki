"""Audio generation service using edge-tts"""
import edge_tts
import asyncio
from typing import Optional
import logging
import io

logger = logging.getLogger(__name__)


class AudioService:
    """Service for generating Chinese audio using edge-tts"""
    
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        """
        Initialize audio service
        
        Args:
            voice: Edge TTS voice name (default: Chinese female voice)
        """
        self.voice = voice
    
    async def generate_audio_async(self, text: str) -> Optional[bytes]:
        """
        Generate audio for Chinese text (async)
        
        Args:
            text: Chinese text to convert to speech
        
        Returns:
            MP3 audio bytes, or None if generation fails
        """
        try:
            # Remove cloze markers for audio
            clean_text = text.replace('{{c1::', '').replace('}}', '')
            
            communicate = edge_tts.Communicate(clean_text, self.voice)
            audio_data = b''
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            if not audio_data:
                logger.warning(f"No audio data generated for text: {text}")
                return None
            
            logger.info(f"Generated audio for: {text[:20]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            return None
    
    def generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generate audio for Chinese text (synchronous wrapper)
        
        Args:
            text: Chinese text to convert to speech
        
        Returns:
            MP3 audio bytes, or None if generation fails
        """
        try:
            # Run async function in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.generate_audio_async(text))
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Failed to run audio generation: {e}")
            return None
    
    async def generate_multiple_async(self, texts: list[str]) -> list[Optional[bytes]]:
        """
        Generate audio for multiple texts concurrently
        
        Args:
            texts: List of Chinese texts
        
        Returns:
            List of audio bytes (or None for failures)
        """
        tasks = [self.generate_audio_async(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to None
        return [r if not isinstance(r, Exception) else None for r in results]
    
    def check_available(self) -> bool:
        """Check if edge-tts is available"""
        try:
            test_audio = self.generate_audio("测试")
            return test_audio is not None
        except Exception:
            return False
