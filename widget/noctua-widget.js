(() => {
  let script =
    document.currentScript ||
    document.getElementById("noctua-demo-script") ||
    document.querySelector("script[src*='noctua-widget']");
  if (!script) return;

  const apiBase = script.dataset.apiBase || "http://localhost:8000";
  const clientId = (script.dataset.clientId || "").trim();

  if (!clientId) {
    console.error("[Noctua Widget] Falta data-client-id en el script.");
    return;
  }

  const DEFAULT_THEME = {
    companyName: "Tu empresa",
    title: "Asistente",
    welcomeMessage: "",
    placeholder: "Escribe tu mensaje...",
    sendLabel: "Enviar",
    launcherIcon: "💬",
    position: "right",
    panelWidth: "420px",
    panelHeight: "620px",
    primaryColor: "#00dfd8",
    secondaryColor: "#4f46e5",
    panelBackgroundColor: "#101026",
    panelTextColor: "#f8fafc",
    inputBg: "#0d0f1f",
    inputText: "#f8fafc",
    inputBorder: "#2b2f43",
    userBubbleBg: "#00dfd8",
    userBubbleText: "#050510",
    botBubbleBg: "#2b2f43",
    botBubbleText: "#f8fafc",
    sendButtonBg: "#4f46e5",
    sendButtonText: "#ffffff",
    hintTextColor: "#94a3b8",
  };

  const sanitizeText = (value, fallback, maxLen = 120) => {
    const text = String(value == null ? "" : value).trim();
    if (!text) return fallback;
    return text.slice(0, maxLen);
  };

  const escapeHtml = (value) =>
    String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const normalizeColor = (value, fallback) => {
    const raw = String(value || "").trim();
    if (!raw) return fallback;
    const testNode = document.createElement("span");
    testNode.style.color = "";
    testNode.style.color = raw;
    if (!testNode.style.color) return fallback;
    return testNode.style.color;
  };

  const normalizePosition = (value) => {
    const normalized = String(value || "").toLowerCase();
    if (normalized === "left") return "left";
    return "right";
  };

  const normalizeDimension = (value, fallback, min, max) => {
    const raw = String(value || "").trim().replace("px", "");
    const numeric = Number(raw);
    if (!Number.isFinite(numeric)) return fallback;
    const clamped = Math.min(max, Math.max(min, numeric));
    return `${clamped}px`;
  };

  const normalizeIcon = (value, fallback) => {
    const text = sanitizeText(value, fallback, 6);
    return text || fallback;
  };

  const companyName = sanitizeText(script.dataset.companyName, DEFAULT_THEME.companyName, 80);
  const theme = {
    companyName,
    title: sanitizeText(script.dataset.title, DEFAULT_THEME.title, 80),
    welcomeMessage: sanitizeText(
      script.dataset.welcomeMessage,
      `¡Hola! Soy el asistente de ${companyName}. ¿En qué te ayudo?`,
      240
    ),
    placeholder: sanitizeText(script.dataset.placeholder, DEFAULT_THEME.placeholder, 80),
    sendLabel: sanitizeText(script.dataset.sendLabel, DEFAULT_THEME.sendLabel, 24),
    launcherIcon: normalizeIcon(script.dataset.icon, DEFAULT_THEME.launcherIcon),
    position: normalizePosition(script.dataset.position || DEFAULT_THEME.position),
    panelWidth: normalizeDimension(script.dataset.panelWidth, DEFAULT_THEME.panelWidth, 300, 520),
    panelHeight: normalizeDimension(script.dataset.panelHeight, DEFAULT_THEME.panelHeight, 420, 760),
    primaryColor: normalizeColor(script.dataset.colorPrimary || script.dataset.color, DEFAULT_THEME.primaryColor),
    secondaryColor: normalizeColor(script.dataset.colorSecondary, DEFAULT_THEME.secondaryColor),
    panelBackgroundColor: normalizeColor(script.dataset.colorPanel, DEFAULT_THEME.panelBackgroundColor),
    panelTextColor: normalizeColor(script.dataset.colorText, DEFAULT_THEME.panelTextColor),
    inputBg: normalizeColor(script.dataset.colorInputBg, DEFAULT_THEME.inputBg),
    inputText: normalizeColor(script.dataset.colorInputText, DEFAULT_THEME.inputText),
    inputBorder: normalizeColor(script.dataset.colorInputBorder, DEFAULT_THEME.inputBorder),
    userBubbleBg: normalizeColor(script.dataset.colorUserBubbleBg, DEFAULT_THEME.userBubbleBg),
    userBubbleText: normalizeColor(script.dataset.colorUserBubbleText, DEFAULT_THEME.userBubbleText),
    botBubbleBg: normalizeColor(script.dataset.colorBotBubbleBg, DEFAULT_THEME.botBubbleBg),
    botBubbleText: normalizeColor(script.dataset.colorBotBubbleText, DEFAULT_THEME.botBubbleText),
    sendButtonBg: normalizeColor(script.dataset.colorSendButton || script.dataset.colorSecondary, DEFAULT_THEME.sendButtonBg),
    sendButtonText: normalizeColor(script.dataset.colorSendButtonText, DEFAULT_THEME.sendButtonText),
    hintTextColor: normalizeColor(script.dataset.colorHintText, DEFAULT_THEME.hintTextColor),
  };

  const SESSION_KEY = `noctua_session_${clientId}`;
  let sessionId = sessionStorage.getItem(SESSION_KEY) || null;
  let isOpen = false;
  let isSending = false;

  // ----- UI -----
  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.bottom = "24px";
  container.style[theme.position] = "24px";
  container.style.zIndex = "999999";
  document.body.appendChild(container);

  const shadow = container.attachShadow({ mode: "open" });
  const safeTitle = escapeHtml(theme.title);
  const safePlaceholder = escapeHtml(theme.placeholder);
  const safeSendLabel = escapeHtml(theme.sendLabel);
  const safeCompanyName = escapeHtml(theme.companyName);

  shadow.innerHTML = `
    <style>
      * { box-sizing: border-box; font-family: Inter, Arial, sans-serif; }
      .btn {
        width: 64px; height: 64px; border-radius: 999px; border: none;
        cursor: pointer; color: #fff; background: ${theme.primaryColor};
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35); font-size: 26px;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s;
      }
      .btn:hover {
        transform: scale(1.08);
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5);
      }
      .panel {
        width: min(${theme.panelWidth}, calc(100vw - 32px));
        height: min(${theme.panelHeight}, calc(100vh - 110px));
        background: ${theme.panelBackgroundColor};
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid ${theme.inputBorder};
        border-radius: 20px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        overflow: hidden;
        display: none; flex-direction: column; margin-bottom: 20px;
        color: ${theme.panelTextColor};
        animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      }
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .header {
        background: linear-gradient(135deg, ${theme.secondaryColor} 0%, ${theme.primaryColor} 100%);
        color: #fff; padding: 18px 20px;
        font-weight: 700; font-size: 16px;
        display: flex; align-items: center; gap: 10px;
      }
      .header-dot { width: 8px; height: 8px; background: #fff; border-radius: 50%; box-shadow: 0 0 10px #fff; }
      .messages {
        flex: 1; overflow-y: auto; padding: 20px; background: transparent;
        display: flex; flex-direction: column; gap: 12px;
      }
      .msg { max-width: 85%; padding: 14px 16px; border-radius: 16px; line-height: 1.5; font-size: 14px; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word; }
      .user {
        margin-left: auto; 
        background: ${theme.userBubbleBg};
        color: ${theme.userBubbleText};
        font-weight: 500;
        border-bottom-right-radius: 4px;
      }
      .bot { 
        margin-right: auto; 
        background: ${theme.botBubbleBg};
        color: ${theme.botBubbleText};
        border: 1px solid rgba(255,255,255,0.04);
        border-bottom-left-radius: 4px;
      }
      .composer { display: flex; gap: 10px; padding: 16px; border-top: 1px solid rgba(255,255,255,0.08); background: rgba(5,5,16,0.35); align-items: center; }
      .input { 
        flex: 1; min-width: 0; border: 1px solid ${theme.inputBorder}; border-radius: 12px;
        padding: 12px 14px; font-size: 14px; background: ${theme.inputBg}; color: ${theme.inputText};
        outline: none; transition: border-color 0.2s;
      }
      .input:focus { border-color: ${theme.primaryColor}; }
      .send {
        flex: 0 0 auto; min-width: 86px; max-width: 45%; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis;
        border: none; border-radius: 12px; padding: 12px 16px; cursor: pointer;
        background: ${theme.sendButtonBg}; color: ${theme.sendButtonText}; font-weight: 600; transition: filter 0.2s;
      }
      .send:hover { filter: brightness(1.08); }
      .hint { font-size: 12px; color: ${theme.hintTextColor}; padding: 8px 16px 16px; text-align: center; background: rgba(5,5,16,0.35); }
      @media (max-width: 480px) {
        .panel { border-radius: 16px; }
        .messages { padding: 14px; }
        .composer { padding: 12px; gap: 8px; }
        .send { min-width: 74px; padding: 10px 12px; }
      }
    </style>
    <div class="panel" id="panel">
      <div class="header">
        <div class="header-dot"></div>
        ${safeTitle}
      </div>
      <div class="messages" id="messages"></div>
      <div class="composer">
        <input id="input" class="input" placeholder="${safePlaceholder}" />
        <button id="send" class="send">${safeSendLabel}</button>
      </div>
      <div class="hint">Conectado con ${safeCompanyName}</div>
    </div>
    <button class="btn" id="toggle"></button>
  `;

  const panel = shadow.getElementById("panel");
  const toggleBtn = shadow.getElementById("toggle");
  const messagesEl = shadow.getElementById("messages");
  const inputEl = shadow.getElementById("input");
  const sendBtn = shadow.getElementById("send");
  toggleBtn.textContent = theme.launcherIcon;

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
        company_name: theme.companyName,
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
      addMessage(theme.welcomeMessage, "bot");
      startSession().catch(() => {});
    }
  });

  sendBtn.addEventListener("click", onSend);
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") onSend();
  });
})();