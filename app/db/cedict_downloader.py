"""Auto-download CC-CEDICT dictionary"""
import requests
from typing import Optional
import logging
from pathlib import Path
from tqdm import tqdm
import gzip
import os

logger = logging.getLogger(__name__)

CEDICT_URL = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
BACKUP_URL = "https://raw.githubusercontent.com/skishore/makemeahanzi/master/cedict_ts.u8"


class CEDICTDownloader:
    """Handle automatic downloading of CC-CEDICT dictionary"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.output_file = self.data_dir / "cedict_ts.u8"
    
    def download(self, force: bool = False) -> bool:
        """
        Download CC-CEDICT dictionary
        
        Args:
            force: Force download even if file exists
        
        Returns:
            True if successful, False otherwise
        """
        if self.output_file.exists() and not force:
            logger.info(f"Dictionary file already exists at {self.output_file}")
            return True
        
        # Try primary URL (compressed)
        logger.info("Downloading CC-CEDICT dictionary...")
        success = self._download_compressed()
        
        if not success:
            logger.warning("Primary download failed, trying backup URL...")
            success = self._download_plain()
        
        if success:
            logger.info(f"✓ Dictionary downloaded to {self.output_file}")
            return True
        else:
            logger.error("✗ Failed to download dictionary")
            return False
    
    def _download_compressed(self) -> bool:
        """Download compressed .gz file from mdbg"""
        try:
            response = requests.get(CEDICT_URL, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get file size for progress bar
            total_size = int(response.headers.get('content-length', 0))
            
            # Download to temp file
            temp_file = self.data_dir / "cedict_temp.txt.gz"
            
            with open(temp_file, 'wb') as f, tqdm(
                desc="Downloading",
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
            
            # Decompress
            logger.info("Decompressing dictionary...")
            with gzip.open(temp_file, 'rb') as f_in:
                with open(self.output_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            
            # Clean up
            temp_file.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Compressed download failed: {e}")
            return False
    
    def _download_plain(self) -> bool:
        """Download plain text file from backup source"""
        try:
            response = requests.get(BACKUP_URL, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(self.output_file, 'wb') as f, tqdm(
                desc="Downloading (backup)",
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
            
            return True
            
        except Exception as e:
            logger.error(f"Backup download failed: {e}")
            return False
    
    def is_downloaded(self) -> bool:
        """Check if dictionary file exists"""
        return self.output_file.exists() and self.output_file.stat().st_size > 0
    
    def get_file_path(self) -> Optional[str]:
        """Get path to downloaded file"""
        if self.is_downloaded():
            return str(self.output_file.absolute())
        return None
