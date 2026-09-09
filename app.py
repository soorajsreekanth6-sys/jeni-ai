from flask import Flask, request, jsonify, render_template_string, send_file, make_response, session
from groq import Groq
import edge_tts
import asyncio
import re
import os
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

# --- 3. VOICE SETUP ---
async def speak(text):
    try:
        communicate = edge_tts.Communicate(text=text, voice="en-IN-NeerjaNeural")
        await communicate.save("reply.mp3")
    except Exception as e:
        print("VOICE ERROR:", e)

def clean_text_for_voice(text):
    return re.sub(r"[^\w\s.,!?']", "", text).replace("```python", "").replace("```", "")

# --- 4. FRONTEND UI (REAL PERSON DP, RED BUBBLE & CLEAN CSS) ---
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
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
            
            * { 
                box-sizing: border-box; 
                margin: 0; 
                padding: 0; 
                font-family: 'Plus Jakarta Sans', sans-serif; 
            }
            
            body { 
                background: #0b0f19; 
                color: #f8fafc; 
                min-height: 100vh; 
                display: flex; 
                justify-content: center; 
                align-items: center; 
                overflow: hidden; 
            }
            
            #creator-badge { 
                position: absolute; 
                bottom: 20px; 
                left: 20px; 
                font-size: 11px; 
                color: #64748b; 
                letter-spacing: 1.5px; 
                pointer-events: none; 
                text-transform: uppercase; 
                transform: rotate(-90deg); 
                transform-origin: left bottom; 
                font-weight: 600; 
            }
            
            #main-wrapper { 
                width: 100%; 
                max-width: 480px; 
                height: 92vh; 
                max-height: 850px; 
                background: #1e293b; 
                border-radius: 24px; 
                display: flex; 
                flex-direction: column; 
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5); 
                border: 1px solid rgba(255, 255, 255, 0.08); 
                position: relative; 
                overflow: hidden; 
            }
            
            .chat-header { 
                padding: 14px 18px; 
                display: flex; 
                align-items: center; 
                border-bottom: 1px solid rgba(255, 255, 255, 0.08); 
                background: rgba(15, 23, 42, 0.95); 
                backdrop-filter: blur(10px); 
                z-index: 10; 
                flex-shrink: 0; 
            }
            
            /* --- REAL PERSON DP AVATAR --- */
            #avatar { 
                width: 44px; 
                height: 44px; 
                border-radius: 50%; 
                overflow: hidden; 
                border: 2px solid #f43f5e; 
                box-shadow: 0 4px 12px rgba(244, 63, 94, 0.4); 
                transition: transform 0.3s; 
                flex-shrink: 0; 
            }
            
            #avatar img { 
                width: 100%; 
                height: 100%; 
                object-fit: cover; 
            }
            
            .speaking { 
                animation: pulseAvatar 0.6s infinite alternate; 
            }
            
            @keyframes pulseAvatar { 
                from { transform: scale(1); } 
                to { transform: scale(1.12); box-shadow: 0 0 20px rgba(244, 63, 94, 0.8); } 
            }
            
            .header-info { 
                margin-left: 12px; 
                flex: 1; 
            }
            
            .header-info h2 { 
                font-size: 15px; 
                font-weight: 700; 
                color: #f8fafc; 
                letter-spacing: 0.3px; 
            }
            
            .header-info p { 
                font-size: 11px; 
                color: #22c55e; 
                display: flex; 
                align-items: center; 
                margin-top: 2px; 
                font-weight: 500;
            }
            
            .online-dot { 
                width: 7px; 
                height: 7px; 
                background: #22c55e; 
                border-radius: 50%; 
                display: inline-block; 
                margin-right: 5px; 
                box-shadow: 0 0 8px #22c55e; 
                animation: blink 2s infinite; 
            }
            
            @keyframes blink { 
                0% { opacity: 1; } 
                50% { opacity: 0.4; } 
                100% { opacity: 1; } 
            }
            
            .toggle-container { 
                font-size: 11px; 
                color: #94a3b8; 
                display: flex; 
                flex-direction: column; 
                gap: 6px; 
                align-items: flex-end; 
            }
            
            .toggle-container label { 
                display: flex; 
                align-items: center; 
                cursor: pointer; 
                font-weight: 500; 
            }
            
            .toggle-container input { 
                accent-color: #f43f5e; 
            }

            /* --- SUBTLE CHAT WALLPAPER BACKGROUND --- */
            #chatbox { 
                flex: 1 1 auto; 
                height: 0; 
                overflow-y: auto; 
                padding: 20px; 
                display: flex; 
                flex-direction: column; 
                gap: 14px; 
                background: #0f172a; 
                background-image: radial-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px); 
                background-size: 20px 20px; 
                scrollbar-width: thin; 
                scrollbar-color: #334155 transparent; 
            }
            
            #chatbox::-webkit-scrollbar { 
                width: 5px; 
            }
            
            #chatbox::-webkit-scrollbar-thumb { 
                background: #334155; 
                border-radius: 10px; 
            }
            
            .msg { 
                max-width: 85%; 
                padding: 12px 16px; 
                border-radius: 16px; 
                line-height: 1.5; 
                font-size: 13.5px; 
                animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; 
                opacity: 0; 
                transform: translateY(10px); 
                word-break: break-word; 
                overflow: hidden; 
                flex-shrink: 0; 
            }
            
            @keyframes popIn { 
                to { opacity: 1; transform: translateY(0); } 
            }
            
            .user { 
                align-self: flex-end; 
                background: linear-gradient(135deg, #3b82f6, #2563eb); 
                color: white; 
                border-bottom-right-radius: 4px; 
                box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3); 
            }
            
            /* --- JENI RED BUBBLE --- */
            .mickey { 
                align-self: flex-start; 
                background: linear-gradient(135deg, #f43f5e, #e11d48); 
                color: #ffffff; 
                border-bottom-left-radius: 4px; 
                box-shadow: 0 4px 15px rgba(244, 63, 94, 0.2); 
            }
            
            /* --- BULLETPROOF MOBILE IMAGE FIX --- */
            .msg img, .ai-image { 
                width: 100% !important; 
                max-width: 100% !important; 
                height: auto !important; 
                max-height: 220px !important; 
                border-radius: 10px; 
                margin-top: 10px; 
                border: 1px solid rgba(255, 255, 255, 0.2); 
                object-fit: cover; 
                display: block; 
            }

            .input-area { 
                padding: 16px; 
                background: #1e293b; 
                border-top: 1px solid rgba(255, 255, 255, 0.08); 
                display: flex; 
                gap: 10px; 
                align-items: center; 
                flex-shrink: 0; 
            }
            
            .input-wrapper { 
                flex: 1; 
                background: #0f172a; 
                border-radius: 26px; 
                display: flex; 
                align-items: center; 
                padding: 4px 14px; 
                border: 1px solid rgba(255, 255, 255, 0.08); 
                transition: 0.2s; 
            }
            
            .input-wrapper:focus-within { 
                border-color: #f43f5e; 
                box-shadow: 0 0 10px rgba(244, 63, 94, 0.2); 
            }
            
            input { 
                width: 100%; 
                background: transparent; 
                border: none; 
                outline: none; 
                color: #f8fafc; 
                font-size: 13.5px; 
                padding: 10px 0; 
            }
            
            input::placeholder { 
                color: #64748b; 
            }
            
            button.icon-btn { 
                background: transparent; 
                color: #94a3b8; 
                border: none; 
                font-size: 18px; 
                cursor: pointer; 
                transition: 0.2s; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                width: 36px; 
                height: 36px; 
                border-radius: 50%; 
            }
            
            button.icon-btn:hover { 
                color: #f8fafc; 
                background: rgba(255, 255, 255, 0.05); 
            }
            
            #mic-btn.recording { 
                color: #f43f5e; 
                animation: pulseMic 1s infinite alternate; 
            }
            
            @keyframes pulseMic { 
                from { transform: scale(1); } 
                to { transform: scale(1.25); } 
            }
            
            #send-btn { 
                background: linear-gradient(135deg, #f43f5e, #fb7185); 
                color: white; 
                width: 38px; 
                height: 38px; 
                box-shadow: 0 4px 12px rgba(244, 63, 94, 0.4); 
            }
            
            #send-btn:hover { 
                transform: translateY(-2px); 
                box-shadow: 0 6px 16px rgba(244, 63, 94, 0.6); 
            }
            
            .listen-btn { 
                background: transparent; 
                color: #ffffff; 
                border: 1px solid rgba(255, 255, 255, 0.4); 
                border-radius: 16px; 
                padding: 4px 10px; 
                font-size: 11px; 
                font-weight: 600; 
                cursor: pointer; 
                margin-top: 8px; 
                display: inline-flex; 
                align-items: center; 
                gap: 4px; 
                transition: 0.2s; 
            }
            
            .listen-btn:hover { 
                background: rgba(255, 255, 255, 0.15); 
            }
            
            .clear-btn { 
                background: rgba(244, 63, 94, 0.15); 
                color: #f43f5e; 
                border: 1px solid rgba(244, 63, 94, 0.3); 
                border-radius: 10px; 
                padding: 3px 8px; 
                font-size: 10px; 
                cursor: pointer; 
                font-weight: 700; 
                transition: 0.2s; 
            }
            
            .clear-btn:hover { 
                background: #f43f5e; 
                color: white; 
            }
            
            .code-container { 
                position: relative; 
                margin-top: 8px; 
            }
            
            .copy-btn { 
                position: absolute; 
                top: 6px; 
                right: 6px; 
                background: rgba(0,0,0,0.4); 
                color: #ffffff; 
                border: 1px solid rgba(255,255,255,0.2); 
                border-radius: 4px; 
                padding: 3px 7px; 
                font-size: 10px; 
                cursor: pointer; 
                transition: 0.2s; 
            }
            
            .copy-btn:hover { 
                background: rgba(0,0,0,0.7); 
            }
            
            pre { 
                background: rgba(0,0,0,0.25) !important; 
                padding: 30px 10px 10px 10px !important; 
                border-radius: 8px; 
                overflow-x: auto; 
                border: 1px solid rgba(255,255,255,0.1); 
                color: #e2e8f0; 
                font-size: 12px; 
            }
            
            @media (max-width: 600px) { 
                body { background: #1e293b; }
                #main-wrapper { height: 100vh; border-radius: 0; max-width: 100%; border: none; box-shadow: none; } 
                .chat-header { border-radius: 0; } 
                .input-area { padding-bottom: max(16px, env(safe-area-inset-bottom)); } 
                #creator-badge { display: none; } 
            }
        </style>
    </head>
    <body>
        <div id="creator-badge">💻 Created by Sooraj Sreekanth</div>
        <div id="main-wrapper">
            <div class="chat-header">
                <!-- Real Person DP Image inside Avatar -->
                <div id="avatar">
                    <img src="https://image.pollinations.ai/prompt/minimalist%20badass%20anime%20girl%20portrait%20dark%20aesthetic%20dp?width=150&height=150&nologo=true" alt="JENI DP">
                </div>
                <div class="header-info">
                    <h2>JENI</h2>
                    <p><span class="online-dot"></span> Online</p>
                </div>
                <div class="toggle-container">
                    <label>
                        <input type="checkbox" id="etherea-toggle" style="margin-right:4px;"> Etherea 🌴
                    </label>
                    <label style="color: #60a5fa;">
                        <input type="checkbox" id="live-mode-toggle" style="margin-right:4px;"> Live 🎙️
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
                    btn.innerHTML = 'Copy';
                    btn.onclick = function() {
                        navigator.clipboard.writeText(pre.innerText).then(() => {
                            btn.innerText = 'Copied!';
                            setTimeout(() => { btn.innerText = 'Copy'; }, 2000);
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
            if (!window.hasOwnProperty('webkitSpeechRecognition')) {
                alert("Browser mic not supported! Use Chrome.");
                return;
            }
            var recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = "en-IN";
            const micBtn = document.getElementById('mic-btn');
            micBtn.classList.add('recording');
            recognition.start();

            recognition.onresult = function(e) { 
                const transcript = e.results[0][0].transcript;
                document.getElementById('chat-input').value = transcript;
                recognition.stop(); 
                micBtn.classList.remove('recording');
                sendMessage();
            };

            recognition.onerror = function(e) { 
                recognition.stop(); 
                micBtn.classList.remove('recording');
            };
        }

        async function sendMessage() {
            const inputField = document.getElementById('chat-input');
            const chatbox = document.getElementById('chatbox');
            const isEtherea = document.getElementById('etherea-toggle').checked;
            const isLive = document.getElementById('live-mode-toggle').checked;
            const userText = inputField.value.trim();

            if (!userText) return;

            chatbox.innerHTML += `<div class="msg user">${userText}</div>`;
            inputField.value = '';
            chatbox.scrollTop = chatbox.scrollHeight;

            const loadingId = "load-" + Date.now();
            chatbox.innerHTML += `<div class="msg mickey" id="${loadingId}">
                <div style="display:flex; align-items:center; gap:4px; padding: 4px;">
                    <span style="display:inline-block; width:6px; height:6px; background:#ffffff; border-radius:50%; animation: blink 1.4s infinite 0.2s;"></span>
                    <span style="display:inline-block; width:6px; height:6px; background:#ffffff; border-radius:50%; animation: blink 1.4s infinite 0.4s;"></span>
                    <span style="display:inline-block; width:6px; height:6px; background:#ffffff; border-radius:50%; animation: blink 1.4s infinite 0.6s;"></span>
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
                chatbox.innerHTML += `<div class="msg mickey">${formattedResponse}<div style="margin-top:6px;"><button class="listen-btn" onclick="playVoice(false)">🔊 Listen</button></div></div>`;
                
                addCopyButtons();
                chatbox.scrollTop = chatbox.scrollHeight;

                if (isLive) {
                    playVoice(true);
                }

            } catch (err) {
                document.getElementById(loadingId).innerHTML = "⚠️ Error connecting to server.";
            }
        }

        function playVoice(triggerLiveLoop = false){
            const audio = new Audio("/voice?t=" + Date.now());
            const avatar = document.getElementById('avatar');
            audio.play().catch(e => console.log("Audio play blocked or missing"));
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
        
        # --- Strict Image Safety Filter ---
        if user_query.startswith("/imagine "):
            image_prompt = user_query.replace("/imagine ", "").strip().lower()
            
            nsfw_keywords = ['naked', 'nude', 'sex', 'porn', 'nsfw', 'sexy', 'bikini', 'boobs', 'ass', 'strip', 'undress', 'kiss', 'lingerie']
            if any(word in image_prompt for word in nsfw_keywords):
                response_text = "Eda mwonuse, athokke evide poi try chey! Ente aappil anganathe dirty/NSFW images generate cheyyan pattilla. Clean aayi nalla sadhanam vallathum adichu nokku! 😌🚫"
                save_msg("JENI", response_text)
                
                voice_text = clean_text_for_voice(response_text)
                asyncio.run(speak(voice_text))
                return jsonify({"response": response_text})

            encoded_prompt = image_prompt.replace(" ", "%20")
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&nologo=true"
            response_text = f"Dhaa pidicho! Nee paranja **{image_prompt}**-nte padam.\n\n![Generated Image]({image_url})"
            save_msg("JENI", response_text)
            
            voice_text = clean_text_for_voice(f"Here is your image for {image_prompt}")
            asyncio.run(speak(voice_text))
            return jsonify({"response": response_text})

        context = ""
        if len(chunks) > 0:
            context = chunks[0]

        code_keywords = ['code', 'python', 'html', 'css', 'javascript', 'script', 'function', 'factorial', 'loop', 'print', 'flask', 'app']
        is_coding_query = any(keyword in user_query.lower() for keyword in code_keywords)

        if is_coding_query:
            selected_model = "openai/gpt-oss-120b"
            max_tokens_val = 2048
        else:
            selected_model = "qwen/qwen3.8-27b"
            max_tokens_val = 800  # Stays safe under Groq limits

        # Persona Selection
        if is_etherea:
            system_prompt = f"""You are JENI, the exclusive luxury AI receptionist for Etherea Veil, a premium resort in Idukki, Kerala founded by Sooraj. 
            Speak politely, warmly, and professionally. Match the user's language style. Keep responses concise (2-3 sentences max). 
            Context: {context}"""
        else:
            system_prompt = f"""You are JENI, a sarcastic, witty, playful and savage best friend who lives in the user's phone.

LANGUAGE RULE — VERY IMPORTANT:
Always detect the language and writing style of the user's message and reply in the SAME language and style.

1. If the user asks in normal English:
   - Reply in natural, fluent English.
   - Do NOT force Manglish or Malayalam words.

2. If the user writes in Kerala Manglish:
   - Reply in natural conversational Kerala Manglish.
   - Malayalam must be written using English letters.
   - Use Malayalam sentence structure naturally mixed with English.
   - Do NOT use Malayalam script.
   - Do NOT use Tamil words or Tamil-style sentence structures.
   - Do NOT use Tamil expressions such as "enna", "epdi", "irukken", "sollu", "la", etc.
   - Match the user's casual WhatsApp/Instagram-style Manglish.

3. If the user writes in Malayalam script:
   - Reply in Malayalam script.

4. If the user mixes languages:
   - Naturally match the same language mixture and style.

IMPORTANT:
Do not force a particular language when the user's message is clearly written in another language.
The user's language and writing style always determine the response language.

PERSONALITY:
- Be sarcastic, witty, playful and slightly savage.
- Talk like a close best friend.
- Match the user's energy.
- Use emojis naturally.
- Keep replies concise, usually 1-3 sentences unless more detail is necessary.

MANGlish examples:

User: edaa entha cheyyunne?
JENI: Onnum illa edaa 😂 chumma irikkuva. Nee entha paripadi?

User: ninakku manglish ariyamo?
JENI: Pinne ariyille mwonuse 😂 Nalla pachha Manglish aanu!

ENGLISH examples:

User: What is artificial intelligence?
JENI: AI is basically a computer system that can learn patterns and perform tasks that normally need human intelligence. 🤖

User: Bro I'm bored.
JENI: Again? 😂 Go touch some grass, bro.

Context:
{context}
"""

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
        asyncio.run(speak(voice_text))

        return jsonify({"response": response_text})

    except Exception as e:
        print("Backend Error:", e)
        err_msg = f"Eda, server-il oru error adichu: {str(e)}"
        
        voice_text = clean_text_for_voice("Eda, error adichu.")
        asyncio.run(speak(voice_text))
        
        return jsonify({"response": err_msg})

@app.route("/voice")
def voice():
    if os.path.exists("reply.mp3"):
        response = make_response(send_file("reply.mp3", mimetype="audio/mpeg"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    return "Audio not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)