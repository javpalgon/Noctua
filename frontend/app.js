(function () {
  const { useMemo, useState, useEffect } = React;
  const h = React.createElement;

  const API_BASE_URL =
    (window.NOCTUA_CONFIG && window.NOCTUA_CONFIG.apiBaseUrl) ||
    "http://localhost:8000";

  const INITIAL_FORM = {
    company_name: "",
    url_portal: "",
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

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
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
        return `  ${key}=\"${val}\"`;
      })
      .join("\n");

    return `<script\n  src=\"${scriptSrc}\"\n${attributesBlock}\n  defer\n></script>`;
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

  function App() {
    const [page, setPage] = useState(getPageFromUrl());
    const [form, setForm] = useState(INITIAL_FORM);
    const [createdClient, setCreatedClient] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    // Sync state with URL history
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

    function navigateTo(nextPage) {
      const nextUrl = withPageInUrl(nextPage);
      if (window.navigation && typeof window.navigation.navigate === "function") {
        window.navigation.navigate(nextUrl);
      } else {
        window.history.pushState({}, "", nextUrl);
      }
      setPage(nextPage);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    const ctaText = useMemo(function () {
      return loading ? "Generando conocimiento..." : "Desplegar asistente";
    }, [loading]);

    function onFormChange(event) {
      const name = event.target.name;
      const value = event.target.value;
      setForm(function (prev) {
        return Object.assign({}, prev, { [name]: value });
      });
    }

    async function onSubmit(event) {
      event.preventDefault();
      setLoading(true);
      setResult(null);
      try {
        const response = await fetch(API_BASE_URL + "/clientes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        const payload = await response.json();
        if (!response.ok) {
          const errorText = payload?.detail ? (typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail)) : "Fallo al crear el asistente";
          throw new Error(errorText);
        }
        setCreatedClient(payload);
        setResult({ type: "success", payload: payload });
        setForm(INITIAL_FORM);
        setTimeout(() => navigateTo("integracion"), 3000);
      } catch (error) {
        setResult({ type: "error", message: error?.message || "Error inesperado" });
      } finally {
        setLoading(false);
      }
    }

    const navItems = [
      { key: "inicio", label: "Inicio" },
      { key: "funcionalidades", label: "Funcionalidades" },
      { key: "demo", label: "Demo Live" },
      { key: "registro", label: "Comenzar" },
      { key: "integracion", label: "Integrar" },
    ];

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
            h("button", { className: "btn btn-primary", onClick: () => navigateTo("registro") }, "Probar gratis"),
            h("button", { className: "btn btn-ghost", onClick: () => navigateTo("funcionalidades") }, "Descubrir más")
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
            h("p", null, "Noctua emplea GraphRAG avanzado (Grafos de Conocimiento) para entender relaciones complejas en tus datos, logrando un 99% de precisión evitando alucinaciones comerciales.")
          ),
          h(
            "div",
            { className: "bento-card bento-hover-secondary" },
            h("h3", null, "Rendimiento Global"),
            h("p", null, "Memoria basada en Redis, escalabilidad masiva y latencia Ultra Baja para tus clientes, en cualquier lugar.")
          ),
          h(
            "div",
            { className: "bento-card bento-hover-accent" },
            h("h3", null, "Seguridad B2B"),
            h("p", null, "Garantía de limitación de contexto. Noctua jamás derivará a la competencia si no cuenta con la solución.")
          ),
          h(
            "div",
            { className: "bento-card bento-large bento-hover-accent" },
            h("h3", null, "Integración Sin Fricción"),
            h("p", null, "Simplemente copia y pega nuestro widget embebido. En menos de 2 minutos tu web pasará de estática a interactiva y cognitiva con cero configuración.")
          )
        )
      );
    }

    function renderRegistro() {
      return h(
        "div",
        { className: "animate-enter form-container" },
        h(
          "div",
          { className: "form-header" },
          h("h2", null, "Únete al futuro."),
          h("p", null, "Ingresa tu web y generaremos tu chatbot. La personalizacion visual se hace luego en el script del widget.")
        ),
        h(
          "form",
          { className: "form", onSubmit: onSubmit },
          h(
            "label",
            null,
            "Nombre de la empresa",
            h("input", {
              name: "company_name",
              value: form.company_name,
              onChange: onFormChange,
              required: true,
              placeholder: "Ej: VentaCorp SL"
            })
          ),
          h(
            "label",
            null,
            "URL de Procesamiento (Web o Data)",
            h("input", {
              type: "url",
              name: "url_portal",
              value: form.url_portal,
              onChange: onFormChange,
              required: true,
              placeholder: "https://tudominio.com"
            })
          ),
          h(
            "button",
            { type: "submit", className: "btn btn-primary", disabled: loading },
            loading
              ? h(React.Fragment, null, h("span", { className: "loader", style: { marginRight: "10px" } }), ctaText)
              : ctaText
          )
        ),
        result &&
          h(
            "div",
            { className: "alert alert-" + result.type, style: { marginTop: "24px" } },
            result.type === "success"
              ? "¡Exito! Asistente generado (Client ID: " + result.payload.id + "). Redirigiendo a la integracion..."
              : "Error: " + result.message
          )
      );
    }

    function renderIntegracion() {
      const currentClientId = createdClient?.id || "TU_CLIENT_ID";
      const currentCompanyName = createdClient?.company_name || form.company_name || "Tu empresa";
      const minimalScriptCode = buildWidgetSnippet({
        apiBase: API_BASE_URL,
        clientId: currentClientId,
        companyName: currentCompanyName,
      });

      const advancedScriptCode = buildWidgetSnippet(
        {
          apiBase: API_BASE_URL,
          clientId: currentClientId,
          companyName: currentCompanyName,
          widgetDefaults: WIDGET_STYLE_DEFAULTS,
        },
        true
      );
    
      return h(
        "div",
        { className: "animate-enter section", style: { maxWidth: "800px", margin: "0 auto" } },
        h("div", { className: "hero", style: { padding: "40px 20px" } },
          h("h1", { style: { fontSize: "2.5rem" } }, "Despliegue rápido."),
          h("p", null, "Copia el snippet minimo para integrar. Si quieres personalizar, usa el snippet avanzado editando atributos data-... en tu HTML.")
        ),
        h(
          "div",
          {
            style: {
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "12px",
              padding: "14px",
              color: "var(--text-secondary)",
              background: "rgba(255,255,255,0.02)",
              marginBottom: "16px",
              fontSize: "0.9rem",
            }
          },
          h("strong", { style: { color: "var(--text-primary)" } }, "Client ID activo: "),
          currentClientId
        ),
        h("h3", { style: { fontSize: "1.15rem", marginBottom: "8px" } }, "Snippet minimo (recomendado)"),
        h(
          "div",
          { className: "code-window" },
          h("div", { className: "code-header" },
            h("div", { className: "code-dot dot-red" }),
            h("div", { className: "code-dot dot-yellow" }),
            h("div", { className: "code-dot dot-green" })
          ),
          h("pre", { className: "code" }, 
            h("code", null, 
              h("span", { style: { opacity: 0.5 }}, "<!-- Inserte en su HTML -->\n"),
              h("span", { className: "code-highlight" }, minimalScriptCode)
            )
          )
        ),
        h("div", { style: { textAlign: "center", marginTop: "32px"} },
          h("button", { className: "btn btn-ghost", onClick: () => {
            navigator.clipboard.writeText(minimalScriptCode)
              .then(() => alert("Codigo copiado al portapapeles"))
              .catch(() => alert("No se pudo copiar automaticamente. Copialo manualmente."));
          }}, "Copiar snippet minimo")
        ),
        h("h3", { style: { fontSize: "1.15rem", marginTop: "28px", marginBottom: "8px" } }, "Snippet avanzado (personalizable)"),
        h(
          "p",
          { style: { color: "var(--text-secondary)", marginBottom: "10px" } },
          "Modifica colores, textos, icono, posicion y tamaño del panel directamente en los atributos del script."
        ),
        h(
          "div",
          { className: "code-window" },
          h("div", { className: "code-header" },
            h("div", { className: "code-dot dot-red" }),
            h("div", { className: "code-dot dot-yellow" }),
            h("div", { className: "code-dot dot-green" })
          ),
          h("pre", { className: "code" },
            h("code", null,
              h("span", { className: "code-highlight" }, advancedScriptCode)
            )
          )
        ),
        h("div", { style: { textAlign: "center", marginTop: "18px" } },
          h("button", { className: "btn btn-ghost", onClick: () => {
            navigator.clipboard.writeText(advancedScriptCode)
              .then(() => alert("Snippet avanzado copiado al portapapeles"))
              .catch(() => alert("No se pudo copiar automaticamente. Copialo manualmente."));
          }}, "Copiar snippet avanzado")
        )
      );
    }

    function renderDemo() {
      useEffect(function() {
        if (!document.getElementById("noctua-demo-script")) {
          const s2 = document.createElement("script");
          s2.src = "./widget/noctua-widget.js"; 
          s2.id = "noctua-demo-script";
          s2.dataset.apiBase = API_BASE_URL;
          s2.dataset.clientId = "ba6c6b9e-aab1-4617-bb96-d6d65ad37b73";
          s2.dataset.companyName = "Noctua";
          s2.dataset.title = "Noctua AI TFG Demo";
          s2.dataset.colorPrimary = "#00dfd8";
          s2.dataset.colorSecondary = "#4f46e5";
          s2.dataset.panelWidth = "460";
          s2.dataset.panelHeight = "600";
          s2.dataset.welcomeMessage = "¡Hola! Soy Noctua. Puedes preguntarme sobre el proyecto.";

          document.body.appendChild(s2);
        }
      }, []);

      return h(
        "div",
        { className: "animate-enter section" },
        h("div", { className: "hero", style: { padding: "40px 20px" } },
          h("h1", { style: { fontSize: "3rem", background: "linear-gradient(to right, #00dfd8, #4f46e5)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" } }, "Demo en directo"),
          h("p", null, "Interactúa con el asistente inteligente en la parte inferior derecha. Le hemos enseñado toda la información de este Trabajo de Fin de Grado.")
        ),
        h(
          "div",
          { className: "bento-card", style: { textAlign: "left", margin: "0 auto", maxWidth: "600px" } },
          h("h3", null, "Prueba el Chatbot"),
          h("p", null, "El widget ahora mismo conoce el contexto de Noctua, GraphRAG y sus características. Puedes hacerle preguntas como:"),
          h("ul", { style: { paddingLeft: "24px", paddingTop: "12px", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "8px" } },
            h("li", null, '"¿Qué es el proyecto Noctua y qué objetivos tiene?"'),
            h("li", null, '"¿Qué tecnologías usáis por detrás?"'),
            h("li", null, '"¿Cómo evitas las alucinaciones del LLM?"')
          )
        )
      );
    }

    return h(
      "div",
      { className: "page" },
      h(
        "nav",
        { className: "topbar" },
        h("button", { className: "brand", onClick: () => navigateTo("inicio") }, "Noctua"),
        h(
          "div",
          { className: "menu" },
          navItems.map(function (item) {
            return h(
              "button",
              {
                key: item.key,
                className: "menu-item " + (page === item.key ? "active" : ""),
                onClick: () => navigateTo(item.key),
              },
              item.label
            );
          })
        )
      ),
      h("main", { className: "main" }, 
        page === "funcionalidades" ? renderFuncionalidades() :
        page === "registro" ? renderRegistro() :
        page === "demo" ? renderDemo() :
        page === "integracion" ? renderIntegracion() :
        renderInicio()
      )
    );
  }

  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(h(App));
})();
