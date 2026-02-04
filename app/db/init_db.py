"""Database initialization and seeding utilities"""
from app.db.session import init_db, get_db
from app.models import AppSettings, DictionaryEntry
from app.db.cedict_downloader import CEDICTDownloader
import re
import logging

logger = logging.getLogger(__name__)


def initialize_database():
    """Create all database tables"""
    print("Initializing database...")
    init_db()
    print("✓ Database tables created")
    
    # Create default settings if they don't exist
    with get_db() as db:
        settings = db.query(AppSettings).first()
        if not settings:
            settings = AppSettings()
            db.add(settings)
            db.commit()
            print("✓ Default settings created")
        else:
            print("✓ Settings already exist")


def check_and_download_dictionary(auto_seed: bool = True) -> dict:
    """
    Check dictionary health and auto-heal if needed
    
    Args:
        auto_seed: If True, automatically seed dictionary if empty
    
    Returns:
        Dictionary with status info: {"ready": bool, "count": int, "message": str}
    """
    with get_db() as db:
        count = db.query(DictionaryEntry).count()
        
        # Dictionary is healthy
        if count >= 100000:
            logger.info(f"Dictionary healthy with {count:,} entries")
            return {
                "ready": True,
                "count": count,
                "message": f"Dictionary loaded ({count:,} entries)"
            }
        
        # Dictionary needs seeding
        if count < 100000 and count > 0:
            logger.warning(f"Dictionary degraded: only {count:,} entries")
            return {
                "ready": False,
                "count": count,
                "message": f"Dictionary incomplete ({count:,} entries, need >100,000)"
            }
    
    # Dictionary is empty - trigger auto-seed
    if not auto_seed:
        return {
            "ready": False,
            "count": 0,
            "message": "Dictionary empty (auto-seed disabled)"
        }
    
    logger.info("🔧 Self-Healing: Dictionary empty, initiating auto-download...")
    downloader = CEDICTDownloader()
    
    if not downloader.is_downloaded():
        print("\n" + "=" * 60)
        print("📚 First-time setup: Downloading CC-CEDICT dictionary...")
        print("   This may take 2-3 minutes...")
        print("=" * 60)
        
        if not downloader.download():
            logger.error("Auto-download failed")
            return {
                "ready": False,
                "count": 0,
                "message": "Auto-download failed. Please upload cedict_ts.u8 manually."
            }
    
    # Download successful - now seed
    file_path = downloader.get_file_path()
    if file_path:
        logger.info(f"Seeding from {file_path}")
        seed_dictionary_from_cedict(file_path)
        
        # Verify seeding succeeded
        with get_db() as db:
            final_count = db.query(DictionaryEntry).count()
            
            if final_count >= 100000:
                logger.info(f"✓ Self-healing complete: {final_count:,} entries loaded")
                return {
                    "ready": True,
                    "count": final_count,
                    "message": f"Dictionary auto-seeded ({final_count:,} entries)"
                }
            else:
                logger.error(f"Seeding incomplete: only {final_count:,} entries")
                return {
                    "ready": False,
                    "count": final_count,
                    "message": f"Seeding incomplete ({final_count:,} entries)"
                }
    
    return {
        "ready": False,
        "count": 0,
        "message": "Failed to locate dictionary file"
    }


def seed_dictionary_from_cedict(cedict_path: str):
    """
    Seed dictionary from CC-CEDICT file
    
    Args:
        cedict_path: Path to CC-CEDICT .u8 file
    """
    print(f"Seeding dictionary from {cedict_path}...")
    
    with get_db() as db:
        # Check if already seeded
        count = db.query(DictionaryEntry).count()
        if count > 0:
            print(f"✓ Dictionary already seeded with {count} entries")
            return
        
        entries_added = 0
        batch = []
        batch_size = 1000
        
        try:
            with open(cedict_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if line.startswith('#') or not line:
                        continue
                    
                    # Parse CEDICT format: 繁體 简体 [pin1 yin1] /definition1/definition2/
                    match = re.match(r'(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/', line)
                    if match:
                        traditional, simplified, pinyin_text, definitions = match.groups()
                        definitions_list = definitions.split('/')
                        
                        entry = DictionaryEntry.from_cedict(
                            traditional=traditional,
                            simplified=simplified,
                            pinyin=pinyin_text,
                            definitions_list=definitions_list
                        )
                        
                        batch.append(entry)
                        entries_added += 1
                        
                        # Commit in batches for performance
                        if len(batch) >= batch_size:
                            db.bulk_save_objects(batch)
                            db.commit()
                            batch = []
                            print(f"  Added {entries_added} entries...")
                
                # Commit remaining entries
                if batch:
                    db.bulk_save_objects(batch)
                    db.commit()
            
            print(f"✓ Dictionary seeded with {entries_added} entries")
            
        except FileNotFoundError:
            print(f"✗ CEDICT file not found at {cedict_path}")
            print("  Please download CC-CEDICT or place cedict_ts.u8 in the data directory")
        except Exception as e:
            print(f"✗ Error seeding dictionary: {e}")
            db.rollback()
