import streamlit as st
import pdfplumber
import wikipedia
import re
import datetime
import google.generativeai as genai
from wikipedia.exceptions import DisambiguationError, PageError
from reportlab.pdfgen import canvas
from io import BytesIO
from database import (
    initialize_db, register_user, authenticate_user, 
    save_flashcard, get_flashcards
)


initialize_db()
GEMINI_API_KEY =""
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")
def generate_flashcards_pdf(flashcards):
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    y = 800  

    for i, card in enumerate(flashcards, 1):
        question = card['question']
        answer = card['answer']
        p.drawString(50, y, f"Q{i}: {question}")
        y -= 20
        p.drawString(50, y, f"A{i}: {answer}")
        y -= 40
        if y < 100:
            p.showPage()
            y = 800

    p.save()
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="Flashcard Generator",  layout="wide")
st.markdown("""
    <style>
    body, .stApp {
        background-color:#000000;
        font-family: 'Segoe UI', sans-serif;
        color: #007f68; 
    }
    .stTitle {
        color:  #205781;
        font-size: 40px;
        font-weight: 700;
        padding-bottom: 1rem;
    }
.stButton>button {
    background: linear-gradient(135deg, #007f68, #00bfa6);
    color: #ffffff;
    font-weight: 600;
    padding: 0.6em 1.2em;
    border-radius: 10px;
    border: none;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 127, 104, 0.3);
}

.stButton>button:hover {
    background: linear-gradient(135deg, #00bfa6, #009e84);
    color: #ffffff;
    transform: scale(1.03);
    box-shadow: 0 6px 14px rgba(0, 127, 104, 0.5);
}

.stButton>button:focus {
    outline: none;
    border: 2px solid #007f68;
}
    .stTextInput>div>input {
        background-color: #1c1c1c;
        color: #f5f5f5;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 0.5rem;
    }

    .stTextInput>div>input:focus {
        border: 1px solid #007f68;
        background-color: #262626;
        color: #fff;
    }
    .stFileUploader {
        max-width: 550px;
        margin: 2 auto; 
        min-height:250px 
    }
    .stFileUploader > div > div > div {
        background-color: #1a1a1a;
        border: 3px dashed #007f68;
        padding: 2em 2em;
        border-radius: 14px;
        min-height: 100px;
        text-align: center;
        font-size: 18px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }

    .stFileUploader > div > div > div:hover {
        background-color: #292929;
    }

    .stFileUploader label {
        display: flex !important;
        justify-content: center !important;
        width:50%;
    }
    .flashcard {
        background-color: #1e1e1e;
        border-radius: 14px;
        padding: 20px;
        margin-top: 20px;
        margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(252, 163, 17, 0.2);
        transition: all 0.3s ease;
    }

    .flashcard:hover {
        background-color: #00bfa6;
        transform: scale(1.01);
    }
    .stMarkdown h3 {
        font-family: 'Poppins', sans-serif;
        font-size: 32px;
        color: #007f68;
        font-weight: 600;
        margin-bottom: 1em;
    }

    .stMarkdown p {
        font-size: 18px;
        line-height: 1.6;
        color:#ffffff
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)
def signup(username, password):
    return register_user(username, password)

def login(username, password):
    return authenticate_user(username, password)

def extract_text(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())

def extract_topic(text):
    for line in text.split("\n"):
        if line.strip() and len(line.split()) > 2:
            return line.strip()
    return "Artificial Intelligence"

def fetch_wikipedia(topic):
    try:
        page = wikipedia.page(topic, auto_suggest=False)
        if any(bad in page.title.lower() for bad in ["porn", "sex", "xxx", "fucking"]):
            raise ValueError("Inappropriate topic")
        return page.content
    except (DisambiguationError, PageError, ValueError):
        return ""

def clean_output(text):
    text = re.sub(r"\*\*+", "", text)
    text = re.sub(r"#+", "", text)
    return text.strip()

def parse_flashcards(text):
    cards = []
    mcq_pattern = re.compile(
        r"Q: (.*?)\nOptions:\s*a\) (.*?)\n\s*b\) (.*?)\n\s*c\) (.*?)\n\s*d\) (.*?)\nAnswer: ([a-dA-D])",
        re.DOTALL
    )

    for match in mcq_pattern.finditer(text):
        question = match.group(1).strip()
        options = [match.group(2).strip(), match.group(3).strip(), match.group(4).strip(), match.group(5).strip()]
        answer_letter = match.group(6).lower()
        answer_index = {"a": 0, "b": 1, "c": 2, "d": 3}.get(answer_letter, 0)
        card = {
            "question": question,
            "options": options,
            "answer": options[answer_index],
            "interval": 1,
            "ease": 2.5,
            "next_review": str(datetime.date.today())
        }
        cards.append(card)

    if not cards:
        qa_pairs = re.findall(r"(?:Q(?:uestion)?:|Q:)\s*(.*?)\s*(?:A(?:nswer)?:|A:)\s*(.*?)(?=\n(?:Q(?:uestion)?:|Q:)|\Z)", text, re.DOTALL)
        for q, a in qa_pairs:
            card = {
                "question": q.strip(),
                "answer": a.strip(),
                "interval": 1,
                "ease": 2.5,
                "next_review": str(datetime.date.today())
            }
            cards.append(card)

    return cards

def update_review(card, feedback):
    today = datetime.date.today()
    if feedback == "again":
        card['interval'] = 1
        card['ease'] = max(1.3, card['ease'] - 0.2)
    elif feedback == "hard":
        card['interval'] = int(card['interval'] * 1.2)
        card['ease'] = max(1.3, card['ease'] - 0.05)
    elif feedback == "easy":
        card['interval'] = int(card['interval'] * card['ease'])
        card['ease'] = min(2.5, card['ease'] + 0.1)
    card['next_review'] = str(today + datetime.timedelta(days=card['interval']))
    return card

def build_prompt(pdf_text, wiki_text, card_type, difficulty):
    task_map = {
        "Q&A": {
            "Easy": "Generate 6 simple Q&A flashcards. Format:\nQ: <question>\nA: <answer>",
            "Medium": "Generate 6 Q&A flashcards. Format:\nQ: <question>\nA: <answer>",
            "Hard": "Generate 6 challenging Q&A flashcards. Format:\nQ: <question>\nA: <answer>",
        },
        "MCQ": {
            "Easy": "Generate 6 MCQs with 4 options. Format:\nQ: <question>\nOptions:\na) ...\nb) ...\nc) ...\nd) ...\nAnswer: <correct option>",
            "Medium": "Generate 6 MCQs testing concepts. Same format as above.",
            "Hard": "Generate 6 reasoning-based MCQs. Same format as above.",
        },
        "Fill-in-the-Blank": {
            "Easy": "Generate 6 easy fill-in-the-blanks. Format:\nQ: <sentence with blank>\nAnswer: <answer>",
            "Medium": "Generate 6 context-based fill-in-the-blanks. Format:\nQ: <sentence with blank>\nAnswer: <answer>",
            "Hard": "Generate 6 reasoning-based fill-in-the-blanks. Format:\nQ: <sentence with blank>\nAnswer: <answer>",
        },
    }
    instruction = task_map[card_type][difficulty]
    return f"""
You are an AI flashcard generator for students.

{instruction}

 Do NOT include:
- Chapter numbers
- Author names
- Metadata like 'This chapter explains...'

 Only include:
- Key concepts
- Definitions
- Explanations
- Applications
- Comparisons
- Theoretical understanding

Use only the content below to generate flashcards:

PDF:
{pdf_text[:3000]}

Wikipedia:
{wiki_text[:3000]}
"""

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if not st.session_state.logged_in:
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.markdown("""
            <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;700&family=Roboto:wght@700&display=swap" rel="stylesheet">

            <div style='padding-top: 50px;'>
                <h1 style="
                    font-size: 60px;
                    color:#007f68;
                    font-family: 'Roboto', sans-serif;
                ">
                    RETENTION BOX!
                </h1>
                <p style='
                    font-size: 20px;
                    color: #ccc;
                    font-family: "Raleway", sans-serif;
                '>
                    Create and review smart flashcards from any PDF.<br>
                    Fast, easy, and built for the grind.
                </p>
            </div>
        """, unsafe_allow_html=True)
    with col2:
           
            st.markdown("""<style>@import url('https://fonts.googleapis.com/css2?family=Raleway:wght@400;600&display=swap');.raleway-text {
        font-family: 'Raleway', sans-serif;font-size: 28px;font-weight: 600;}</style><div class="raleway-text">Login / Signup</div><br>""", unsafe_allow_html=True)

            tab1, tab2 = st.tabs(["Login", "Create Account"])

            with tab1:
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")

                if st.button("Login"):
                    if not username or not password:
                        st.error("Please enter both username and password!")
                    elif login(username, password):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            with tab2:
                username = st.text_input("Username", key="signup_username")
                password = st.text_input("Password", type="password", key="signup_password")
                confirm_password = st.text_input("Re-enter Password", type="password", key="confirm_password")

                if st.button("Create Account"):
                    if not username or not password or not confirm_password:
                        st.error("Please enter all fields!")
                    elif password != confirm_password:
                        st.error("Passwords do not match!")
                    elif signup(username, password):
                        st.success("Account created. You can now login!")
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error(" Username already exists or password too short.")

else:

    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("")
    with col2:
        if st.button("Logout"):
            st.session_state.logged_in = False
            del st.session_state.username
            st.session_state.flashcards = []
            st.session_state.current_index = 0
            st.session_state.show_answer = False
            st.rerun()

    st.markdown("""
        <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@600&display=swap" rel="stylesheet">
        <h5 style="font-family: 'Raleway', sans-serif; font-size: 36px; color:#007f68;">
            <i class="fa-regular fa-file" style="margin-right: 24px;color:#ffffff"></i> Upload a PDF
        </h5>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1])

    with left_col:
        uploaded_file = st.file_uploader(" ", type=["pdf"], label_visibility="collapsed")
        st.markdown("""
            <style>
                .stFileUploader > div > div > div {
                    background-color: #1a1a1a;
                    color: #007f68;
                    border: 3px dashed #007f68;
                    padding: 3em 2em;  /* top-bottom: 3em, left-right: 2em */
                    border-radius: 14px;
                    min-height: 220px;
                    text-align: center;
                    font-size: 18px;
                }
                .stFileUploader > div > div > div:hover {
                    background-color: #292929;
                }
            </style>
        """, unsafe_allow_html=True)


    with right_col:
        custom_topic = st.text_input("Optional: Specify topic (or leave blank to auto-detect)")

        col1, col2 = st.columns([1, 1])  
        with col1:
            card_type = st.selectbox("Select Flashcard Type", ["Q&A", "MCQ", "Fill-in-the-Blank"])
        with col2:
            difficulty = st.selectbox("Select Difficulty Level", ["Easy", "Medium", "Hard"])
        st.markdown("<br>", unsafe_allow_html=True)
        
    if "flashcards" not in st.session_state:
        st.session_state.flashcards = []

    if not st.session_state.flashcards and "user_id" in st.session_state:
        st.session_state.flashcards = get_flashcards(st.session_state.user_id)
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False
    if "flashcards" not in st.session_state:
        st.session_state.flashcards = []

    if st.button("Generate Flashcards"):
        if uploaded_file:
            text = extract_text(uploaded_file)
            topic = custom_topic if custom_topic else extract_topic(text)
            wiki = fetch_wikipedia(topic)
            prompt = build_prompt(text, wiki, card_type, difficulty)

            try:
                response = model.generate_content(prompt)
                raw = clean_output(response.text)
                flashcards = parse_flashcards(raw)

                if not flashcards:
                    st.warning("Warning: Couldn't parse flashcards. Showing raw Gemini output:")
                    st.text(raw)
                else:
                    st.session_state.flashcards = flashcards
                    st.session_state.current_index = 0
                    st.session_state.show_answer = False
                    for card in flashcards:
                     save_flashcard(st.session_state.username, card["question"], card["answer"], card["interval"], card["ease"], card["next_review"])

            except Exception as e:
                st.error(f"Warning: Error: {e}")
        else:
            st.warning("Warning:Please upload a PDF first.")

    if st.session_state.flashcards:
        idx = st.session_state.current_index
        card = st.session_state.flashcards[idx]

        st.markdown(f"### Flashcard {idx+1} of {len(st.session_state.flashcards)}")
        st.markdown(f"**Q:** {card['question']}")

        if "options" in card:
            selected = st.radio("Choose the correct option:", card["options"], key=f"mcq_{idx}")
            if st.button(" Show Answer"):
                st.success(f"Correct Answer: {card['answer']}")
        else:
            if st.button("Show Answer"):
                st.session_state.show_answer = True
            if st.session_state.show_answer:
                st.markdown(f"**A:** {card['answer']}")
        pdf_buffer = generate_flashcards_pdf(st.session_state.flashcards)
        st.download_button(
        label="Download All Flashcards as PDF",
        data=pdf_buffer,
        file_name="flashcards.pdf",
        mime="application/pdf"
        )

        cols = st.columns(4)

        if cols[0].button("Previous"):
            st.session_state.current_index = (st.session_state.current_index - 1) % len(st.session_state.flashcards)
            st.session_state.show_answer = False
            st.rerun()

        if cols[1].button("Next"):
            st.session_state.current_index = (idx + 1) % len(st.session_state.flashcards)
            st.session_state.show_answer = False
            st.rerun()

        from database import update_flashcard

        if cols[2].button(" Hard"):
           st.session_state.flashcards[idx] = update_review(card, "hard")
           update_flashcard(st.session_state.username, card["question"], card["interval"], card["ease"], card["next_review"])
           st.success("Feedback recorded as: Hard")

        if cols[3].button(" Easy"):
           st.session_state.flashcards[idx] = update_review(card, "easy")
           update_flashcard(st.session_state.username, card["question"], card["interval"], card["ease"], card["next_review"])
           st.success("Feedback recorded as: Easy")