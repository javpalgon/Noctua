(function () {
  const { useMemo, useState, useEffect } = React;
  const h = React.createElement;

  const API_BASE_URL =
    (window.NOCTUA_CONFIG && window.NOCTUA_CONFIG.apiBaseUrl) ||
    "http://localhost:8000";

  const SESSION_TOKEN_KEY = "noctua_user_token";
  const SESSION_EMAIL_KEY = "noctua_user_email";

  const INITIAL_FORM = {
    company_name: "",
    url_portal: "",
    single_url: false,
  };

  const INITIAL_LOGIN_FORM = {
    email: "",
    password: "",
  };

  const INITIAL_SIGNUP_FORM = {
    email: "",
    password: "",
  };

  const WIDGET_STYLE_DEFAULTS = {
    title: "Asistente",
    welcome_message: "",
    placeholder: "Escribe tu mensaje...",
    send_label: "Enviar",
    position: "right",
    icon: "💬",
    color_primary: "#00dfd8",
    color_secondary: "#4f46e5",
    color_panel: "#101026",
    color_text: "#f8fafc",
    color_input_bg: "#0d0f1f",
    color_input_text: "#f8fafc",
    color_input_border: "#2b2f43",
    color_user_bubble_bg: "#00dfd8",
    color_user_bubble_text: "#050510",
    color_bot_bubble_bg: "#2b2f43",
    color_bot_bubble_text: "#f8fafc",
    panel_width: "420",
    panel_height: "620",
  };

  function cloneWidgetDefaults() {
    return Object.assign({}, WIDGET_STYLE_DEFAULTS);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function parseError(payload, fallback) {
    if (!payload) return fallback;
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) return payload.detail.map((x) => x.msg).join(" | ");
    if (payload.message) return payload.message;
    return fallback;
  }

  function buildWidgetSnippet(options, includeOptional = false) {
    const origin = window.location.origin && window.location.origin !== "null"
      ? window.location.origin
      : "http://localhost:3000";
    const scriptSrc = origin + "/widget/noctua-widget.js";

    const attrs = [
      ["data-api-base", options.apiBase],
      ["data-client-id", options.clientId],
      ["data-company-name", options.companyName],
    ];

    if (includeOptional) {
      const defaults = options.widgetDefaults || WIDGET_STYLE_DEFAULTS;
      const welcomeMessage = defaults.welcome_message && defaults.welcome_message.trim().length > 0
        ? defaults.welcome_message
        : `¡Hola! Soy el asistente de ${options.companyName}. ¿En qué te ayudo?`;
      attrs.push(
        ["data-title", defaults.title],
        ["data-welcome-message", welcomeMessage],
        ["data-placeholder", defaults.placeholder],
        ["data-send-label", defaults.send_label],
        ["data-position", defaults.position],
        ["data-icon", defaults.icon],
        ["data-color-primary", defaults.color_primary],
        ["data-color-secondary", defaults.color_secondary],
        ["data-color-panel", defaults.color_panel],
        ["data-color-text", defaults.color_text],
        ["data-color-input-bg", defaults.color_input_bg],
        ["data-color-input-text", defaults.color_input_text],
        ["data-color-input-border", defaults.color_input_border],
        ["data-color-user-bubble-bg", defaults.color_user_bubble_bg],
        ["data-color-user-bubble-text", defaults.color_user_bubble_text],
        ["data-color-bot-bubble-bg", defaults.color_bot_bubble_bg],
        ["data-color-bot-bubble-text", defaults.color_bot_bubble_text],
        ["data-panel-width", defaults.panel_width],
        ["data-panel-height", defaults.panel_height]
      );
    }

    const attributesBlock = attrs
      .map(function (pair) {
        const key = pair[0];
        const val = escapeHtml(pair[1]);
        return `  ${key}="${val}"`;
      })
      .join("\n");

    return `<script\n  src="${scriptSrc}"\n${attributesBlock}\n  defer\n></script>`;
  }

  function getPageFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("page") || "inicio";
  }

  function withPageInUrl(page) {
    const params = new URLSearchParams(window.location.search);
    params.set("page", page);
    return "?" + params.toString();
  }

  function DemoPage() {
    useEffect(function () {
      const DEMO_CLIENT_ID = "ba6c6b9e-aab1-4617-bb96-d6d65ad37b73";
      const SCRIPT_ID = "noctua-demo-script";

      const existing = document.getElementById(SCRIPT_ID);
      if (existing) existing.remove();

      const s = document.createElement("script");
      s.id = SCRIPT_ID;
      s.src = window.location.origin + "/widget/noctua-widget.js";
      s.dataset.apiBase = API_BASE_URL;
      s.dataset.clientId = DEMO_CLIENT_ID;
      s.dataset.companyName = "Noctua Demo";
      s.dataset.title = "Asistente Demo";
      s.dataset.welcomeMessage = "¡Hola! Soy el asistente demo de Noctua. ¿En qué te ayudo?";
      s.defer = true;
      document.body.appendChild(s);

      return function () {
        const existing = document.getElementById(SCRIPT_ID);
        if (existing) existing.remove();
        document.querySelectorAll("body > div[style*='position: fixed']").forEach(function (el) {
          if (el.shadowRoot) el.remove();
        });
      };
    }, []);

    return h(
      "div",
      { className: "animate-enter section" },
      h("div", { className: "hero" },
        h("h1", { style: { fontSize: "3rem" } }, "Demo en vivo"),
        h("p", null, "Prueba el widget de Noctua directamente aquí."),
        h("p", { style: { color: "var(--text-muted)", fontSize: "0.9rem", marginTop: "12px" } },
          "👇 El botón del chat aparece abajo a la derecha."
        )
      )
    );
  }

  function App() {
    const [page, setPage] = useState(getPageFromUrl());
    const [form, setForm] = useState(INITIAL_FORM);
    const [createdClient, setCreatedClient] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [widgetConfig, setWidgetConfig] = useState(() => cloneWidgetDefaults());

    // Auth state — single source of truth
    const [user, setUser] = useState(() => {
      const token = localStorage.getItem(SESSION_TOKEN_KEY);
      const email = localStorage.getItem(SESSION_EMAIL_KEY);
      return token ? { token, email } : null;
    });
    const [loginForm, setLoginForm] = useState(INITIAL_LOGIN_FORM);
    const [signupForm, setSignupForm] = useState(INITIAL_SIGNUP_FORM);
    const [userBots, setUserBots] = useState([]);
    const [postLoginRedirect, setPostLoginRedirect] = useState(null);
    const [authLoading, setAuthLoading] = useState(false);
    const [authError, setAuthError] = useState("");
    const [chatbots, setChatbots] = useState([]);
    const [chatbotsLoading, setChatbotsLoading] = useState(false);
    const [chatbotsError, setChatbotsError] = useState("");
    const [refreshState, setRefreshState] = useState({});
    const [refreshOptions, setRefreshOptions] = useState({});

    // Derived from user object — no separate userToken/userEmail state needed
    const userToken = user ? user.token : "";
    const userEmail = user ? user.email : "";
    const isLoggedIn = !!user;

    // Sync page from browser back/forward
    useEffect(function () {
      function syncPageFromUrl() {
        setPage(getPageFromUrl());
      }
      window.addEventListener("popstate", syncPageFromUrl);
      if (window.navigation && typeof window.navigation.addEventListener === "function") {
        window.navigation.addEventListener("currententrychange", syncPageFromUrl);
      }
      return function () {
        window.removeEventListener("popstate", syncPageFromUrl);
      };
    }, []);

    // Persist session to localStorage whenever user changes
    useEffect(function () {
      if (user) {
        localStorage.setItem(SESSION_TOKEN_KEY, user.token);
        localStorage.setItem(SESSION_EMAIL_KEY, user.email || "");
      } else {
        localStorage.removeItem(SESSION_TOKEN_KEY);
        localStorage.removeItem(SESSION_EMAIL_KEY);
      }
    }, [user]);

    // Load bots when entering dashboard
    useEffect(function () {
      if (page === "dashboard" && user) {
        loadMyChatbots(user.token);
      }
    }, [page, user]);

    useEffect(function () {
      if (page === "integracion") {
        setWidgetConfig(cloneWidgetDefaults());
      }
    }, [page, result]);

    function navigateTo(nextPage) {
      // Soft Gating: protege registro y dashboard
      if ((nextPage === "dashboard" || nextPage === "registro") && !user) {
        setPostLoginRedirect(nextPage);
        setAuthError("");
        setPage("login");
        window.history.pushState({}, "", withPageInUrl("login"));
        return;
      }
      setPage(nextPage);
      window.history.pushState({}, "", withPageInUrl(nextPage));
      window.scrollTo(0, 0);
    }

    function mapsTo(pageName) {
      navigateTo(pageName);
    }

    function logout() {
      setUser(null);
      setCreatedClient(null);
      setChatbots([]);
      setChatbotsError("");
      setRefreshState({});
      setRefreshOptions({});
      setPostLoginRedirect(null);
      setPage("inicio");
      window.history.pushState({}, "", withPageInUrl("inicio"));
    }

    function requireLogin(nextPageAfterLogin) {
      setPostLoginRedirect(nextPageAfterLogin);
      setAuthError("");
      mapsTo("login");
    }

    const ctaText = useMemo(function () {
      return loading ? "Generando conocimiento..." : "Generar Grafo";
    }, [loading]);

    function onFormChange(event) {
      const name = event.target.name;
      const value = event.target.value;
      setForm(function (prev) {
        return Object.assign({}, prev, { [name]: value });
      });
    }

    function onLoginFormChange(event) {
      const name = event.target.name;
      const value = event.target.value;
      setLoginForm(function (prev) {
        return Object.assign({}, prev, { [name]: value });
      });
    }

    function onSignupFormChange(event) {
      const name = event.target.name;
      const value = event.target.value;
      setSignupForm(function (prev) {
        return Object.assign({}, prev, { [name]: value });
      });
    }

    function updateWidgetConfig(key, value) {
      setWidgetConfig(function (prev) {
        return Object.assign({}, prev, { [key]: value });
      });
    }

    async function loadMyChatbots(token) {
      const tok = token || userToken;
      if (!tok) return;

      setChatbotsLoading(true);
      setChatbotsError("");
      try {
        const response = await fetch(API_BASE_URL + "/me/chatbots", {
          method: "GET",
          headers: {
            Authorization: "Bearer " + tok,
          },
        });
        const payload = await response.json().catch(() => ({}));

        if (response.status === 401) {
          logout();
          requireLogin("dashboard");
          return;
        }

        if (!response.ok) {
          throw new Error(parseError(payload, "No se pudo cargar el dashboard"));
        }

        const bots = Array.isArray(payload) ? payload : [];
        setChatbots(bots);
        setUserBots(bots);
      } catch (error) {
        setChatbotsError(error?.message || "Error cargando tus chatbots");
      } finally {
        setChatbotsLoading(false);
      }
    }

    function setRefreshStatus(botId, status, message) {
      setRefreshState(function (prev) {
        return Object.assign({}, prev, {
          [botId]: { status: status, message: message }
        });
      });
    }

    function clearRefreshStatus(botId) {
      setRefreshState(function (prev) {
        if (!prev[botId]) return prev;
        const next = Object.assign({}, prev);
        delete next[botId];
        return next;
      });
    }

    function setRefreshOption(botId, value) {
      setRefreshOptions(function (prev) {
        return Object.assign({}, prev, { [botId]: value });
      });
    }

    async function refreshGraph(bot) {
      if (!bot || !bot.id) return;
      const botId = bot.id;
      if (!userToken) {
        requireLogin("dashboard");
        return;
      }

      const singleUrl = !!refreshOptions[botId];

      setRefreshStatus(
        botId,
        "loading",
        singleUrl ? "Actualizando solo esta URL..." : "Actualizando grafo..."
      );
      try {
        const refreshUrl = API_BASE_URL + "/clientes/" + botId + "/refresh" +
          (singleUrl ? "?single_url=true" : "");
        const response = await fetch(refreshUrl, {
          method: "POST",
          headers: {
            Authorization: "Bearer " + userToken,
          },
        });
        const payload = await response.json().catch(() => ({}));

        if (response.status === 401) {
          logout();
          requireLogin("dashboard");
          return;
        }

        if (!response.ok) {
          throw new Error(parseError(payload, "No se pudo actualizar el grafo"));
        }

        setRefreshStatus(botId, "success", "Actualización iniciada");
        setTimeout(function () {
          clearRefreshStatus(botId);
        }, 2600);
      } catch (error) {
        setRefreshStatus(botId, "error", error?.message || "Error actualizando el grafo");
      }
    }

    async function onSubmit(event) {
      event.preventDefault();

      if (!isLoggedIn) {
        requireLogin("registro");
        return;
      }

      setLoading(true);
      setResult(null);
      try {
        const response = await fetch(API_BASE_URL + "/clientes", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + userToken,
          },
          body: JSON.stringify(form),
        });

        const payload = await response.json().catch(() => ({}));

        if (response.status === 401) {
          logout();
          requireLogin("registro");
          return;
        }

        if (!response.ok) {
          throw new Error(parseError(payload, "Fallo al crear el asistente"));
        }

        setCreatedClient(payload);
        setResult({ type: "success", payload: payload });
        setForm(INITIAL_FORM);
        loadMyChatbots();
        setTimeout(() => mapsTo("integracion"), 1200);
      } catch (error) {
        setResult({ type: "error", message: error?.message || "Error inesperado" });
      } finally {
        setLoading(false);
      }
    }

    async function onRegisterSubmit(event) {
      event.preventDefault();
      setAuthLoading(true);
      setAuthError("");
      try {
        const response = await fetch(API_BASE_URL + "/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(signupForm),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(parseError(payload, "No se pudo crear la cuenta"));
        }

        const email = payload.email || signupForm.email;
        setUser({ token: payload.access_token, email });
        setSignupForm(INITIAL_SIGNUP_FORM);
        const destination = postLoginRedirect || "dashboard";
        setPostLoginRedirect(null);
        setPage(destination);
        window.history.pushState({}, "", withPageInUrl(destination));
        window.scrollTo(0, 0);
      } catch (error) {
        setAuthError(error?.message || "Error de registro");
      } finally {
        setAuthLoading(false);
      }
    }

    async function onLoginSubmit(event) {
      event.preventDefault();
      setAuthLoading(true);
      setAuthError("");
      try {
        const response = await fetch(API_BASE_URL + "/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(loginForm),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(parseError(payload, "No se pudo iniciar sesión"));
        }

        const email = payload.email || loginForm.email;
        setUser({ token: payload.access_token, email });
        setLoginForm(INITIAL_LOGIN_FORM);
        const destination = postLoginRedirect || "dashboard";
        setPostLoginRedirect(null);
        setPage(destination);
        window.history.pushState({}, "", withPageInUrl(destination));
        window.scrollTo(0, 0);
      } catch (error) {
        setAuthError(error?.message || "Error de login");
      } finally {
        setAuthLoading(false);
      }
    }

    // ─── RENDER FUNCTIONS ───────────────────────────────────────────────────

    function renderInicio() {
      return h(
        "div",
        { className: "animate-enter flex-col", style: { display: "flex", gap: "60px" } },
        h(
          "section",
          { className: "hero" },
          h(
            "div",
            { className: "badge" },
            h("span", { style: { display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: "#00dfd8", boxShadow: "0 0 10px #00dfd8" } }),
            "Noctua AI v2.0"
          ),
          h("h1", null, "La inteligencia que tu negocio merece."),
          h(
            "p",
            null,
            "Transformamos todo el conocimiento de tu web en un asistente conversacional avanzado."
          ),
          h(
            "div",
            { className: "hero-actions" },
            h("button", { className: "btn btn-primary", onClick: () => mapsTo("registro") }, "Probar gratis"),
            h("button", { className: "btn btn-ghost", onClick: () => mapsTo("funcionalidades") }, "Descubrir más")
          )
        )
      );
    }

    function renderFuncionalidades() {
      return h(
        "div",
        { className: "animate-enter section" },
        h("div", { className: "hero" },
          h("h1", { style: { fontSize: "3rem" } }, "Potencia inigualable."),
          h("p", null, "Arquitectura moderna con IA de última generación para B2B.")
        ),
        h(
          "div",
          { className: "bento-grid" },
          h(
            "div",
            { className: "bento-card bento-large bento-hover-primary" },
            h("h3", null, "IA Consciente del Contexto"),
            h("p", null, "Noctua emplea GraphRAG avanzado para entender relaciones complejas en tus datos evitando alucinaciones comerciales.")
          ),
          h(
            "div",
            { className: "bento-card bento-hover-secondary" },
            h("h3", null, "Rendimiento Global"),
            h("p", null, "Memoria en Redis, escalabilidad masiva y latencia ultra baja para tus clientes en cualquier lugar.")
          ),
          h(
            "div",
            { className: "bento-card bento-hover-accent" },
            h("h3", null, "Seguridad B2B"),
            h("p", null, "Aislamiento por cliente y contexto restringido para respuestas alineadas con cada marca.")
          ),
          h(
            "div",
            { className: "bento-card bento-large bento-hover-accent" },
            h("h3", null, "Integración Sin Fricción"),
            h("p", null, "Genera tu bot y copia un snippet para incrustarlo en minutos en cualquier sitio web.")
          )
        )
      );
    }

    function renderLoginForm() {
      return h(
        "div",
        { className: "animate-enter form-container" },
        h("div", { className: "form-header" },
          h("h2", null, "Iniciar sesión"),
          h("p", null, "Accede para crear grafos y ver tu dashboard de chatbots.")
        ),
        h(
          "form",
          { className: "form", onSubmit: onLoginSubmit },
          h("label", null, "Email", h("input", {
            type: "email",
            name: "email",
            value: loginForm.email,
            onChange: onLoginFormChange,
            required: true,
            placeholder: "tu@email.com",
          })),
          h("label", null, "Contraseña", h("input", {
            type: "password",
            name: "password",
            value: loginForm.password,
            onChange: onLoginFormChange,
            required: true,
            placeholder: "********",
          })),
          h("button", { type: "submit", className: "btn btn-primary", disabled: authLoading }, authLoading ? "Entrando..." : "Entrar")
        ),
        authError && h("div", { className: "alert alert-error", style: { marginTop: "16px" } }, "Error: " + authError),
        h("div", { style: { marginTop: "14px", color: "var(--text-secondary)", fontSize: "0.9rem" } },
          "¿No tienes cuenta? ",
          h("button", { className: "btn btn-ghost", style: { marginLeft: "8px", padding: "8px 14px" }, onClick: () => mapsTo("signup") }, "Crear cuenta")
        )
      );
    }

    function renderSignupForm() {
      return h(
        "div",
        { className: "animate-enter form-container" },
        h("div", { className: "form-header" },
          h("h2", null, "Crear cuenta"),
          h("p", null, "Regístrate para gestionar tus bots y generar grafos privados.")
        ),
        h(
          "form",
          { className: "form", onSubmit: onRegisterSubmit },
          h("label", null, "Email", h("input", {
            type: "email",
            name: "email",
            value: signupForm.email,
            onChange: onSignupFormChange,
            required: true,
            placeholder: "tu@email.com",
          })),
          h("label", null, "Contraseña (mínimo 8 caracteres)", h("input", {
            type: "password",
            name: "password",
            value: signupForm.password,
            onChange: onSignupFormChange,
            required: true,
            minLength: 8,
            placeholder: "********",
          })),
          h("button", { type: "submit", className: "btn btn-primary", disabled: authLoading }, authLoading ? "Creando..." : "Crear cuenta")
        ),
        authError && h("div", { className: "alert alert-error", style: { marginTop: "16px" } }, "Error: " + authError),
        h("div", { style: { marginTop: "14px", color: "var(--text-secondary)", fontSize: "0.9rem" } },
          "¿Ya tienes cuenta? ",
          h("button", { className: "btn btn-ghost", style: { marginLeft: "8px", padding: "8px 14px" }, onClick: () => mapsTo("login") }, "Iniciar sesión")
        )
      );
    }

    function renderRegistro() {
      if (result && result.type === "success") {
        return h("div", { className: "container py-lg" },
          h("div", { className: "card", style: { textAlign: 'center' } },
            h("h2", null, "¡Bot creado con éxito!"),
            h("p", { style: { marginBottom: '20px' } }, "Ya tienes un chatbot configurado para esta sesión."),
            h("button", { 
              className: "btn btn-primary", 
              onClick: () => navigateTo('integracion') 
            }, "Ver código de instalación")
          )
        );
      }

      return h(
        "div",
        { className: "animate-enter form-container" },
        h("div", { className: "form-header" },
          h("h2", null, "Crear nuevo Asistente"),
          h("p", null, "Introduce tu empresa y URL para generar el grafo de conocimiento."),
        ),
        h("form", {
          className: "form",
          onSubmit: onSubmit
        },
          h("label", null, "Nombre de la empresa", h("input", {
            placeholder: "Ej: Mi Negocio S.L.",
            value: form.company_name,
            onChange: (e) => setForm({ ...form, company_name: e.target.value }),
            required: true
          })),
          h("label", null, "URL del sitio web", h("input", {
            placeholder: "https://tudominio.com",
            type: "url",
            value: form.url_portal,
            onChange: (e) => setForm({ ...form, url_portal: e.target.value }),
            required: true
          })),
          h("label", {
            style: {
              display: "flex",
              alignItems: "center",
              gap: "10px",
              fontSize: "0.9rem",
              color: "var(--text-secondary)"
            }
          },
          h("input", {
            type: "checkbox",
            checked: !!form.single_url,
            onChange: (e) => setForm({ ...form, single_url: e.target.checked }),
            style: { width: "18px", height: "18px" }
          }),
          "Crear solo con esta URL (sin subpaginas)"
          ),
          h("button", { type: "submit", className: "btn btn-primary", disabled: loading },
            loading ? "Generando conocimiento..." : "Crear Chatbot"
          )
        )
      );
    }

    function renderDashboard() {
      return h(
        "div",
        { className: "animate-enter section", style: { maxWidth: "980px", margin: "0 auto" } },
        h("div", { className: "hero", style: { padding: "30px 20px" } },
          h("h1", { style: { fontSize: "2.3rem" } }, "Tu Dashboard"),
          h("p", null, "Gestiona todos los chatbots asociados a tu cuenta: " + (userEmail || ""))
        ),
        h("div", { style: { display: "flex", justifyContent: "center", marginBottom: "18px" } },
          h("button", { className: "btn btn-primary", onClick: () => mapsTo("registro") }, "Crear nuevo chatbot")
        ),
        chatbotsLoading && h("div", { className: "alert alert-success" }, "Cargando chatbots..."),
        chatbotsError && h("div", { className: "alert alert-error" }, "Error: " + chatbotsError),
        !chatbotsLoading && chatbots.length === 0 && h(
          "div",
          { className: "bento-card", style: { textAlign: "center" } },
          h("h3", null, "Aún no tienes chatbots"),
          h("p", null, "Crea el primero desde 'Crear nuevo chatbot'.")
        ),
        !chatbotsLoading && chatbots.length > 0 && h(
          "div",
          {
            style: {
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "14px",
            }
          },
          chatbots.map(function (bot) {
            const refreshInfo = refreshState[bot.id];
            const isRefreshing = refreshInfo && refreshInfo.status === "loading";
            const refreshSingleUrl = !!refreshOptions[bot.id];
            const statusColor = refreshInfo && refreshInfo.status === "error"
              ? "#ff5f56"
              : refreshInfo && refreshInfo.status === "success"
                ? "#27c93f"
                : "var(--text-muted)";

            return h(
              "div",
              { key: bot.id, className: "bento-card" },
              h("h3", null, bot.company_name),
              h("p", { style: { wordBreak: "break-all" } }, bot.url_portal),
              h("p", { style: { color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "8px" } }, "ID: " + bot.id),
              h("div", { style: { display: "flex", gap: "8px", marginTop: "14px", flexWrap: "wrap" } },
                h("button", {
                  className: "btn btn-ghost",
                  onClick: function () {
                    setCreatedClient(bot);
                    setResult({ type: "integracion", payload: bot });
                    mapsTo("integracion");
                  }
                }, "Integrar"),
                h("button", {
                  className: "btn btn-ghost",
                  disabled: isRefreshing,
                  onClick: function () {
                    refreshGraph(bot);
                  }
                }, isRefreshing ? "Actualizando..." : "Actualizar grafo")
              ),
              h("label", {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginTop: "10px",
                  fontSize: "0.8rem",
                  color: "var(--text-secondary)"
                }
              },
              h("input", {
                type: "checkbox",
                checked: refreshSingleUrl,
                onChange: function (e) {
                  setRefreshOption(bot.id, e.target.checked);
                },
                style: { width: "16px", height: "16px" }
              }),
              "Actualizar solo esta URL"
              ),
              refreshInfo && h("p", {
                style: {
                  color: statusColor,
                  fontSize: "0.85rem",
                  marginTop: "10px"
                }
              }, refreshInfo.message)
            );
          })
        )
      );
    }

    function renderIntegracion() {
      const selectedClient = result && result.payload ? result.payload : result;

      if (!selectedClient) {
        return h("div", { className: "container py-lg" },
          h("div", { className: "card", style: { textAlign: 'center' } },
            h("h2", null, "No hay ningún bot seleccionado"),
            h("p", { style: { marginBottom: '20px' } }, "Para ver el código de integración, primero debes crear un bot o seleccionarlo desde tu panel."),
            h("button", { className: "btn btn-primary", onClick: () => navigateTo('registro') }, "Ir a Crear Bot")
          )
        );
      }

      const currentClientId = selectedClient.id || selectedClient.client_id || "TU_CLIENT_ID";
      const companyName = selectedClient.company_name || "Tu empresa";
      const minimalScriptCode = `<script \n  src="${API_BASE_URL}/static/noctua-widget.js" \n  data-client-id="${currentClientId}"\n><\/script>`;
      const advancedScriptCode = buildWidgetSnippet({
        apiBase: API_BASE_URL,
        clientId: currentClientId,
        companyName: companyName,
        widgetDefaults: widgetConfig,
      }, true);

      const colorFields = [
        { key: "color_primary", label: "Color primario" },
        { key: "color_secondary", label: "Color secundario" },
        { key: "color_panel", label: "Fondo panel" },
        { key: "color_text", label: "Texto panel" },
        { key: "color_input_bg", label: "Fondo input" },
        { key: "color_input_text", label: "Texto input" },
        { key: "color_input_border", label: "Borde input" },
        { key: "color_user_bubble_bg", label: "Burbuja usuario" },
        { key: "color_user_bubble_text", label: "Texto usuario" },
        { key: "color_bot_bubble_bg", label: "Burbuja bot" },
        { key: "color_bot_bubble_text", label: "Texto bot" },
      ];

      return h("div", { className: "container py-lg" },
        h("div", { className: "card" },
          h("h2", null, "¡Tu chatbot está listo!"),
          h("p", { style: { marginBottom: "20px" } }, "Copia este código en el <body> de tu web:"),
          h("div", { className: "code-window" },
            h("pre", { className: "code" }, h("code", null, minimalScriptCode))
          ),
          h("div", { style: { display: "flex", gap: "12px", flexWrap: "wrap" } },
            h("button", {
              className: "btn btn-primary",
              onClick: () => {
                navigator.clipboard.writeText(minimalScriptCode);
                alert("Código copiado");
              }
            }, "Copiar Código"),
            h("button", {
              className: "btn btn-ghost",
              onClick: () => setWidgetConfig(cloneWidgetDefaults())
            }, "Reset estilos")
          ),

          h("div", { style: { marginTop: "28px" } },
            h("h3", null, "Personaliza el widget"),
            h("p", { style: { color: "var(--text-secondary)", marginTop: "6px" } },
              "Ajusta textos, posicion, icono, colores y tamano. El snippet avanzado se actualiza automaticamente."
            )
          ),

          h("div", { className: "form", style: { marginTop: "18px" } },
            h("label", null, "Titulo", h("input", {
              value: widgetConfig.title,
              onChange: (e) => updateWidgetConfig("title", e.target.value)
            })),
            h("label", null, "Mensaje de bienvenida", h("input", {
              value: widgetConfig.welcome_message,
              onChange: (e) => updateWidgetConfig("welcome_message", e.target.value),
              placeholder: "Deja vacio para usar el mensaje por defecto"
            })),
            h("label", null, "Placeholder del input", h("input", {
              value: widgetConfig.placeholder,
              onChange: (e) => updateWidgetConfig("placeholder", e.target.value)
            })),
            h("label", null, "Texto del boton", h("input", {
              value: widgetConfig.send_label,
              onChange: (e) => updateWidgetConfig("send_label", e.target.value)
            })),
            h("label", null, "Posicion del launcher", h("select", {
              value: widgetConfig.position,
              onChange: (e) => updateWidgetConfig("position", e.target.value),
              style: { padding: "14px 16px", borderRadius: "var(--radius-md)", background: "var(--bg-primary)", color: "var(--text-primary)", border: "1px solid var(--border-light)" }
            },
              h("option", { value: "right" }, "Derecha"),
              h("option", { value: "left" }, "Izquierda")
            )),
            h("label", null, "Icono del launcher", h("input", {
              value: widgetConfig.icon,
              onChange: (e) => updateWidgetConfig("icon", e.target.value),
              placeholder: "Ej: 💬"
            })),
            h("div", {
              style: {
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px"
              }
            },
              colorFields.map(function (field) {
                return h("label", { key: field.key }, field.label, h("input", {
                  type: "color",
                  value: widgetConfig[field.key],
                  onChange: (e) => updateWidgetConfig(field.key, e.target.value),
                  style: { width: "100%", height: "44px", padding: "0", borderRadius: "var(--radius-md)", border: "1px solid var(--border-light)", background: "transparent" }
                }));
              })
            ),
            h("div", {
              style: {
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px"
              }
            },
              h("label", null, "Ancho del panel (px)", h("input", {
                type: "number",
                value: widgetConfig.panel_width,
                onChange: (e) => updateWidgetConfig("panel_width", e.target.value),
                min: 300,
                max: 520
              })),
              h("label", null, "Alto del panel (px)", h("input", {
                type: "number",
                value: widgetConfig.panel_height,
                onChange: (e) => updateWidgetConfig("panel_height", e.target.value),
                min: 420,
                max: 760
              }))
            )
          ),

          h("div", { style: { marginTop: "26px" } },
            h("h3", null, "Snippet avanzado"),
            h("p", { style: { color: "var(--text-secondary)", marginBottom: "12px" } },
              "Copia este snippet si quieres mantener la configuracion personalizada."
            ),
            h("div", { className: "code-window" },
              h("pre", { className: "code" }, h("code", null, advancedScriptCode))
            ),
            h("button", {
              className: "btn btn-primary",
              onClick: () => {
                navigator.clipboard.writeText(advancedScriptCode);
                alert("Snippet avanzado copiado");
              }
            }, "Copiar snippet avanzado")
          )
        )
      );
    }

    // ─── RENDER PRINCIPAL ───────────────────────────────────────────────────

    const navItems = [
      { key: "inicio", label: "Inicio" },
      { key: "funcionalidades", label: "Funcionalidades" },
      { key: "demo", label: "Demo Live" },
      { key: "registro", label: "Generar Grafo" },
    ];
    if (user) {
      navItems.push({ key: "dashboard", label: "Dashboard" });
    } else {
      navItems.push({ key: "login", label: "Entrar" });
    }

    return h("div", { className: "page" },
      h("nav", { className: "topbar" },
        h("button", { className: "brand", onClick: () => navigateTo("inicio") }, "Noctua"),
        h("div", { className: "menu" },
          navItems.map(function (item) {
            return h("button", {
              key: item.key,
              className: "menu-item " + (page === item.key ? "active" : ""),
              onClick: () => navigateTo(item.key)
            }, item.label);
          }),
          user && h("button", { className: "menu-item", style: { color: "#ff5f56" }, onClick: logout }, "Salir")
        )
      ),
      h("main", { className: "main" },
        page === "dashboard"      ? renderDashboard() :
        page === "login"          ? renderLoginForm() :
        page === "signup"         ? renderSignupForm() :
        page === "registro"       ? renderRegistro() :
        // FIX: usar h(DemoPage) en lugar de renderDemo()
        // Esto garantiza que React trate DemoPage como un componente real,
        // permitiendo el uso de useEffect dentro de él.
        page === "demo"           ? h(DemoPage) :
        page === "integracion"    ? renderIntegracion() :
        page === "funcionalidades"? renderFuncionalidades() :
        renderInicio()
      )
    );
  } // Cierre App

  const rootElement = document.getElementById("root");
  if (rootElement) {
    ReactDOM.createRoot(rootElement).render(h(App));
  }
})();