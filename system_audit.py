#!/usr/bin/env python3
"""
ChAnki System Audit Script
Purpose: Deep diagnostic of all system components (read-only)
Role: Principal Software Architect & SRE
"""

import os
import sys
import sqlite3
import requests
import time
from pathlib import Path

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {text}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠{Colors.ENDC} {text}")

def print_error(text):
    print(f"{Colors.FAIL}✗{Colors.ENDC} {text}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {text}")

# ============================================================================
# PHASE 1: FILESYSTEM INTEGRITY
# ============================================================================

def check_filesystem():
    print_header("PHASE 1: FILESYSTEM INTEGRITY")
    
    issues = []
    
    # Check requirements.txt
    print(f"{Colors.BOLD}Checking requirements.txt...{Colors.ENDC}")
    required_libs = [
        'fastapi',
        'uvicorn',
        'requests',
        'sqlalchemy',
        'openai',
        'jieba',
        'edge-tts',
        'pydantic'
    ]
    
    if os.path.exists('requirements.txt'):
        with open('requirements.txt', 'r') as f:
            content = f.read().lower()
            for lib in required_libs:
                if lib.lower() in content:
                    print_success(f"{lib} found in requirements.txt")
                else:
                    print_error(f"{lib} MISSING from requirements.txt")
                    issues.append(f"Missing library: {lib}")
    else:
        print_error("requirements.txt NOT FOUND")
        issues.append("requirements.txt missing")
    
    # Check dictionary file
    print(f"\n{Colors.BOLD}Checking dictionary file...{Colors.ENDC}")
    dict_path = Path('data/cedict_ts.u8')
    
    if dict_path.exists():
        size_mb = dict_path.stat().st_size / (1024 * 1024)
        print_success(f"Dictionary file found: {dict_path} ({size_mb:.2f} MB)")
    else:
        print_error(f"Dictionary file NOT FOUND: {dict_path}")
        print_info("Can download from: https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz")
        issues.append("Dictionary file missing")
    
    # Check critical directories
    print(f"\n{Colors.BOLD}Checking directory structure...{Colors.ENDC}")
    critical_dirs = ['app', 'app/api', 'app/services', 'app/models', 'static', 'data']
    for dir_name in critical_dirs:
        if os.path.exists(dir_name):
            print_success(f"Directory exists: {dir_name}")
        else:
            print_error(f"Directory MISSING: {dir_name}")
            issues.append(f"Missing directory: {dir_name}")
    
    return issues

# ============================================================================
# PHASE 2: DATABASE HEALTH (SQLite)
# ============================================================================

def check_database():
    print_header("PHASE 2: DATABASE HEALTH")
    
    issues = []
    db_path = 'data/chanki.db'
    
    if not os.path.exists(db_path):
        print_error(f"Database file NOT FOUND: {db_path}")
        issues.append("Database file missing")
        return issues
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # List all tables
        print(f"{Colors.BOLD}Database tables:{Colors.ENDC}")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print_info(f"Table: {table_name} - Rows: {count:,}")
        
        # Critical check: dictionary table
        print(f"\n{Colors.BOLD}Checking dictionary table...{Colors.ENDC}")
        if ('dictionary',) in tables:
            cursor.execute("SELECT COUNT(*) FROM dictionary")
            dict_count = cursor.fetchone()[0]
            
            if dict_count < 100000:
                print_error(f"CRITICAL: Dictionary table has only {dict_count:,} rows (Expected: >100,000)")
                print_warning("Status: EMPTY/CORRUPT")
                issues.append(f"Dictionary table insufficient: {dict_count} rows")
            else:
                print_success(f"Dictionary table healthy: {dict_count:,} rows")
        else:
            print_error("CRITICAL: 'dictionary' table does not exist")
            issues.append("Dictionary table missing")
        
        # Check settings table
        print(f"\n{Colors.BOLD}Checking settings table...{Colors.ENDC}")
        if ('settings',) in tables:
            cursor.execute("SELECT * FROM settings LIMIT 1")
            settings = cursor.fetchone()
            
            if settings:
                # Get column names
                cursor.execute("PRAGMA table_info(settings)")
                columns = [col[1] for col in cursor.fetchall()]
                settings_dict = dict(zip(columns, settings))
                
                # Mask API key
                if 'openai_api_key' in settings_dict and settings_dict['openai_api_key']:
                    masked_key = settings_dict['openai_api_key'][:8] + "..." + settings_dict['openai_api_key'][-4:]
                    print_info(f"OpenAI API Key: {masked_key}")
                else:
                    print_warning("OpenAI API Key: NOT SET")
                
                if 'anki_deck_name' in settings_dict:
                    print_info(f"Target Deck: {settings_dict['anki_deck_name']}")
                else:
                    print_warning("Target Deck: NOT SET")
            else:
                print_warning("Settings table is empty")
        else:
            print_error("Settings table does not exist")
            issues.append("Settings table missing")
        
        conn.close()
        
    except sqlite3.Error as e:
        print_error(f"Database error: {e}")
        issues.append(f"Database error: {e}")
    
    return issues

# ============================================================================
# PHASE 3: ANKICONNECT INTEGRATION
# ============================================================================

def check_anki():
    print_header("PHASE 3: ANKICONNECT INTEGRATION")
    
    issues = []
    anki_url = "http://localhost:8765"
    
    print(f"{Colors.BOLD}Testing AnkiConnect at {anki_url}...{Colors.ENDC}")
    
    try:
        payload = {
            "action": "version",
            "version": 6
        }
        
        response = requests.post(anki_url, json=payload, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            version = data.get('result')
            print_success(f"AnkiConnect is ONLINE (Version: {version})")
            
            # Request deck names
            print(f"\n{Colors.BOLD}Fetching deck list...{Colors.ENDC}")
            deck_payload = {
                "action": "deckNames",
                "version": 6
            }
            
            deck_response = requests.post(anki_url, json=deck_payload, timeout=3)
            if deck_response.status_code == 200:
                deck_data = deck_response.json()
                decks = deck_data.get('result', [])
                
                if decks:
                    print_success(f"Found {len(decks)} deck(s):")
                    for deck in decks:
                        print_info(f"  • {deck}")
                else:
                    print_warning("No decks found in Anki")
            else:
                print_error("Failed to fetch deck names")
                issues.append("Cannot fetch Anki decks")
        else:
            print_error(f"AnkiConnect returned status code: {response.status_code}")
            issues.append("AnkiConnect error")
    
    except requests.exceptions.ConnectionError:
        print_error("CRITICAL: Anki is not running")
        print_info("Please start Anki and ensure AnkiConnect add-on is installed")
        issues.append("Anki not running")
    
    except requests.exceptions.Timeout:
        print_error("AnkiConnect request timed out")
        issues.append("AnkiConnect timeout")
    
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        issues.append(f"AnkiConnect error: {e}")
    
    return issues

# ============================================================================
# PHASE 4: OPENAI INTEGRATION
# ============================================================================

def check_openai():
    print_header("PHASE 4: OPENAI INTEGRATION")

    issues = []
    api_key = None

    # Try to load API key from .env
    print(f"{Colors.BOLD}Loading API key...{Colors.ENDC}")

    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY'):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    print_info("API key found in .env")
                    break

    # Try from database if not in .env
    if not api_key:
        if os.path.exists('data/chanki.db'):
            try:
                conn = sqlite3.connect('data/chanki.db')
                cursor = conn.cursor()
                cursor.execute("SELECT openai_api_key FROM settings LIMIT 1")
                result = cursor.fetchone()
                if result and result[0]:
                    api_key = result[0]
                    print_info("API key found in database")
                conn.close()
            except Exception:
                pass

    if not api_key:
        print_warning("No OpenAI API key found")
        print_info("Set OPENAI_API_KEY in .env or configure in Settings")
        issues.append("OpenAI API key missing")
        return issues

    # Test OpenAI — read-only models.list() call, no token cost
    print(f"\n{Colors.BOLD}Testing OpenAI API (models.list)...{Colors.ENDC}")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        start_time = time.time()
        models = list(client.models.list())
        latency = (time.time() - start_time) * 1000

        model_ids = {m.id for m in models}
        if "gpt-4o-mini" in model_ids:
            print_success(f"OpenAI API is ONLINE — gpt-4o-mini available")
        else:
            print_success(f"OpenAI API is ONLINE ({len(models)} models listed)")
            print_warning("gpt-4o-mini not found in model list — check org access")
        print_info(f"Latency: {latency:.0f}ms")

    except ImportError:
        print_error("openai library not installed")
        print_info("Run: pip install openai")
        issues.append("openai not installed")

    except Exception as e:
        print_error(f"OpenAI API error: {e}")
        issues.append(f"OpenAI API error: {e}")

    return issues

# ============================================================================
# PHASE 5: LOCAL SERVER CHECK
# ============================================================================

def check_server():
    print_header("PHASE 5: LOCAL SERVER CHECK")
    
    issues = []
    port = 8000
    
    print(f"{Colors.BOLD}Checking port {port}...{Colors.ENDC}")
    
    try:
        response = requests.get(f"http://localhost:{port}", timeout=2)
        print_warning(f"Port {port} is IN USE (Server may already be running)")
        print_info(f"Status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print_success(f"Port {port} is FREE (ready for uvicorn)")
    except requests.exceptions.Timeout:
        print_warning(f"Port {port} is IN USE but not responding")
    except Exception as e:
        print_error(f"Error checking port: {e}")
    
    return issues

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print(f"\n{Colors.BOLD}{Colors.OKCYAN}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                   ChAnki System Audit v1.0                        ║")
    print("║              Comprehensive Health & Stability Check               ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")
    
    all_issues = []
    
    # Run all checks
    all_issues.extend(check_filesystem())
    all_issues.extend(check_database())
    all_issues.extend(check_anki())
    all_issues.extend(check_openai())
    all_issues.extend(check_server())
    
    # Final summary
    print_header("AUDIT SUMMARY")
    
    if all_issues:
        print_error(f"Found {len(all_issues)} issue(s):\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {Colors.FAIL}{i}.{Colors.ENDC} {issue}")
        print(f"\n{Colors.WARNING}{Colors.BOLD}System Status: NEEDS ATTENTION{Colors.ENDC}")
        return 1
    else:
        print_success("All systems operational!")
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}System Status: HEALTHY{Colors.ENDC}")
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Audit interrupted by user{Colors.ENDC}")
        sys.exit(130)
