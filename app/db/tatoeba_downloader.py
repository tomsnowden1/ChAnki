"""Auto-download Tatoeba Mandarin/English sentences and translation links."""
import bz2
import logging
from pathlib import Path
from typing import Dict, Optional

import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

CMN_SENTENCES_URL = "https://downloads.tatoeba.org/exports/per_language/cmn/cmn_sentences.tsv.bz2"
ENG_SENTENCES_URL = "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2"
LINKS_URL = "https://downloads.tatoeba.org/exports/per_language/cmn/cmn-eng_links.tsv.bz2"


class TatoebaDownloader:
    """Handle automatic downloading of Tatoeba sentence corpus."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir) / "tatoeba"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cmn_file = self.data_dir / "cmn_sentences.tsv"
        self.eng_file = self.data_dir / "eng_sentences.tsv"
        self.links_file = self.data_dir / "cmn-eng_links.tsv"

    def download(self, force: bool = False) -> bool:
        """Download all three Tatoeba files. Returns True if all succeeded."""
        targets = [
            (CMN_SENTENCES_URL, self.cmn_file, "Mandarin sentences"),
            (ENG_SENTENCES_URL, self.eng_file, "English sentences"),
            (LINKS_URL, self.links_file, "cmn-eng links"),
        ]
        for url, dest, label in targets:
            if dest.exists() and not force:
                logger.info(f"{label} already present at {dest}")
                continue
            if not self._download_bz2(url, dest, label):
                logger.error(f"Failed to download {label}")
                return False
        return True

    def _download_bz2(self, url: str, dest: Path, label: str) -> bool:
        """Download a .bz2 file and decompress it to dest."""
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            tmp_bz2 = dest.with_suffix(dest.suffix + ".bz2.tmp")

            with open(tmp_bz2, "wb") as f, tqdm(
                desc=f"Downloading {label}",
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)

            logger.info(f"Decompressing {label}...")
            with bz2.open(tmp_bz2, "rb") as f_in, open(dest, "wb") as f_out:
                f_out.write(f_in.read())
            tmp_bz2.unlink()
            return True

        except Exception as e:
            logger.error(f"Download of {label} failed: {e}")
            return False

    def is_downloaded(self) -> bool:
        """All three files present and non-empty."""
        return all(
            f.exists() and f.stat().st_size > 0
            for f in (self.cmn_file, self.eng_file, self.links_file)
        )

    def get_paths(self) -> Optional[Dict[str, str]]:
        if not self.is_downloaded():
            return None
        return {
            "cmn": str(self.cmn_file.absolute()),
            "eng": str(self.eng_file.absolute()),
            "links": str(self.links_file.absolute()),
        }
