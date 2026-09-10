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
app.secret_key = "sooraj_etherea_veil_secret_key_999"  # Needed for isolated user sessions

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

# --- 2. KNOWLEDGE BASE (SAFE LOAD) ---
chunks = []
try:
    reader = PdfReader("chatbot_v2.pdf")
    pdf_text = "".join([page.extract_text() + "\n" for page in reader.pages if page.extract_text()])
    chunks = [pdf_text[i:i + 1000] for i in range(0, len(pdf_text), 1000)]
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
    return re.sub(r"[^\w\s.,!?']", "", text).replace("```python", "").replace("```", "")

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
        .mickey { align-self: flex-start; background: linear-gradient(135deg, #f43f5e, #e11d48); color: #ffffff; border-bottom-left-radius: 4px; box-shadow: 0 4px 15px rgba(244, 63, 94, 0.2); }
        
        .msg img { width: 100% !important; max-width: 100% !important; height: auto !important; max-height: 220px !important; border-radius: 10px; margin-top: 10px; border: 1px solid rgba(255, 255, 255, 0.2); object-fit: cover; display: block; }

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
        
        .listen-btn { background: transparent; color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.4); border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; margin-top: 8px; display: inline-flex; align-items: center; gap: 4px; transition: 0.2s; }
        
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
                    <label><input type="checkbox" id="etherea-toggle" style="margin-right:2px;"> Etherea 🌴</label>
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
    <script>
    marked.setOptions({ breaks: true });

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
        const isEtherea = document.getElementById('etherea-toggle').checked;
        const isLive = document.getElementById('live-mode-toggle').checked;
        const selectedVoice = document.getElementById('voice-select').value;
        const userText = inputField.value.trim();

        if (!userText) return;

        chatbox.innerHTML += `<div class="msg user">${userText}</div>`;
        inputField.value = '';
        chatbox.scrollTop = chatbox.scrollHeight;

        const loadingId = "load-" + Date.now();
        chatbox.innerHTML += `<div class="msg mickey" id="${loadingId}">
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.2s;"></span>
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.4s; margin:0 2px;"></span>
            <span style="display:inline-block; width:6px; height:6px; background:#fff; border-radius:50%; animation: blink 1.4s infinite 0.6s;"></span>
        </div>`;
        chatbox.scrollTop = chatbox.scrollHeight;

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: userText, etherea_mode: isEtherea, voice: selectedVoice})
            });
            const data = await response.json();
            const formattedResponse = marked.parse(data.response);
            
            document.getElementById(loadingId).remove();
            chatbox.innerHTML += `<div class="msg mickey">${formattedResponse}<div style="margin-top:6px;"><button class="listen-btn" onclick="playVoice(false)">🔊 Listen</button></div></div>`;
            chatbox.scrollTop = chatbox.scrollHeight;

            if (isLive) playVoice(true);

        } catch (err) {
            document.getElementById(loadingId).innerHTML = "⚠️ Error connecting to server.";
        }
    }

    function playVoice(triggerLiveLoop = false){
        const audio = new Audio("/voice?t=" + Date.now());
        const avatar = document.getElementById('avatar');
        audio.play().catch(e => console.log("Audio block"));
        avatar.classList.add('speaking'); 

        audio.onended = function() { 
            avatar.classList.remove('speaking'); 
            if (triggerLiveLoop && document.getElementById('live-mode-toggle').checked) {
                setTimeout(() => { startDictation(); }, 500);
            }
        };
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
        is_etherea = data.get('etherea_mode', False)
        selected_voice = data.get('voice', 'en-IN-NeerjaNeural')  
        
        save_msg("User", user_query)

        # Unique Audio File name for THIS session request
        audio_filename = f"reply_{uuid.uuid4().hex}.mp3"
        session['current_audio'] = audio_filename 
        
        # --- Strict Image Safety Filter ---
        if user_query.startswith("/imagine "):
            image_prompt = user_query.replace("/imagine ", "").strip().lower()
            nsfw_keywords = ['naked', 'nude', 'sex', 'porn', 'nsfw', 'sexy', 'bikini', 'boobs', 'ass']
            if any(word in image_prompt for word in nsfw_keywords):
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

        # Inject User Profile into Prompt for Personalization
        user_info = session.get('user_profile', {'name': 'Friend', 'age': 'unknown', 'gender': 'unknown'})
        user_context = f"\n\nCURRENT USER PROFILE:\nName: {user_info['name']}\nAge: {user_info['age']}\nGender: {user_info['gender']}\n(Use this info to personalize your responses naturally! If male, use terms like 'eda', 'mwonuse'. If female, use 'edi', 'penne' etc.)\n"

        context = chunks[0] if chunks else ""
        selected_model = "qwen/qwen3.8-27b"

        # Persona Selection
        if is_etherea:
            system_prompt = f"You are JENI, luxury AI receptionist for Etherea Veil in Idukki. Speak politely. {user_context}"
        else:
            system_prompt = f"""You are JENI, a sarcastic, witty, playful and savage best friend.
LANGUAGE RULE: Match the user's language EXACTLY (English -> English, Manglish -> Kerala Manglish with english letters).
PERSONALITY: Sarcastic, funny, savage. Keep it 1-3 sentences max.
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
            max_tokens=800
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