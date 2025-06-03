import streamlit as st
import toml
import google.generativeai as genai
import sqlite3
import os
from datetime import datetime
import PyPDF2
import docx
import io
import base64

# Initialize CV database
def init_cv_database():
    conn = sqlite3.connect('cv_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cvs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_type TEXT,
            candidate_name TEXT,
            summary TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Extract text from PDF
def extract_pdf_text(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

# Extract text from DOCX
def extract_docx_text(file):
    try:
        doc = docx.Document(file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return None

# Save CV to database
def save_cv_to_db(filename, content, file_type, candidate_name="", summary=""):
    conn = sqlite3.connect('cv_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cvs (filename, content, file_type, candidate_name, summary)
        VALUES (?, ?, ?, ?, ?)
    ''', (filename, content, file_type, candidate_name, summary))
    conn.commit()
    conn.close()

# Get all CVs from database
def get_all_cvs():
    conn = sqlite3.connect('cv_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cvs ORDER BY upload_date DESC')
    cvs = cursor.fetchall()
    conn.close()
    return cvs

# Delete CV from database
def delete_cv(cv_id):
    conn = sqlite3.connect('cv_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cvs WHERE id = ?', (cv_id,))
    conn.commit()
    conn.close()

# Get CV context for chatbot
def get_cv_context():
    cvs = get_all_cvs()
    if not cvs:
        return "No CVs are currently uploaded in the database."
    
    context = "Available CVs in database:\n\n"
    for cv in cvs:
        context += f"CV ID: {cv[0]}\n"
        context += f"Filename: {cv[1]}\n"
        context += f"Candidate: {cv[5] if cv[5] else 'Not specified'}\n"
        context += f"Upload Date: {cv[3]}\n"
        context += f"Summary: {cv[6] if cv[6] else 'No summary'}\n"
        context += f"Content Preview: {cv[2][:200]}...\n"
        context += "-" * 50 + "\n\n"
    
    return context

# Load secrets
config = toml.load(".streamlit/secrets.toml")

# Initialize database
init_cv_database()

# Configure Gemini
genai.configure(api_key=config['apiKEY']['GEMINI_API_KEY'])

# Load model with enhanced system instruction
system_prompt = """You are designed as HR assistant Chatbot that helps HR to analyze CVs of applicants. Your name is Eyts Ar. 

You specialize in:
- Analyzing and reviewing CVs/resumes from the uploaded database
- Identifying key qualifications and skills
- Comparing candidates against job requirements
- Providing hiring recommendations
- Suggesting interview questions based on candidate profiles
- Highlighting strengths and potential concerns in applications
- Offering insights on candidate fit for specific roles

When users ask about CVs, you have access to a database of uploaded CVs. You can:
- Analyze specific CVs by ID or filename
- Compare multiple candidates
- Search for candidates with specific skills
- Provide detailed CV reviews and recommendations

Always maintain a professional tone and provide constructive, actionable feedback to help HR teams make informed decisions. When referencing CVs, always mention the CV ID and candidate name for clarity."""

model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=system_prompt)

# Page config - wide layout to use full screen
st.set_page_config(
    page_title="Eyts Ar - HR Assistant", 
    page_icon="👔", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide sidebar for more space
)

# Tabs
tabs = st.tabs(["👔 HR Assistant", "📁 CV Upload", "⚙️ Settings", "📜 Logs"])

# Chatbot Tab
with tabs[0]:
    st.title("👔 Eyts Ar - HR Assistant")

    # Initialize session state
    if "chat" not in st.session_state:
        st.session_state.chat = model.start_chat(history=[])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Custom CSS
    st.markdown("""
    <style>
        /* Hide Streamlit default elements for more space */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
            max-width: 100%;
        }
        
        /* Main app container */
        .stApp > div {
            height: 100vh;
            overflow: hidden;
        }
        
        .chat-container {
            height: 65vh;
            min-height: 400px;
            overflow-y: auto;
            border: 2px solid #e1e5e9;
            border-radius: 15px;
            padding: 15px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            scroll-behavior: smooth;
        }
        
        .user-msg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: right;
            padding: 12px 16px;
            margin: 10px 0;
            border-radius: 18px 18px 5px 18px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            max-width: 80%;
            margin-left: auto;
            word-wrap: break-word;
        }
        
        .bot-msg {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-align: left;
            padding: 12px 16px;
            margin: 10px 0;
            border-radius: 18px 18px 18px 5px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            max-width: 80%;
            margin-right: auto;
            word-wrap: break-word;
        }
        
        .message-wrapper {
            display: flex;
            flex-direction: column;
        }
        
        .empty-chat {
            text-align: center;
            color: #666;
            font-style: italic;
            margin-top: 30%;
            transform: translateY(-50%);
        }
        
        /* Compact title */
        .main h1 {
            margin-top: 0;
            margin-bottom: 1rem;
            font-size: 2rem;
        }
        
        /* Make input area more compact */
        .stChatInput {
            margin-top: 10px;
        }
        
        /* Hide streamlit footer and other elements */
        footer {
            visibility: hidden;
        }
        
        .stDeployButton {
            display: none;
        }
        
        header[data-testid="stHeader"] {
            height: 0;
        }
    </style>
    """, unsafe_allow_html=True)

    # Chat display container
    chat_container = st.container()
    
    with chat_container:
        if st.session_state.messages:
            # Build chat HTML
            chat_html = "<div class='chat-container'>"
            
            for msg in st.session_state.messages:
                role_class = "user-msg" if msg["role"] == "user" else "bot-msg"
                # Escape HTML and preserve line breaks
                content = msg["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                chat_html += f"<div class='{role_class}'>{content}</div>"
            
            chat_html += "</div>"
            
            # Enhanced auto-scroll with multiple fallback methods
            import time
            timestamp = int(time.time() * 1000)
            
            st.markdown(f"""
            {chat_html}
            <script>
                // Multiple scroll attempts for better reliability
                function scrollToBottom() {{
                    try {{
                        // Method 1: Find by class name
                        var containers = window.parent.document.getElementsByClassName('chat-container');
                        if (containers.length > 0) {{
                            var container = containers[containers.length - 1];
                            container.scrollTop = container.scrollHeight;
                            return true;
                        }}
                        
                        // Method 2: Find by CSS selector
                        var container = window.parent.document.querySelector('.chat-container');
                        if (container) {{
                            container.scrollTop = container.scrollHeight;
                            return true;
                        }}
                        
                        return false;
                    }} catch (e) {{
                        console.log('Auto-scroll failed:', e);
                        return false;
                    }}
                }}
                
                // Try scrolling multiple times with increasing delays
                setTimeout(scrollToBottom, 50);
                setTimeout(scrollToBottom, 100);
                setTimeout(scrollToBottom, 200);
                setTimeout(scrollToBottom, 500);
                
                // Also try when the page is fully loaded
                if (window.parent.document.readyState === 'complete') {{
                    scrollToBottom();
                }} else {{
                    window.parent.document.addEventListener('DOMContentLoaded', scrollToBottom);
                }}
            </script>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='chat-container'>
                <div class='empty-chat'>
                    👋 Hello! I'm Eyts Ar, your HR assistant.<br>
                    I help analyze CVs and support your hiring decisions.<br>
                    Upload a CV or ask me anything about recruitment!
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Input at bottom with HR-specific placeholder
    prompt = st.chat_input("Ask about CV analysis, hiring decisions, or upload a resume...")

    if prompt:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get bot response with CV context
        try:
            with st.spinner("🤔 Analyzing..."):
                # Add CV context to the conversation
                cv_context = get_cv_context()
                enhanced_prompt = f"CV Database Context:\n{cv_context}\n\nUser Query: {prompt}"
                
                response = st.session_state.chat.send_message(enhanced_prompt)
                bot_reply = response.text
            
            # Add bot response
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            
            # Rerun to update the chat display
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

# CV Upload Tab
with tabs[1]:
    st.title("📁 CV Upload & Management")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Upload New CV")
        
        # File uploader
        uploaded_files = st.file_uploader(
            "Choose CV files", 
            accept_multiple_files=True,
            type=['pdf', 'docx', 'txt'],
            help="Supported formats: PDF, DOCX, TXT"
        )
        
        # Candidate name input
        candidate_name = st.text_input("Candidate Name (Optional)", placeholder="Enter candidate's name")
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if st.button(f"📤 Upload {uploaded_file.name}", key=f"upload_{uploaded_file.name}"):
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        # Extract text based on file type
                        file_type = uploaded_file.name.split('.')[-1].lower()
                        
                        if file_type == 'pdf':
                            content = extract_pdf_text(uploaded_file)
                        elif file_type == 'docx':
                            content = extract_docx_text(uploaded_file)
                        elif file_type == 'txt':
                            content = str(uploaded_file.read(), "utf-8")
                        else:
                            st.error("Unsupported file format")
                            continue
                        
                        if content:
                            # Generate summary using Gemini
                            try:
                                summary_prompt = f"Analyze this CV and provide a brief summary (2-3 sentences) highlighting key skills, experience, and qualifications:\n\n{content[:2000]}"
                                summary_response = model.generate_content(summary_prompt)
                                summary = summary_response.text
                            except:
                                summary = "Summary generation failed"
                            
                            # Save to database
                            save_cv_to_db(
                                uploaded_file.name, 
                                content, 
                                file_type, 
                                candidate_name if candidate_name else "",
                                summary
                            )
                            
                            st.success(f"✅ {uploaded_file.name} uploaded successfully!")
                            st.rerun()
    
    with col2:
        st.subheader("Upload Statistics")
        cvs = get_all_cvs()
        
        st.metric("Total CVs", len(cvs))
        
        if cvs:
            pdf_count = len([cv for cv in cvs if cv[4] == 'pdf'])
            docx_count = len([cv for cv in cvs if cv[4] == 'docx'])
            txt_count = len([cv for cv in cvs if cv[4] == 'txt'])
            
            st.metric("PDF Files", pdf_count)
            st.metric("DOCX Files", docx_count)
            st.metric("TXT Files", txt_count)
    
    st.divider()
    
    # CV Management Section
    st.subheader("📋 CV Database")
    
    cvs = get_all_cvs()
    
    if cvs:
        # Search functionality
        search_term = st.text_input("🔍 Search CVs", placeholder="Search by filename or candidate name...")
        
        # Filter CVs based on search
        if search_term:
            filtered_cvs = [cv for cv in cvs if 
                           search_term.lower() in cv[1].lower() or 
                           search_term.lower() in (cv[5] or "").lower()]
        else:
            filtered_cvs = cvs
        
        if filtered_cvs:
            for cv in filtered_cvs:
                with st.expander(f"📄 {cv[1]} - {cv[5] if cv[5] else 'Unknown Candidate'}", expanded=False):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**CV ID:** {cv[0]}")
                        st.write(f"**Filename:** {cv[1]}")
                        st.write(f"**Candidate:** {cv[5] if cv[5] else 'Not specified'}")
                        st.write(f"**Upload Date:** {cv[3]}")
                        st.write(f"**File Type:** {cv[4].upper()}")
                        
                        if cv[6]:
                            st.write("**Summary:**")
                            st.info(cv[6])
                    
                    with col2:
                        if st.button("👁️ Preview", key=f"preview_{cv[0]}"):
                            st.text_area("Content Preview", cv[2][:500] + "...", height=200, key=f"content_{cv[0]}")
                    
                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_{cv[0]}", type="secondary"):
                            delete_cv(cv[0])
                            st.success("CV deleted successfully!")
                            st.rerun()
        else:
            st.info("No CVs match your search criteria.")
    else:
        st.info("📝 No CVs uploaded yet. Upload some CVs to get started!")
        st.markdown("""
        **Tips for better CV analysis:**
        - Upload CVs in PDF or DOCX format for best text extraction
        - Include candidate names for easier identification
        - Use descriptive filenames
        - The chatbot can analyze and compare uploaded CVs automatically
        """)

# Settings tab
with tabs[2]:
    st.title("⚙️ Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Chat Management")
        if st.button("🧹 Clear Chat", type="primary"):
            st.session_state.chat = model.start_chat(history=[])
            st.session_state.messages = []
            st.success("✅ Chat cleared successfully!")
            st.rerun()
    
    with col2:
        st.subheader("Statistics")
        message_count = len(st.session_state.get("messages", []))
        user_messages = len([m for m in st.session_state.get("messages", []) if m["role"] == "user"])
        bot_messages = len([m for m in st.session_state.get("messages", []) if m["role"] == "assistant"])
        
        st.metric("Total Messages", message_count)
        st.metric("Your Messages", user_messages)
        st.metric("Bot Responses", bot_messages)

# Logs tab
with tabs[3]:
    st.title("📜 Conversation Logs")
    
    if st.session_state.get("messages"):
        # Add export functionality
        col1, col2 = st.columns([3, 1])
        
        with col2:
            if st.button("📥 Export Chat"):
                chat_text = ""
                for msg in st.session_state.messages:
                    role = "You" if msg["role"] == "user" else "Gemini"
                    chat_text += f"{role}: {msg['content']}\n\n"
                
                st.download_button(
                    label="💾 Download as TXT",
                    data=chat_text,
                    file_name="gemini_chat_log.txt",
                    mime="text/plain"
                )
        
        # Display messages with better formatting
        for i, msg in enumerate(st.session_state.messages):
            with st.expander(f"💬 Message {i+1} - {msg['role'].capitalize()}", expanded=False):
                st.write(msg['content'])
                st.caption(f"Message ID: {i+1}")
    else:
        st.info("📝 No conversation history yet. Start chatting to see logs here!")
        st.markdown("---")
        st.markdown("💡 **Tip**: All your conversations will be logged here for easy reference.")