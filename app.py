from flask import Flask, request, jsonify, render_template_string, send_file, make_response, session
from groq import Groq
import edge_tts
import asyncio
import re
import os
from pypdf import PdfReader
from dotenv import load_dotenv

# Load API Keys
load_dotenv()

app = Flask(__name__)
app.secret_key = "sooraj_etherea_veil_secret_key_999"  # Needed for isolated user sessions

# Securely load Groq client using Environment Variable
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- 1. SESSION-BASED HISTORY MANAGEMENT ---
def get_user_history():
    if 'chat_history' not in session:
        session['chat_history'] = []
    return session['chat_history']

def save_msg(role, content):
    history = get_user_history()
    history.append({"role": role, "content": content})
    # Keep only the last 6 messages so the cookie never exceeds the 4KB limit!
    session['chat_history'] = history[-6:]
    session.modified = True

# --- 2. KNOWLEDGE BASE (SAFE LOAD) ---
chunks = []
doc_embeddings = None
try:
    reader = PdfReader("chatbot_v2.pdf")
    pdf_text = "".join([page.extract_text() + "\n" for page in reader.pages if page.extract_text()])
    chunks = [pdf_text[i:i + 1000] for i in range(0, len(pdf_text), 1000)]
except Exception as e:
    print("PDF Load Error (Ignoring):", e)

# --- 3. VOICE SETUP ---
async def speak(text):
    try:
        communicate = edge_tts.Communicate(text=text, voice="en-IN-NeerjaNeural")
        await communicate.save("reply.mp3")
    except Exception as e:
        print("VOICE ERROR:", e)

def clean_text_for_voice(text):
    return re.sub(r"[^\w\s.,!?']", "", text).replace("```python", "").replace("```", "")

# --- 4. FRONTEND UI ---
@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>JENI AI | By Sooraj</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
            body { background: #f0f2f5; color: #1c1e21; min-height: 100vh; display: flex; justify-content: center; align-items: center; overflow: hidden; }
            #creator-badge { position: absolute; bottom: 20px; left: 20px; font-size: 12px; color: #8c939d; letter-spacing: 1px; pointer-events: none; text-transform: uppercase; transform: rotate(-90deg); transform-origin: left bottom; font-weight: 500; }
            #main-wrapper { width: 100%; max-width: 500px; height: 90vh; max-height: 800px; background: #ffffff; border-radius: 20px; display: flex; flex-direction: column; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08); position: relative; overflow: hidden; }
            .chat-header { padding: 15px 20px; display: flex; align-items: center; border-bottom: 1px solid #e4e6eb; background: #ffffff; }
            #avatar { width: 45px; height: 45px; border-radius: 50%; background: linear-gradient(135deg, #ff416c, #ff4b2b); color: white; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; box-shadow: 0 4px 10px rgba(255, 65, 108, 0.3); transition: transform 0.3s; }
            .speaking { animation: pulse 0.5s infinite alternate; }
            @keyframes pulse { from { transform: scale(1); } to { transform: scale(1.1); box-shadow: 0 0 15px rgba(255, 65, 108, 0.6); } }
            .header-info { margin-left: 15px; flex: 1; }
            .header-info h2 { font-size: 16px; font-weight: 600; color: #050505; }
            .header-info p { font-size: 12px; color: #31a24c; display: flex; align-items: center; margin-top: 2px;}
            .online-dot { width: 8px; height: 8px; background: #31a24c; border-radius: 50%; display: inline-block; margin-right: 5px; animation: blink 2s infinite; }
            @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
            .toggle-container { font-size: 11px; color: #65676b; display: flex; flex-direction: column; gap: 5px; align-items: flex-end; }
            #chatbox { flex: 1; min-height: 0; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; background: #ffffff; scrollbar-width: thin; scrollbar-color: #ccd0d5 transparent; }
            #chatbox::-webkit-scrollbar { width: 6px; }
            #chatbox::-webkit-scrollbar-thumb { background: #ccd0d5; border-radius: 10px; }
            .msg { max-width: 80%; padding: 10px 14px; border-radius: 18px; line-height: 1.4; font-size: 14px; animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; opacity: 0; transform: translateY(10px); }
            @keyframes popIn { to { opacity: 1; transform: translateY(0); } }
            .user { align-self: flex-end; background: #0084ff; color: white; border-bottom-right-radius: 4px; box-shadow: 0 2px 5px rgba(0, 132, 255, 0.2); }
            .mickey { align-self: flex-start; background: #f0f2f5; color: #050505; border-bottom-left-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
            .input-area { padding: 15px; background: #ffffff; border-top: 1px solid #e4e6eb; display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
            .input-wrapper { flex: 1; background: #f0f2f5; border-radius: 30px; display: flex; align-items: center; padding: 5px 15px; border: 1px solid #e4e6eb; }
            input { width: 100%; background: transparent; border: none; outline: none; color: #050505; font-size: 14px; padding: 10px 0; }
            input::placeholder { color: #8c939d; }
            button.icon-btn { background: transparent; color: #65676b; border: none; font-size: 18px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; }
            button.icon-btn:hover { color: #050505; background: #e4e6eb; }
            #mic-btn.recording { color: #ff416c; animation: pulseMic 1s infinite alternate; }
            @keyframes pulseMic { from { transform: scale(1); } to { transform: scale(1.2); } }
            #send-btn { background: #0084ff; color: white; width: 40px; height: 40px; }
            #send-btn:hover { transform: translateY(-2px); background: #0073e6; box-shadow: 0 4px 10px rgba(0, 132, 255, 0.3); }
            .listen-btn { background: transparent; color: #0084ff; border: 1px solid #0084ff; border-radius: 20px; padding: 4px 10px; font-size: 11px; font-weight: 500; cursor: pointer; margin-top: 8px; display: inline-flex; align-items: center; gap: 4px; transition: 0.2s; }
            .listen-btn:hover { background: #e6f2ff; }
            .clear-btn { background: #ff416c; color: white; border: none; border-radius: 12px; padding: 2px 8px; font-size: 10px; cursor: pointer; font-weight: 600; }
            .clear-btn:hover { background: #e0355b; }
            
            .code-container { position: relative; margin-top: 8px; }
            .copy-btn { position: absolute; top: 8px; right: 8px; background: #2d2d2d; color: #d4d4d4; border: 1px solid #444; border-radius: 4px; padding: 4px 8px; font-size: 11px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; gap: 4px; z-index: 10; }
            .copy-btn:hover { background: #444; color: #fff; }
            pre { background: #1e1e1e !important; padding: 36px 12px 12px 12px !important; border-radius: 8px; overflow-x: auto; border: 1px solid #e4e6eb; color: #d4d4d4; font-size: 12px; }
            
            p { margin-bottom: 5px; }
            .ai-image { max-width: 100%; border-radius: 12px; margin-top: 8px; border: 1px solid #e4e6eb; }
            @media (max-width: 600px) { #main-wrapper { height: 100vh; border-radius: 0; max-width: 100%; border: none; } .chat-header { border-radius: 0; } .input-area { padding-bottom: 20px; } #creator-badge { display: none; } }
        </style>
    </head>
    <body>
        <div id="creator-badge">💻 Created by Sooraj Sreekanth</div>
        <div id="main-wrapper">
            <div class="chat-header">
                <div id="avatar">JENI</div>
                <div class="header-info">
                    <h2>JENI AI</h2>
                    <p><span class="online-dot"></span> Online</p>
                </div>
                <div class="toggle-container">
                    <label style="display:flex; align-items:center; cursor:pointer;">
                        <input type="checkbox" id="etherea-toggle" style="width:auto; margin-right:5px;"> 
                        Etherea Mode 🌴
                    </label>
                    <button class="clear-btn" onclick="clearHistory()">Clear 🗑️</button>
                </div>
            </div>
            <div id="chatbox"></div>
            <div class="input-area">
                <div class="input-wrapper">
                    <button id="mic-btn" class="icon-btn" onclick="startDictation()" title="Click to speak">🎙️</button>
                    <input type="text" id="chat-input" placeholder="Message Jeni...">
                </div>
                <button id="send-btn" class="icon-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
        
        <script>
        marked.setOptions({ breaks: true, highlight: function(code, lang) { const language = hljs.getLanguage(lang) ? lang : 'plaintext'; return hljs.highlight(code, { language }).value; } });

        function addCopyButtons() {
            document.querySelectorAll('pre').forEach(pre => {
                if (!pre.parentElement.classList.contains('code-container')) {
                    const container = document.createElement('div');
                    container.className = 'code-container';
                    pre.parentNode.insertBefore(container, pre);
                    container.appendChild(pre);

                    const btn = document.createElement('button');
                    btn.className = 'copy-btn';
                    btn.innerHTML = '📑 Copy';
                    btn.onclick = function() {
                        navigator.clipboard.writeText(pre.innerText).then(() => {
                            btn.innerText = 'Copied! ✅';
                            setTimeout(() => { btn.innerText = '📑 Copy'; }, 2000);
                        });
                    };
                    container.appendChild(btn);
                }
            });
        }

        async function clearHistory() {
            await fetch('/clear', {method: 'POST'});
            document.getElementById('chatbox').innerHTML = '';
        }

        function startDictation() {
            if (window.hasOwnProperty('webkitSpeechRecognition')) {
                var recognition = new webkitSpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = "en-IN";
                const micBtn = document.getElementById('mic-btn');
                micBtn.classList.add('recording');
                recognition.start();
                recognition.onresult = function(e) { document.getElementById('chat-input').value = e.results[0][0].transcript; recognition.stop(); micBtn.classList.remove('recording'); };
                recognition.onerror = function(e) { recognition.stop(); micBtn.classList.remove('recording'); };
            } else { alert("Browser mic not supported! Use Chrome."); }
        }

        async function sendMessage() {
            const inputField = document.getElementById('chat-input');
            const chatbox = document.getElementById('chatbox');
            const isEtherea = document.getElementById('etherea-toggle').checked;
            const userText = inputField.value.trim();

            if (!userText) return;

            chatbox.innerHTML += `<div class="msg user">${userText}</div>`;
            inputField.value = '';
            chatbox.scrollTop = chatbox.scrollHeight;

            const loadingId = "load-" + Date.now();
            chatbox.innerHTML += `<div class="msg mickey" id="${loadingId}">
                <div style="display:flex; align-items:center; gap:4px;">
                    <span style="display:inline-block; width:6px; height:6px; background:#8c939d; border-radius:50%; animation: blink 1.4s infinite 0.2s;"></span>
                    <span style="display:inline-block; width:6px; height:6px; background:#8c939d; border-radius:50%; animation: blink 1.4s infinite 0.4s;"></span>
                    <span style="display:inline-block; width:6px; height:6px; background:#8c939d; border-radius:50%; animation: blink 1.4s infinite 0.6s;"></span>
                </div>
            </div>`;
            chatbox.scrollTop = chatbox.scrollHeight;

            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: userText, etherea_mode: isEtherea})
                });
                const data = await response.json();
                const formattedResponse = marked.parse(data.response);
                
                document.getElementById(loadingId).remove();
                chatbox.innerHTML += `<div class="msg mickey">${formattedResponse}<div style="margin-top:5px;"><button class="listen-btn" onclick="playVoice()">🔊 Listen</button></div></div>`;
                
                addCopyButtons();
                chatbox.scrollTop = chatbox.scrollHeight;
            } catch (err) {
                document.getElementById(loadingId).innerHTML = "⚠️ Error connecting to server.";
            }
        }

        function playVoice(){
            const audio = new Audio("/voice?t=" + Date.now());
            const avatar = document.getElementById('avatar');
            audio.play();
            avatar.classList.add('speaking'); 
            audio.onended = function() { avatar.classList.remove('speaking'); };
        }

        document.getElementById("chat-input").addEventListener("keyup", function(e) { if (e.key === "Enter") sendMessage(); });
        </script>
    </body>
    </html>
    """)

# --- 5. BACKEND LOGIC ---
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
        
        save_msg("User", user_query)
        
        # Image Generation
        if user_query.startswith("/imagine "):
            image_prompt = user_query.replace("/imagine ", "").strip()
            encoded_prompt = image_prompt.replace(" ", "%20")
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            response_text = f"Dhaa pidicho! Nee paranja **{image_prompt}**-nte padam.\n\n![Generated Image]({image_url})"
            save_msg("JENI", response_text)
            return jsonify({"response": response_text})

        # Knowledge Base Search
        context = ""
        if doc_embeddings is not None and len(chunks) > 0:
            global model
            query_embedding = model.encode(user_query)
            hits = util.semantic_search(query_embedding, doc_embeddings, top_k=1)
            if hits:
                context = chunks[hits[0][0]["corpus_id"]]

        # Smart Routing for Code
        code_keywords = ['code', 'python', 'html', 'css', 'javascript', 'script', 'function', 'factorial', 'loop', 'print']
        is_coding_query = any(keyword in user_query.lower() for keyword in code_keywords)

        if is_coding_query:
            selected_model = "openai/gpt-oss-120b"
            max_tokens_val = 2048
        else:
            selected_model = "qwen/qwen3.8-27b"
            max_tokens_val = 1000

        # Persona Selection
        if is_etherea:
            system_prompt = f"""You are JENI, the exclusive luxury AI receptionist for Etherea Veil, a premium resort in Idukki, Kerala founded by Sooraj. 
            Speak politely, warmly, and professionally. Match the user's language style (if they speak Manglish, reply in Manglish). Keep responses concise (2-3 sentences max). 
            Context: {context}"""
        else:
            system_prompt = f"""You are JENI, a sarcastic, witty, and savage best friend who lives in the user's phone. 
            CRITICAL LANGUAGE RULE: Default to normal English for standard greetings like "Hey" or general English questions. ONLY switch to natural Kerala Manglish (casual Malayalam slang mixed with English, like "Njaan Jeni aanu, ninte phone-il ulla best friend!", "Poda", "Set aanu") if the user explicitly speaks to you in Manglish or asks in Malayalam slang. 
            Never use hashtags. Never talk about being a boring AI. Keep it punchy and fun (1-3 sentences max unless writing requested code).
            Context: {context}"""

        # Build Message History
        messages = [{"role": "system", "content": system_prompt}]
        history = get_user_history()
        for msg in history[-6:]: 
            role = "user" if msg['role'] == "User" else "assistant"
            messages.append({"role": role, "content": msg['content']})

        # Groq API Call
        completion = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=0.7,
            max_tokens=max_tokens_val
        )
        response_text = completion.choices[0].message.content

        save_msg("JENI", response_text)

        # Generate Audio
        voice_text = clean_text_for_voice(response_text)
        asyncio.run(speak(voice_text))

        return jsonify({"response": response_text})

    except Exception as e:
        print("Backend Error:", e)
        return jsonify({"response": "Eda, server-il oru cheriya technical glitch! Oru vattam koode try cheythu nokkikoo. 🥲"})

@app.route("/voice")
def voice():
    response = make_response(send_file("reply.mp3", mimetype="audio/mpeg"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)