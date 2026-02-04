#!/usr/bin/env python3
"""Script to seed the dictionary database from CC-CEDICT file"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.init_db import initialize_database, seed_dictionary_from_cedict


def main():
    """Main seeding function"""
    print("=" * 60)
    print("ChAnki v2 - Dictionary Database Seeding")
    print("=" * 60)
    
    # Initialize database
    initialize_database()
    
    # Seed dictionary
    cedict_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data',
        'cedict_ts.u8'
    )
    
    seed_dictionary_from_cedict(cedict_path)
    
    print("=" * 60)
    print("✓ Database setup complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
