"""Main Flask application for ChAnki"""
from flask import Flask, render_template, request, jsonify
from config import Config
from services.dictionary import DictionaryService
from services.llm_service import LLMService
from services.anki_service import AnkiService

app = Flask(__name__)
app.config.from_object(Config)

# Initialize services
dictionary = DictionaryService(Config.CEDICT_PATH)
llm = LLMService(Config.OLLAMA_BASE_URL, Config.OLLAMA_MODEL)
anki = AnkiService(Config.ANKI_CONNECT_URL)


@app.route('/')
def index():
    """Render the main search interface"""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def search():
    """
    Search for Chinese words
    
    Request JSON:
        {
            "query": "hello" | "ni hao" | "你好"
        }
    
    Response JSON:
        {
            "success": true,
            "results": [
                {
                    "hanzi": "你好",
                    "pinyin": "nǐ hǎo",
                    "definitions": ["hello", "hi"]
                }
            ]
        }
    """
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query is required'
        }), 400
    
    try:
        results = dictionary.search(query)
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/generate-cloze', methods=['POST'])
def generate_cloze():
    """
    Generate cloze deletion sentence for a word
    
    Request JSON:
        {
            "hanzi": "你好",
            "pinyin": "nǐ hǎo",
            "definition": "hello"
        }
    
    Response JSON:
        {
            "success": true,
            "sentence": "{{c1::你好}}，很高兴见到你。",
            "translation": "Hello, nice to meet you."
        }
    """
    data = request.get_json()
    hanzi = data.get('hanzi', '').strip()
    pinyin = data.get('pinyin', '').strip()
    definition = data.get('definition', '').strip()
    
    if not all([hanzi, pinyin, definition]):
        return jsonify({
            'success': False,
            'error': 'Hanzi, pinyin, and definition are required'
        }), 400
    
    try:
        result = llm.generate_cloze_sentence(hanzi, pinyin, definition)
        return jsonify({
            'success': True,
            'sentence': result['sentence'],
            'translation': result['translation']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/check-duplicate', methods=['POST'])
def check_duplicate():
    """
    Check if word already exists in Anki deck
    
    Request JSON:
        {
            "hanzi": "你好"
        }
    
    Response JSON:
        {
            "success": true,
            "exists": true
        }
    """
    data = request.get_json()
    hanzi = data.get('hanzi', '').strip()
    
    if not hanzi:
        return jsonify({
            'success': False,
            'error': 'Hanzi is required'
        }), 400
    
    try:
        exists = anki.check_duplicate(hanzi, Config.ANKI_DECK_NAME)
        return jsonify({
            'success': True,
            'exists': exists
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/add-to-anki', methods=['POST'])
def add_to_anki():
    """
    Add a new card to Anki
    
    Request JSON:
        {
            "hanzi": "你好",
            "pinyin": "nǐ hǎo",
            "definition": "hello",
            "sentence": "{{c1::你好}}，很高兴见到你。",
            "translation": "Hello, nice to meet you."
        }
    
    Response JSON:
        {
            "success": true,
            "message": "Card added successfully"
        }
    """
    data = request.get_json()
    hanzi = data.get('hanzi', '').strip()
    pinyin = data.get('pinyin', '').strip()
    definition = data.get('definition', '').strip()
    sentence = data.get('sentence', '').strip()
    translation = data.get('translation', '').strip()
    
    if not all([hanzi, pinyin, definition, sentence, translation]):
        return jsonify({
            'success': False,
            'error': 'All fields are required'
        }), 400
    
    try:
        # Check if AnkiConnect is running
        if not anki.check_connection():
            return jsonify({
                'success': False,
                'error': 'AnkiConnect is not running. Please start Anki.'
            }), 503
        
        # Add the note
        success = anki.add_note(
            hanzi=hanzi,
            pinyin=pinyin,
            definition=definition,
            cloze_sentence=sentence,
            cloze_translation=translation,
            deck_name=Config.ANKI_DECK_NAME
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Card added successfully to Anki!'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add card to Anki'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
def status():
    """
    Check status of all services
    
    Response JSON:
        {
            "dictionary": true,
            "llm": true,
            "anki": true
        }
    """
    return jsonify({
        'dictionary': len(dictionary.entries) > 0,
        'llm': llm.check_connection(),
        'anki': anki.check_connection()
    })


if __name__ == '__main__':
    print("Starting ChAnki application...")
    print(f"Dictionary entries loaded: {len(dictionary.entries)}")
    print(f"Anki deck: {Config.ANKI_DECK_NAME}")
    print(f"LLM model: {Config.OLLAMA_MODEL}")
    app.run(debug=True, host='0.0.0.0', port=5173)

