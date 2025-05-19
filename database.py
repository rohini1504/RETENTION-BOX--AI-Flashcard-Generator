import sqlite3
from hashlib import sha256
from datetime import datetime, timedelta
def get_connection():
    return sqlite3.connect("flashcards.db", check_same_thread=False)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Flashcards table with spaced repetition fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            interval INTEGER DEFAULT 1,
            ease REAL DEFAULT 2.5,
            next_review DATE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

# Hash password
def hash_password(password):
    return sha256(password.encode()).hexdigest()

# Register a user
def register_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                       (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Authenticate user
def authenticate_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ? AND password_hash = ?", 
                   (username, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

# Retrieve details of all users (admin-like functionality)
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users")
    results = cursor.fetchall()
    conn.close()
    return results

# Retrieve details of currently logged-in user (assuming session management)
def get_logged_in_user(session_user_id):
    if session_user_id is None:
        return None  # No user logged in
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE id = ?", (session_user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Save new flashcard with initial spaced repetition values
def save_flashcard(user_id, question, answer, interval=1, ease=2.5, next_review=None):
    conn = get_connection()
    cursor = conn.cursor()
    if next_review is None:
        next_review = (datetime.today() + timedelta(days=interval)).date()

    try:
        cursor.execute("""
            INSERT INTO flashcards (user_id, question, answer, interval, ease, next_review)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, question, answer, interval, ease, next_review))
        conn.commit()
        print(f"Flashcard saved for user_id {user_id}")
    except Exception as e:
        print(f"Error inserting flashcard: {e}")
    finally:
        conn.close()


# Get all flashcards for a user
def get_flashcards(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, question, answer, interval, ease, next_review
        FROM flashcards
        WHERE user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "interval": row[3],
            "ease": row[4],
            "next_review": str(row[5])
        }
        for row in rows
    ]


# Get flashcards due for review
def get_due_flashcards(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.today().date()
    cursor.execute("""
        SELECT id, question, answer, interval, ease, next_review
        FROM flashcards
        WHERE user_id = ? AND date(next_review) <= ?
    """, (user_id, today))
    results = cursor.fetchall()
    conn.close()
    return results

# Update flashcard review using a simplified SuperMemo 2 algorithm
def update_flashcard_review(card_id, quality):
    """
    `quality` should be an integer from 0 to 5:
    5 - perfect response
    4 - correct response after hesitation
    3 - correct response with difficulty
    2 or less - incorrect or complete blackout
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch current interval and ease
    cursor.execute("SELECT interval, ease FROM flashcards WHERE id = ?", (card_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False  

    interval, ease = row

    if quality < 3:
        interval = 1
    else:
        ease = max(1.3, ease + 0.1 - (5 - quality) * 0.08)
        interval = int(interval * ease)

    next_review = (datetime.today() + timedelta(days=interval)).date()

    cursor.execute("""
        UPDATE flashcards
        SET interval = ?, ease = ?, next_review = ?
        WHERE id = ?
    """, (interval, ease, next_review, card_id))

    conn.commit()
    conn.close()
    return True


def update_flashcard(username, question, interval, ease, next_review):
    conn = sqlite3.connect("flashcards.db")
    c = conn.cursor()

    # First, retrieve the user_id from the username
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = c.fetchone()

    if not user_id:
        conn.close()
        return False 

    user_id = user_id[0]
    c.execute("""
        UPDATE flashcards 
        SET interval=?, ease=?, next_review=?
        WHERE user_id=? AND question=?
    """, (interval, ease, next_review, user_id, question))

    conn.commit()
    conn.close()
    return True
