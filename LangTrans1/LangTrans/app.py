import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
import pdfplumber
from deep_translator import GoogleTranslator
from pdf2image import convert_from_path
import pytesseract
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
UPLOAD_FOLDER = 'uploads/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

LANGUAGE_NAMES = {
    'af': 'Afrikaans', 'ar': 'Arabic', 'bn': 'Bengali', 'bg': 'Bulgarian',
    'ca': 'Catalan', 'zh-CN': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)',
    'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish', 'nl': 'Dutch', 'en': 'English',
    'et': 'Estonian', 'fil': 'Filipino', 'fi': 'Finnish', 'fr': 'French', 'de': 'German',
    'el': 'Greek', 'gu': 'Gujarati', 'he': 'Hebrew', 'hi': 'Hindi', 'hu': 'Hungarian',
    'id': 'Indonesian', 'it': 'Italian', 'ja': 'Japanese', 'kn': 'Kannada', 'ko': 'Korean',
    'lv': 'Latvian', 'lt': 'Lithuanian', 'ml': 'Malayalam', 'mr': 'Marathi', 'ne': 'Nepali',
    'no': 'Norwegian', 'pa': 'Punjabi', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
    'ru': 'Russian', 'sr': 'Serbian', 'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian',
    'es': 'Spanish', 'sw': 'Swahili', 'sv': 'Swedish', 'ta': 'Tamil', 'te': 'Telugu',
    'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese',
}

# Initialize SQLite DB
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def default_route():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = user[1]  # Assuming name is at index 1
            return redirect(url_for('welcome', welcome='1'))
        else:
            return render_template('login.html', error="Account does not exist. Please sign up.")
    
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return render_template('signup.html', error="User already exists")
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('signup.html')

                                                                                                                                                                     
@app.route('/logout')
def logout():
    session.pop('user', None)
    session['logout_message'] = "You're logged out 👋"
    return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    return render_template('index.html', language_names=LANGUAGE_NAMES, username=session.get('user'))

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/contact')
@login_required
def contact():
    return render_template('contact.html')

@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('pdf_file')
    if file and file.filename.endswith('.pdf'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        extracted_text = extract_text_from_pdf(file_path)
        return render_template(
            'view_pdf.html',
            file_path=file.filename,
            extracted_text=extracted_text,
            language_names=LANGUAGE_NAMES,
            uploaded_filename=file.filename
        )
    return "Invalid file format", 400

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return "Error: PDF file not found"
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    if text.strip():
        return text
    try:
        images = convert_from_path(pdf_path)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img) + "\n"
        return ocr_text if ocr_text.strip() else "No readable text found in the PDF (even with OCR)."
    except Exception as e:
        return f"OCR Error: {str(e)}"

@app.route('/translate_word', methods=['GET'])
@login_required
def translate_word():
    text = request.args.get('text')
    target_lang = request.args.get('lang', 'en')
    if not text:
        return jsonify({"translated_text": "No text provided"})
    try:
        translated_text = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return jsonify({"translated_text": translated_text})
    except Exception as e:
        return jsonify({"translated_text": f"Translation Error: {str(e)}"})

@app.route('/translate_pdf/<filename>', methods=['GET'])
@login_required
def translate_pdf(filename):
    target_lang = request.args.get('lang', 'en')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return "Error: PDF file not found"
    extracted_text = extract_text_from_pdf(file_path)
    try:
        translated_text = GoogleTranslator(source='auto', target=target_lang).translate(extracted_text)
    except Exception as e:
        translated_text = f"Translation Error: {str(e)}"
    return render_template('translated_pdf.html', translated_text=translated_text, target_lang=target_lang)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Final main block
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
