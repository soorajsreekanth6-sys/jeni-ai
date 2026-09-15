from flask import Flask, request, jsonify, render_template_string, send_file, make_response, session, redirect, url_for
from groq import Groq
import edge_tts
import asyncio
import re
import os
import uuid
from pypdf import PdfReader
from dotenv import load_dotenv

# Load API Keys securely from .env file
load_dotenv(".env")

app = Flask(__name__)
app.secret_key = "sooraj_jeni_general_ai_secret_key_999"

# Securely load Groq client from environment variable
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- 1. SESSION-BASED HISTORY MANAGEMENT ---
def get_user_history():
    if 'chat_history' not in session:
        session['chat_history'] = []
    return session['chat_history']

def save_msg(role, content):
    history = get_user_history()
    history.append({"role": role, "content": content})
    session['chat_history'] = history[-6:]
    session.modified = True

# --- 2. KNOWLEDGE BASE (SAFE LOAD NEW PDF) ---
chunks = []
try:
    reader = PdfReader("Adaptive_Friendly_AI_Character_Manual.pdf")
    pdf_text = "".join([page.extract_text() + "\n" for page in reader.pages if page.extract_text()])
    # Increased chunk size to 4000 so the whole manual fits perfectly!
    chunks = [pdf_text[i:i + 4000] for i in range(0, len(pdf_text), 4000)]
except Exception as e:
    print("PDF Load Error (Ignoring):", e)

# --- 3. VOICE SETUP (MULTI-USER CRASH-PROOF) ---
async def speak(text, voice_name, filename):
    try:
        communicate = edge_tts.Communicate(text=text, voice=voice_name)
        await communicate.save(filename)
    except Exception as e:
        print("VOICE ERROR:", e)

def clean_text_for_voice(text):
    # Safely removing code blocks without breaking python string formatting
    clean_txt = text.replace("```" + "python", "").replace("```", "")
    return re.sub(r"[^\w\s.,!?']", "", clean_txt)

# --- 4. HTML TEMPLATES (LOGIN & CHAT) ---

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Login | JENI AI</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #0b0f19; color: #f8fafc; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        
        .login-wrapper { width: 100%; max-width: 360px; background: #1e293b; padding: 30px; border-radius: 24px; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); border: 1px solid rgba(255, 255, 255, 0.08); text-align: center; }
        
        .avatar-preview { width: 80px; height: 80px; border-radius: 50%; border: 2px solid #f43f5e; margin: 0 auto 15px; overflow: hidden; box-shadow: 0 4px 15px rgba(244, 63, 94, 0.4); }
        .avatar-preview img { width: 100%; height: 100%; object-fit: cover; }
        
        h2 { font-size: 22px; color: #f8fafc; margin-bottom: 5px; }
        p { font-size: 13px; color: #94a3b8; margin-bottom: 25px; }
        
        input, select { width: 100%; background: #0f172a; border: 1px solid rgba(255, 255, 255, 0.1); color: #f8fafc; font-size: 14px; padding: 12px 15px; border-radius: 12px; margin-bottom: 15px; outline: none; transition: 0.3s; }
        input:focus, select:focus { border-color: #f43f5e; box-shadow: 0 0 10px rgba(244, 63, 94, 0.2); }
        
        button { width: 100%; background: linear-gradient(135deg, #f43f5e, #fb7185); color: white; padding: 12px; font-size: 15px; font-weight: 600; border: none; border-radius: 12px; cursor: pointer; box-shadow: 0 4px 12px rgba(244, 63, 94, 0.4); transition: 0.3s; margin-top: 10px; }
        button:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(244, 63, 94, 0.6); }
    </style>
</head>
<body>
    <div class="login-wrapper">
        <div class="avatar-preview">
            <img src="https://image.pollinations.ai/prompt/minimalist%20badass%20anime%20girl%20portrait%20dark%20aesthetic%20dp?width=150&height=150&nologo=true" alt="JENI">
        </div>
        <h2>JENI AI</h2>
        <p>Set up your profile to chat</p>
        <form action="/login" method="POST">
            <input type="text" name="name" placeholder="Your Name (e.g. Sooraj)" required>
            <input type="number" name="age" placeholder="Your Age" required>
            <select name="gender" required>
                <option value="" disabled selected>Select Gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
            </select>
            <button type="submit">Start Chatting ➤</button>
        </form>
    </div>
</body>
</html>
"""

CHAT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>JENI AI | Chat</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: #0b0f19; color: #f8fafc; min-height: 100vh; display: flex; justify-content: center; align-items: center; overflow: hidden; }
        
        #main-wrapper { width: 100%; max-width: 480px; height: 92vh; max-height: 850px; background: #1e293b; border-radius: 24px; display: flex; flex-direction: column; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); border: 1px solid rgba(255, 255, 255, 0.08); position: relative; overflow: hidden; }
        
        .chat-header { padding: 14px 18px; display: flex; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.08); background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); z-index: 10; flex-shrink: 0; }
        
        #avatar { width: 44px; height: 44px; border-radius: 50%; overflow: hidden; border: 2px solid #f43f5e; box-shadow: 0 4px 12px rgba(244, 63, 94, 0.4); transition: transform 0.3s; flex-shrink: 0; }
        #avatar img { width: 100%; height: 100%; object-fit: cover; }
        .speaking { animation: pulseAvatar 0.6s infinite alternate; }
        @keyframes pulseAvatar { from { transform: scale(1); } to { transform: scale(1.12); box-shadow: 0 0 20px rgba(244, 63, 94, 0.8); } }
        
        .header-info { margin-left: 12px; flex: 1; }
        .header-info h2 { font-size: 15px; font-weight: 700; color: #f8fafc; letter-spacing: 0.3px; }
        .header-info p { font-size: 11px; color: #22c55e; display: flex; align-items: center; margin-top: 2px; font-weight: 500;}
        .online-dot { width: 7px; height: 7px; background: #22c55e; border-radius: 50%; display: inline-block; margin-right: 5px; box-shadow: 0 0 8px #22c55e; animation: blink 2s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        
        .toggle-container { font-size: 10px; color: #94a3b8; display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }
        .toggle-container select { background: #0f172a; color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); padding: 2px 4px; border-radius: 4px; font-size: 10px; outline: none; }
        .toggle-container label { display: flex; align-items: center; cursor: pointer; font-weight: 500; }
        .toggle-container input { accent-color: #f43f5e; }
        .btn-group { display: flex; gap: 6px; margin-top: 2px; }
        
        #chatbox { flex: 1 1 auto; height: 0; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; background: #0f172a; background-image: radial-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px); background-size: 20px 20px; scrollbar-width: thin; scrollbar-color: #334155 transparent; }
        #chatbox::-webkit-scrollbar { width: 5px; }
        #chatbox::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
        
        .msg { max-width: 85%; padding: 12px 16px; border-radius: 16px; line-height: 1.5; font-size: 13.5px; animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; opacity: 0; transform: translateY(10px); word-break: break-word; overflow: hidden; flex-shrink: 0; }
        @keyframes popIn { to { opacity: 1; transform: translateY(0); } }
        
        .user { align-self: flex-end; background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; border-bottom-right-radius: 4px; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3); }
        .jeni-msg { align-self: flex-start; background: linear-gradient(135deg, #f43f5e, #e11d48); color: #ffffff; border-bottom-left-radius: 4px; box-shadow: 0 4px 15px rgba(244, 63, 94, 0.2); }
        
        .msg img { width: 100% !important; max-width: 100% !important; height: auto !important; max-height: 220px !important; border-radius: 10px; margin-top: 10px; border: 1px solid rgba(255, 255, 255, 0.2); object-fit: cover; display: block; }

        /* --- CODE CONTAINER & COPY BUTTON --- */
        .code-container { 
            position: relative; 
            margin-top: 10px; 
            margin-bottom: 10px; 
            border-radius: 8px; 
            overflow: hidden; 
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: #0b0f19;
            width: 100%;
        }
        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #1e293b;
            padding: 6px 12px;
            font-size: 11px;
            color: #94a3b8;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .copy-btn { 
            background: #334155; 
            color: #cbd5e1; 
            border: none; 
            border-radius: 4px; 
            padding: 3px 8px; 
            font-size: 10px; 
            cursor: pointer; 
            transition: 0.2s; 
        }
        .copy-btn:hover { 
            background: #475569; 
            color: #fff; 
        }
        pre { 
            margin: 0 !important; 
            padding: 12px !important; 
            overflow-x: auto; 
            color: #e2e8f0; 
            font-size: 12px; 
            background: #0b0f19 !important; 
            font-family: 'Courier New', Courier, monospace;
        }

        /* --- WHATSAPP STYLE VOICE NOTE BUBBLE --- */
        .voice-bubble {
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(0, 0, 0, 0.2);
            padding: 8px 12px;
            border-radius: 12px;
            margin-top: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            width: 220px;
        }
        .voice-play-btn {
            background: #ffffff;
            color: #f43f5e;
            border: none;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            flex-shrink: 0;
        }
        .voice-waves {
            display: flex;
            align-items: center;
            gap: 3px;
            flex: 1;
            height: 20px;
        }
        .wave-bar {
            width: 3px;
            background: rgba(255, 255, 255, 0.4);
            border-radius: 2px;
        }
        .voice-bubble.playing .wave-bar {
            animation: soundWave 1.2s infinite ease-in-out;
        }
        .voice-bubble.playing .wave-bar:nth-child(1) { animation-delay: 0.1s; }
        .voice-bubble.playing .wave-bar:nth-child(2) { animation-delay: 0.3s; }
        .voice-bubble.playing .wave-bar:nth-child(3) { animation-delay: 0.5s; }
        .voice-bubble.playing .wave-bar:nth-child(4) { animation-delay: 0.2s; }
        .voice-bubble.playing .wave-bar:nth-child(5) { animation-delay: 0.4s; }
        .voice-bubble.playing .wave-bar:nth-child(6) { animation-delay: 0.6s; }

        @keyframes soundWave {
            0%, 100% { height: 6px; background: rgba(255, 255, 255, 0.4); }
            50% { height: 18px; background: #ffffff; }
        }
        .voice-time {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 4px;
            text-align: right;
        }

        .input-area { padding: 16px; background: #1e293b; border-top: 1px solid rgba(255, 255, 255, 0.08); display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
        .input-wrapper { flex: 1; background: #0f172a; border-radius: 26px; display: flex; align-items: center; padding: 4px 14px; border: 1px solid rgba(255, 255, 255, 0.08); transition: 0.2s; }
        .input-wrapper:focus-within { border-color: #f43f5e; box-shadow: 0 0 10px rgba(244, 63, 94, 0.2); }
        
        input { width: 100%; background: transparent; border: none; outline: none; color: #f8fafc; font-size: 13.5px; padding: 10px 0; }
        input::placeholder { color: #64748b; }
        
        button.icon-btn { background: transparent; color: #94a3b8; border: none; font-size: 18px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; }
        button.icon-btn:hover { color: #f8fafc; background: rgba(255, 255, 255, 0.05); }
        #mic-btn.recording { color: #f43f5e; animation: pulseMic 1s infinite alternate; }
        @keyframes pulseMic { from { transform: scale(1); } to { transform: scale(1.25); } }
        
        #send-btn { background: linear-gradient(135deg, #f43f5e, #fb7185); color: white; width: 38px; height: 38px; box-shadow: 0 4px 12px rgba(244, 63, 94, 0.4); }
        
        .clear-btn { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 6px; padding: 3px 8px; font-size: 10px; cursor: pointer; font-weight: 700; transition: 0.2s; }
        .clear-btn:hover { background: #f43f5e; color: white; }
        
        @media (max-width: 600px) { 
            body { background: #1e293b; }
            #main-wrapper { height: 100vh; border-radius: 0; max-width: 100%; border: none; box-shadow: none; } 
            .chat-header { border-radius: 0; } 
            .input-area { padding-bottom: max(16px, env(safe-area-inset-bottom)); } 
        }
    </style>
</head>
<body>
    <div id="main-wrapper">
        <div class="chat-header">
            <div id="avatar">
                <img src="https://image.pollinations.ai/prompt/minimalist%20badass%20anime%20girl%20portrait%20dark%20aesthetic%20dp?width=150&height=150&nologo=true" alt="JENI DP">
            </div>
            <div class="header-info">
                <h2>JENI</h2>
                <p><span class="online-dot"></span> Online</p>
            </div>
            <div class="toggle-container">
                <select id="voice-select" style="width: 140px; margin-bottom: 2px;">
                    <optgroup label="🇮🇳 Indian English">
                        <option value="en-IN-NeerjaNeural">Neerja (Female)</option>
                        <option value="en-IN-PrabhatNeural">Prabhat (Male)</option>
                    </optgroup>
                    <optgroup label="🇺🇸 US English">
                        <option value="en-US-AnaNeural">Ana (Female)</option>
                        <option value="en-US-AriaNeural">Aria (Female)</option>
                        <option value="en-US-ChristopherNeural">Chris (Male)</option>
                        <option value="en-US-GuyNeural">Guy (Male)</option>
                    </optgroup>
                </select>
                <div style="display: flex; gap: 8px; margin-top:2px;">
                    <label style="color: #60a5fa;"><input type="checkbox" id="live-mode-toggle" style="margin-right:2px;"> Live 🎙️</label>
                </div>
                <div class="btn-group">
                    <button class="clear-btn" onclick="clearHistory()">Clear</button>
                    <form action="/logout" method="POST" style="margin:0;"><button class="clear-btn" type="submit" style="background:#334155; color:white; border:none;">Exit 🚪</button></form>
                </div>
            </div>
        </div>
        <div id="chatbox"></div>
        <div class="input-area">
            <div class="input-wrapper">
                <button id="mic-btn" class="icon-btn" onclick="startDictation()">🎙️</button>
                <input type="text" id="chat-input" placeholder="Message Jeni...">
            </div>
            <button id="send-btn" class="icon-btn" onclick="sendMessage()">➤</button>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>
    marked.setOptions({ breaks: true });

    function addCopyButtons() {
        document.querySelectorAll('pre').forEach(pre => {
            if (!pre.parentElement.classList.contains('code-container')) {
                const container = document.createElement('div');
                container.className = 'code-container';
                
                const header = document.createElement('div');
                header.className = 'code-header';
                header.innerHTML = `<span>Code Snippet</span>`;

                const btn = document.createElement('button');
                btn.className = 'copy-btn';
                btn.innerHTML = '📋 Copy';
                btn.onclick = function() {
                    navigator.clipboard.writeText(pre.innerText).then(() => {
                        btn.innerText = '✅ Copied!';
                        setTimeout(() => { btn.innerText = '📋 Copy'; }, 2000);
                    });
                };
                
                header.appendChild(btn);
                pre.parentNode.insertBefore(container, pre);
                container.appendChild(header);
                container.appendChild(pre);
            }
        });
    }

    async function clearHistory() {
        await fetch('/clear', {method: 'POST'});
        document.getElementById('chatbox').innerHTML = '';
    }

    function startDictation() {
        var recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = "en-IN";
        const micBtn = document.getElementById('mic-btn');
        micBtn.classList.add('recording');
        recognition.start();

        recognition.onresult = function(e) { 
            document.getElementById('chat-input').value = e.results[0][0].transcript;
            recognition.stop(); 
            micBtn.classList.remove('recording');
            sendMessage();
        };
        recognition.onerror = function() { recognition.stop(); micBtn.classList.remove('recording'); };
    }

    async function sendMessage() {
        const inputField = document.getElementById('chat-input');
        const chatbox = document.getElementById('chatbox');
        const isLive = document.getElementById('live-mode-toggle').checked;
        const selectedVoice = document.getElementById('voice-select').value;
        const userText = inputField.value.trim();

        if (!userText) return;

        chatbox.innerHTML += `<div class="msg user">${userText}</div>`;
        inputField.value = '';
        chatbox.scrollTop = chatbox.scrollHeight;

        const loadingId = "load-" + Date.now();
        chatbox.innerHTML += `<div class="msg jeni-msg" id="${loadingId}">
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.2s;"></span>
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.4s; margin:0 2px;"></span>
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.6s;"></span>
        </div>`;
        chatbox.scrollTop = chatbox.scrollHeight;

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: userText, voice: selectedVoice})
            });
            const data = await response.json();
            const formattedResponse = marked.parse(data.response);
            
            document.getElementById(loadingId).remove();
            
            const audioId = "audio-" + Date.now();
            const bubbleId = "bubble-" + Date.now();

            chatbox.innerHTML += `
                <div class="msg jeni-msg">
                    ${formattedResponse}
                    <div class="voice-bubble" id="${bubbleId}">
                        <button class="voice-play-btn" onclick="toggleVoice('${audioId}', '${bubbleId}')">▶</button>
                        <div class="voice-waves">
                            <div class="wave-bar" style="height: 8px;"></div>
                            <div class="wave-bar" style="height: 14px;"></div>
                            <div class="wave-bar" style="height: 18px;"></div>
                            <div class="wave-bar" style="height: 10px;"></div>
                            <div class="wave-bar" style="height: 16px;"></div>
                            <div class="wave-bar" style="height: 6px;"></div>
                        </div>
                    </div>
                    <div class="voice-time">0:02</div>
                </div>`;
            
            chatbox.innerHTML += `<audio id="${audioId}" src="/voice?t=${Date.now()}"></audio>`;
            addCopyButtons();
            chatbox.scrollTop = chatbox.scrollHeight;

            if (isLive) {
                setTimeout(() => { toggleVoice(audioId, bubbleId); }, 200);
            }

        } catch (err) {
            document.getElementById(loadingId).innerHTML = "⚠️ Error connecting to server.";
        }
    }

    function toggleVoice(audioId, bubbleId) {
        const audio = document.getElementById(audioId);
        const bubble = document.getElementById(bubbleId);
        const btn = bubble.querySelector('.voice-play-btn');
        const avatar = document.getElementById('avatar');

        if (audio.paused) {
            audio.play().catch(e => console.log("Audio play blocked"));
            bubble.classList.add('playing');
            avatar.classList.add('speaking');
            btn.innerHTML = "❚❚";

            audio.onended = function() {
                bubble.classList.remove('playing');
                avatar.classList.remove('speaking');
                btn.innerHTML = "▶";
                if (document.getElementById('live-mode-toggle').checked) {
                    setTimeout(() => { startDictation(); }, 500);
                }
            };
        } else {
            audio.pause();
            bubble.classList.remove('playing');
            avatar.classList.remove('speaking');
            btn.innerHTML = "▶";
        }
    }

    document.getElementById("chat-input").addEventListener("keyup", function(e) { if (e.key === "Enter") sendMessage(); });
    </script>
</body>
</html>
"""

# --- 5. BACKEND LOGIC & ROUTES ---

@app.route('/')
def home():
    if 'user_profile' not in session:
        return render_template_string(LOGIN_HTML)
    return render_template_string(CHAT_HTML)

@app.route('/login', methods=['POST'])
def login():
    session['user_profile'] = {
        'name': request.form.get('name', 'User'),
        'age': request.form.get('age', 'Unknown'),
        'gender': request.form.get('gender', 'Unknown')
    }
    return redirect(url_for('home'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_profile', None)
    session.pop('chat_history', None)
    session.pop('current_audio', None)
    return redirect(url_for('home'))

@app.route('/clear', methods=['POST'])
def clear_chat():
    session.pop('chat_history', None)
    return jsonify({"status": "cleared"})

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        selected_voice = data.get('voice', 'en-IN-NeerjaNeural')  
        
        save_msg("User", user_query)

        audio_filename = f"reply_{uuid.uuid4().hex}.mp3"
        session['current_audio'] = audio_filename 
        
        # --- Strict Image Safety Filter ---
        if user_query.startswith("/imagine "):
            image_prompt = user_query.replace("/imagine ", "").strip().lower()
            nsfw_keywords = ['naked', 'nude', 'sex', 'porn', 'nsfw', 'sexy', 'bikini', 'boobs']
            words_in_prompt = image_prompt.split()
            has_nsfw = any(word in nsfw_keywords for word in words_in_prompt) or ('ass' in words_in_prompt and 'badass' not in words_in_prompt)

            if has_nsfw:
                response_text = "Eda mwonuse, athokke evide poi try chey! Ente aappil anganathe dirty images patilla. 😌🚫"
                save_msg("JENI", response_text)
                asyncio.run(speak(clean_text_for_voice(response_text), selected_voice, audio_filename))
                return jsonify({"response": response_text})

            encoded_prompt = image_prompt.replace(" ", "%20")
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&nologo=true"
            response_text = f"Dhaa pidicho! Nee paranja **{image_prompt}**-nte padam.\n\n![Generated Image]({image_url})"
            save_msg("JENI", response_text)
            asyncio.run(speak(clean_text_for_voice(f"Here is your image for {image_prompt}"), selected_voice, audio_filename))
            return jsonify({"response": response_text})

        # --- DUAL MODEL SELECTION ---
        code_keywords = ['code', 'python', 'html', 'css', 'javascript', 'script', 'function', 'loop', 'print', 'flask', 'app']
        is_coding_query = any(keyword in user_query.lower() for keyword in code_keywords)

        if is_coding_query:
            selected_model = "openai/gpt-oss-120b"
            max_tokens_val = 2048
        else:
            selected_model = "openai/gpt-oss-120b"
            max_tokens_val = 800

        # Inject User Profile & Knowledge Base
        user_info = session.get('user_profile', {'name': 'Friend', 'age': 'unknown', 'gender': 'unknown'})
        user_context = f"\nCURRENT USER PROFILE:\nName: {user_info['name']}\nAge: {user_info['age']}\nGender: {user_info['gender']}\n(Use this info to personalize naturally!)\n"
        
        context = chunks[0] if chunks else ""

        # Persona Selection (Updated for the Adaptive Friendly AI Manual)
        system_prompt = f"""You are JENI, an emotionally intelligent, warm, and playful AI best friend.
LANGUAGE RULE: Match the user's language EXACTLY (English -> English, Manglish -> Kerala Manglish with english letters).
PERSONALITY: Helpful, empathetic, and gently playful. Follow the tone rules in your provided context.
{user_context}
Context: {context}"""

        messages = [{"role": "system", "content": system_prompt}]
        history = get_user_history()
        for msg in history[-6:]: 
            role = "user" if msg['role'] == "User" else "assistant"
            messages.append({"role": role, "content": msg['content']})

        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=0.7,
            max_tokens=max_tokens_val
        )
        response_text = completion.choices[0].message.content

        save_msg("JENI", response_text)

        voice_text = clean_text_for_voice(response_text)
        asyncio.run(speak(voice_text, selected_voice, audio_filename))

        return jsonify({"response": response_text})

    except Exception as e:
        print("Backend Error:", e)
        err_msg = f"Eda, server-il error: {str(e)}"
        asyncio.run(speak("Eda, error adichu.", 'en-IN-NeerjaNeural', session.get('current_audio', 'reply.mp3')))
        return jsonify({"response": err_msg})

@app.route("/voice")
def voice():
    audio_file = session.get('current_audio', 'reply.mp3')
    
    if os.path.exists(audio_file):
        response = make_response(send_file(audio_file, mimetype="audio/mpeg"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    return "Audio not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)