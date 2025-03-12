import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO
import pickle

# Load the fake news detection model and vectorizer
with open(r"D:\College Projects\Chat App\random_forest_model.pkl", "rb") as model_file:
    model = pickle.load(model_file)

with open("tfidf_vectorizer.pkl", "rb") as vectorizer_file:
    vectorizer = pickle.load(vectorizer_file)

app = Flask(__name__)
app.secret_key = "your_secret_key"
socketio = SocketIO(app)

def preprocess_text(text):
    """Preprocesses text by removing special characters, extra spaces, and converting to lowercase."""
    text = text.lower()  # Convert to lowercase
    text = re.sub(r'\s+', ' ', text)  # Remove extra spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)  # Remove special characters
    return text.strip()

def init_db():
    # Create 'databases' folder if it doesn't exist
    if not os.path.exists('databases'):
        os.makedirs('databases', exist_ok=True)

    # Initialize 'users.db'
    if not os.path.exists('databases/users.db'):
        conn = sqlite3.connect('databases/users.db')
        cursor = conn.cursor()

        # Create 'users' table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY,
                            name TEXT NOT NULL,
                            email TEXT NOT NULL,
                            password TEXT NOT NULL)''')

        # Create 'messages' table
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY,
                            content TEXT NOT NULL,
                            sender_id INTEGER NOT NULL,
                            timestamp TEXT NOT NULL,
                            fake_probability REAL NOT NULL,
                            FOREIGN KEY (sender_id) REFERENCES users(id))''')
        
        conn.commit()

        # Insert a sample user if the 'users' table is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', 
                           ('Sample User', 'sampleuser@example.com', 'password123'))
        
        # Insert a sample message if the 'messages' table is empty
        cursor.execute("SELECT COUNT(*) FROM messages")
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO messages (content, sender_id, timestamp, fake_probability) VALUES (?, ?, ?, ?)', 
                           ('This is a sample message.', 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0.1))
        
        conn.commit()
        conn.close()

# Initialize the database when the app starts
init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('databases/users.db')
    cursor = conn.cursor()
    cursor.execute("""SELECT messages.content, messages.timestamp, users.name, messages.sender_id, messages.fake_probability
                      FROM messages 
                      JOIN users ON messages.sender_id = users.id 
                      ORDER BY messages.timestamp ASC""")
    messages = cursor.fetchall()
    conn.close()

    return render_template('chat.html', messages=messages, user_id=session['user_id'], username=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'] 

        conn = sqlite3.connect('databases/users.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', 
                       (name, email, password))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('databases/users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user and user[3] == password:  # Check plain text password
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials. Please try again.'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' in session:
        content = request.form['content']
        sender_id = session['user_id']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # ✅ Preprocess the message
        processed_content = preprocess_text(content)

        # ✅ Convert to numerical features using TF-IDF
        transformed_content = vectorizer.transform([processed_content])

        # ✅ Predict fake news probability
        fake_probability = model.predict_proba(transformed_content)[0][1]

        # ✅ Store original message (optional) & processed content in DB
        conn = sqlite3.connect('databases/users.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO messages (content, sender_id, timestamp, fake_probability) VALUES (?, ?, ?, ?)', 
                       (content, sender_id, timestamp, fake_probability))
        conn.commit()
        conn.close()

        # Emit a refresh event to all connected clients
        socketio.emit('refresh_chat', broadcast=True)

    return '', 200

@socketio.on('connect')
def handle_connect():
    print("User connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("User disconnected")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
