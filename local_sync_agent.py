#!/usr/bin/env python3
"""
ChAnki Local Sync Agent - "The Courier"

Polls the cloud ChAnki instance for pending cards and syncs them to local Anki.
Runs as a background service on your home computer.
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path
import sys

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log(message: str, color: str = Colors.RESET):
    """Print colored log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{timestamp}] {message}{Colors.RESET}")

class SyncAgent:
    """Synchronization agent for cloud-to-local Anki card sync"""
    
    def __init__(self, config_path: str = "sync_agent_config.json"):
        self.config = self.load_config(config_path)
        self.cloud_url = self.config["cloud_url"].rstrip("/")
        self.sync_secret = self.config["sync_secret"]
        self.anki_url = self.config["anki_url"]
        self.poll_interval = self.config.get("poll_interval", 30)
        self.deck_name = self.config.get("deck_name", "Chinese::Mining")
        
        log(f"🚀 Sync Agent initialized", Colors.BLUE)
        log(f"   Cloud: {self.cloud_url}", Colors.BLUE)
        log(f"   Anki: {self.anki_url}", Colors.BLUE)
        log(f"   Poll interval: {self.poll_interval}s", Colors.BLUE)
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        if not Path(config_path).exists():
            log(f"❌ Config file not found: {config_path}", Colors.RED)
            log(f"   Creating template config...", Colors.YELLOW)
            self.create_template_config(config_path)
            log(f"\n   Please edit {config_path} with your settings and restart.", Colors.YELLOW)
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def create_template_config(self, config_path: str):
        """Create a template configuration file"""
        template = {
            "cloud_url": "https://chanki.up.railway.app",
            "sync_secret": "YOUR_SYNC_SECRET_HERE",
            "anki_url": "http://localhost:8765",
            "poll_interval": 30,
            "deck_name": "Chinese::Mining"
        }
        with open(config_path, 'w') as f:
            json.dump(template, f, indent=2)
    
    def check_anki_connection(self) -> bool:
        """Verify Anki is running and AnkiConnect is accessible"""
        try:
            response = requests.post(
                self.anki_url,
                json={"action": "version", "version": 6},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def fetch_pending_cards(self) -> list:
        """Fetch pending cards from cloud"""
        try:
            response = requests.get(
                f"{self.cloud_url}/api/sync/pending",
                headers={"X-Sync-Secret": self.sync_secret},
                timeout=10
            )
            
            if response.status_code == 401:
                log("❌ Authentication failed - check SYNC_SECRET", Colors.RED)
                return []
            
            if response.status_code != 200:
                log(f"⚠️  Cloud returned status {response.status_code}", Colors.YELLOW)
                return []
            
            data = response.json()
            return data.get("cards", [])
        
        except requests.exceptions.Timeout:
            log("⏱️  Cloud request timed out", Colors.YELLOW)
            return []
        except requests.exceptions.ConnectionError:
            log("🔌 Cannot reach cloud server", Colors.YELLOW)
            return []
        except Exception as e:
            log(f"⚠️  Error fetching cards: {e}", Colors.YELLOW)
            return []
    
    def ensure_deck_exists(self):
        """Create the deck if it doesn't exist yet (AnkiConnect createDeck is idempotent)."""
        try:
            requests.post(
                self.anki_url,
                json={"action": "createDeck", "version": 6, "params": {"deck": self.deck_name}},
                timeout=5
            )
        except Exception:
            pass  # Best-effort; addNote will surface any real error

    def add_card_to_anki(self, card: dict) -> bool:
        """Add a single card to Anki via AnkiConnect"""
        self.ensure_deck_exists()
        try:
            # Format sentence with cloze deletion
            sentence = card.get("sentence_hanzi", "")
            if sentence and card["hanzi"] in sentence:
                sentence = sentence.replace(
                    card["hanzi"], 
                    f"{{{{c1::{card['hanzi']}}}}}",
                    1
                )
            else:
                sentence = f"{{{{c1::{card['hanzi']}}}}}"
            
            # Create Anki note
            note = {
                "deckName": self.deck_name,
                "modelName": "Cloze",
                "fields": {
                    "Text": sentence,
                    "Back Extra": f"{card['pinyin']}<br>{card['definition']}<br><br>{card.get('sentence_pinyin', '')}<br>{card.get('sentence_english', '')}"
                },
                "tags": ["chanki-synced", f"hsk{card.get('hsk_level', 0)}"]
            }
            
            # Add to Anki
            payload = {
                "action": "addNote",
                "version": 6,
                "params": {"note": note}
            }
            
            response = requests.post(self.anki_url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("error"):
                log(f"   ⚠️  Anki error: {result['error']}", Colors.YELLOW)
                return False
            
            return bool(result.get("result"))
        
        except Exception as e:
            log(f"   ❌ Error adding card: {e}", Colors.RED)
            return False
    
    def acknowledge_synced_cards(self, card_ids: list) -> bool:
        """Send acknowledgment to cloud for successfully synced cards"""
        if not card_ids:
            return True
        
        try:
            response = requests.post(
                f"{self.cloud_url}/api/sync/ack",
                headers={
                    "X-Sync-Secret": self.sync_secret,
                    "Content-Type": "application/json"
                },
                json={"ids": card_ids},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            log(f"⚠️  Failed to acknowledge: {e}", Colors.YELLOW)
            return False
    
    def sync_once(self):
        """Perform one sync cycle"""
        # Check Anki connection
        if not self.check_anki_connection():
            log("❌ Anki is not running or AnkiConnect is not installed", Colors.RED)
            return
        
        # Fetch pending cards
        cards = self.fetch_pending_cards()
        
        if not cards:
            log("✓ No pending cards", Colors.GREEN)
            return
        
        log(f"📥 Found {len(cards)} pending card(s)", Colors.BLUE)
        
        # Sync each card
        synced_ids = []
        for card in cards:
            hanzi = card.get("hanzi", "?")
            log(f"   Syncing: {hanzi}...", Colors.BLUE)
            
            if self.add_card_to_anki(card):
                log(f"   ✓ Synced: {hanzi}", Colors.GREEN)
                synced_ids.append(card["id"])
            else:
                log(f"   ✗ Failed: {hanzi}", Colors.RED)
        
        # Acknowledge successful syncs
        if synced_ids:
            if self.acknowledge_synced_cards(synced_ids):
                log(f"✅ Acknowledged {len(synced_ids)} card(s) to cloud", Colors.GREEN)
            else:
                log(f"⚠️  Could not acknowledge cards to cloud", Colors.YELLOW)
    
    def run_forever(self):
        """Main polling loop"""
        log(f"\n{'='*60}", Colors.BLUE)
        log(f"🔄 Starting sync loop (every {self.poll_interval}s)", Colors.BLUE)
        log(f"   Press Ctrl+C to stop", Colors.BLUE)
        log(f"{'='*60}\n", Colors.BLUE)
        
        while True:
            try:
                self.sync_once()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                log("\n\n👋 Sync agent stopped", Colors.YELLOW)
                break
            except Exception as e:
                log(f"💥 Unexpected error: {e}", Colors.RED)
                time.sleep(self.poll_interval)

def main():
    """Entry point"""
    agent = SyncAgent()
    agent.run_forever()

if __name__ == "__main__":
    main()
