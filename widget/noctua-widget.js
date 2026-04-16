(() => {
  const script = document.currentScript;
  if (!script) return;

  const apiBase = script.dataset.apiBase || "http://localhost:8000";
  const clientId = script.dataset.clientId;
  const companyName = script.dataset.companyName || "Tu empresa";
  const title = script.dataset.title || "Asistente";
  const primaryColor = script.dataset.color || "#111827";

  if (!clientId) {
    console.error("[Noctua Widget] Falta data-client-id en el script.");
    return;
  }

  const SESSION_KEY = `noctua_session_${clientId}`;
  let sessionId = sessionStorage.getItem(SESSION_KEY) || null;
  let isOpen = false;
  let isSending = false;

  // ----- UI -----
  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.bottom = "24px";
  container.style.right = "24px";
  container.style.zIndex = "999999";
  document.body.appendChild(container);

  const shadow = container.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      * { box-sizing: border-box; font-family: Inter, Arial, sans-serif; }
      .btn {
        width: 64px; height: 64px; border-radius: 999px; border: none;
        cursor: pointer; color: #fff; background: ${primaryColor};
        box-shadow: 0 12px 32px rgba(0, 223, 216, 0.4); font-size: 26px;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s;
      }
      .btn:hover {
        transform: scale(1.08);
        box-shadow: 0 16px 40px rgba(0, 223, 216, 0.6);
      }
      .panel {
        width: 380px; height: 560px; 
        background: rgba(16, 16, 38, 0.85); 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 223, 216, 0.3); 
        border-radius: 20px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5), 0 0 20px rgba(79, 70, 229, 0.2); 
        overflow: hidden;
        display: none; flex-direction: column; margin-bottom: 20px;
        color: #fff;
        animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .header {
        background: linear-gradient(135deg, #4f46e5 0%, #00dfd8 100%);
        color: #fff; padding: 18px 20px;
        font-weight: 700; font-size: 16px;
        display: flex; align-items: center; gap: 10px;
      }
      .header-dot { width: 8px; height: 8px; background: #fff; border-radius: 50%; box-shadow: 0 0 10px #fff; }
      .messages {
        flex: 1; overflow-y: auto; padding: 20px; background: transparent;
        display: flex; flex-direction: column; gap: 12px;
      }
      .msg { max-width: 85%; padding: 14px 16px; border-radius: 16px; line-height: 1.5; font-size: 14px; }
      .user { 
        margin-left: auto; 
        background: #00dfd8; 
        color: #050510; 
        font-weight: 500;
        border-bottom-right-radius: 4px;
      }
      .bot { 
        margin-right: auto; 
        background: rgba(255,255,255,0.1); 
        color: #f8fafc; 
        border: 1px solid rgba(255,255,255,0.05);
        border-bottom-left-radius: 4px;
      }
      .composer { display: flex; gap: 10px; padding: 16px; border-top: 1px solid rgba(255,255,255,0.1); background: rgba(5,5,16,0.5); }
      .input { 
        flex: 1; border: 1px solid rgba(255,255,255,0.15); border-radius: 12px; 
        padding: 12px 14px; font-size: 14px; background: rgba(0,0,0,0.3); color: #fff;
        outline: none; transition: border-color 0.2s;
      }
      .input:focus { border-color: #00dfd8; }
      .send {
        border: none; border-radius: 12px; padding: 0 18px; cursor: pointer;
        background: #4f46e5; color: #fff; font-weight: 600; transition: background 0.2s;
      }
      .send:hover { background: #4338ca; }
      .hint { font-size: 12px; color: #94a3b8; padding: 8px 16px 16px; text-align: center; background: rgba(5,5,16,0.5); }
    </style>
    <div class="panel" id="panel">
      <div class="header">
        <div class="header-dot"></div>
        ${title}
      </div>
      <div class="messages" id="messages"></div>
      <div class="composer">
        <input id="input" class="input" placeholder="Escribe tu mensaje..." />
        <button id="send" class="send">Enviar</button>
      </div>
      <div class="hint">Conectado con ${companyName}</div>
    </div>
    <button class="btn" id="toggle">💬</button>
  `;

  const panel = shadow.getElementById("panel");
  const toggleBtn = shadow.getElementById("toggle");
  const messagesEl = shadow.getElementById("messages");
  const inputEl = shadow.getElementById("input");
  const sendBtn = shadow.getElementById("send");

  const addMessage = (text, role = "bot") => {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  };

  const startSession = async () => {
    if (sessionId) return sessionId;
    const res = await fetch(`${apiBase}/chat/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId })
    });
    if (!res.ok) throw new Error("No se pudo iniciar sesión de chat");
    const data = await res.json();
    sessionId = data.session_id;
    sessionStorage.setItem(SESSION_KEY, sessionId);
    return sessionId;
  };

  const sendQuestion = async (question, retry = true) => {
    await startSession();

    const res = await fetch(`${apiBase}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        company_name: companyName,
        session_id: sessionId,
        question
      })
    });

    if (res.status === 410 && retry) {
      sessionId = null;
      sessionStorage.removeItem(SESSION_KEY);
      return sendQuestion(question, false);
    }

    if (!res.ok) throw new Error("Error consultando el chat");
    return res.json();
  };

  const onSend = async () => {
    if (isSending) return;
    const text = inputEl.value.trim();
    if (!text) return;

    inputEl.value = "";
    addMessage(text, "user");

    isSending = true;
    sendBtn.disabled = true;
    try {
      const data = await sendQuestion(text);
      addMessage(data.answer || "No he podido responder ahora mismo.", "bot");
    } catch (e) {
      addMessage("Ups, ahora mismo no puedo responder. Inténtalo en unos segundos.", "bot");
      console.error("[Noctua Widget]", e);
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  };

  toggleBtn.addEventListener("click", () => {
    isOpen = !isOpen;
    panel.style.display = isOpen ? "flex" : "none";
    if (isOpen && messagesEl.children.length === 0) {
      addMessage(`¡Hola! Soy el asistente de ${companyName}. ¿En qué te ayudo?`, "bot");
      startSession().catch(() => {});
    }
  });

  sendBtn.addEventListener("click", onSend);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") onSend();
  });
})();