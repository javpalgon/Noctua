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

    function onChange(event) {
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
          h("p", null, "Ingresa tu web y crearemos tu grafo de conocimiento.")
        ),
        h(
          "form",
          { className: "form", onSubmit: onSubmit },
          h(
            "label",
            null,
            "Nombre de la Eempresa",
            h("input", {
              name: "company_name",
              value: form.company_name,
              onChange: onChange,
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
              onChange: onChange,
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
              ? "¡Exito! Asistente generado (Client ID: " + result.payload.client_id + "). Redirigiendo..."
              : "Error: " + result.message
          )
      );
    }

    function renderIntegracion() {
      const scriptCode = "<script>\n  window.NOCTUA_CLIENT_ID = \"TU_CLIENT_ID\";\n</script>\n<script src=\"http://localhost:5500/widget/noctua-widget.js\" defer></script>";
    
      return h(
        "div",
        { className: "animate-enter section", style: { maxWidth: "800px", margin: "0 auto" } },
        h("div", { className: "hero", style: { padding: "40px 20px" } },
          h("h1", { style: { fontSize: "2.5rem" } }, "Despliegue rápido."),
          h("p", null, "Copia el siguiente fragmento de código Justo antes de cerrar la etiqueta </body> en tu web.")
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
              h("span", { style: { opacity: 0.5 }}, "<!-- Inserte en su HTML -->\n"),
              h("span", { className: "code-highlight" }, scriptCode)
            )
          )
        ),
        h("div", { style: { textAlign: "center", marginTop: "32px"} },
          h("button", { className: "btn btn-ghost", onClick: () => {
            navigator.clipboard.writeText(scriptCode);
            alert("Código copiado al portapapeles");
          }}, "Copiar al portapapeles")
        )
      );
    }

    function renderDemo() {
      useEffect(function() {
        if (!document.getElementById("noctua-demo-script")) {
          const s1 = document.createElement("script");
          s1.innerHTML = "window.NOCTUA_CLIENT_ID = 'demo_noctua'; window.NOCTUA_COMPANY_NAME = 'Noctua'; window.NOCTUA_TITLE = 'Asistente Noctua'; window.NOCTUA_COLOR = '#00dfd8';";
          s1.id = "noctua-demo-config";
          document.body.appendChild(s1);
          
          const s2 = document.createElement("script");
          s2.src = "../widget/noctua-widget.js"; 
          s2.id = "noctua-demo-script";
          s2.dataset.apiBase = API_BASE_URL;
          s2.dataset.clientId = "demo_noctua";
          s2.dataset.companyName = "Proyecto Noctua TFG";
          s2.dataset.title = "Noctua AI TFG Demo";
          s2.dataset.color = "#00dfd8";

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
          h("div", { className: "feature-icon" }, "👀"),
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
