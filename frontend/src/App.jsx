import { useMemo, useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const INITIAL_FORM = {
  company_name: '',
  url_portal: '',
};

export default function App() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const ctaText = useMemo(() => {
    if (loading) return 'Creando cliente...';
    return 'Crear mi asistente';
  }, [loading]);

  const onChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/clientes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(form),
      });

      const payload = await response.json();

      if (!response.ok) {
        const errorText = payload?.detail
          ? typeof payload.detail === 'string'
            ? payload.detail
            : JSON.stringify(payload.detail)
          : 'No se pudo crear el cliente';
        throw new Error(errorText);
      }

      setResult({ type: 'success', payload });
      setForm(INITIAL_FORM);
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Error inesperado' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div className="badge">Noctua</div>
        <h1>Tu web convertida en un asistente que vende por ti</h1>
        <p>
          Noctua rastrea el contenido de tu negocio, crea un grafo de conocimiento y despliega
          un chatbot que responde con contexto real de tu marca.
        </p>
        <div className="hero-actions">
          <a href="#registro" className="btn btn-primary">Empezar ahora</a>
          <a href="#como-funciona" className="btn btn-ghost">Cómo funciona</a>
        </div>
      </header>

      <section id="como-funciona" className="section">
        <h2>Cómo funciona Noctua</h2>
        <div className="grid">
          <article className="card">
            <h3>1. Conecta tu web</h3>
            <p>Nos pasas la URL y Noctua analiza tu contenido para crear la base de conocimiento.</p>
          </article>
          <article className="card">
            <h3>2. Generamos tu grafo</h3>
            <p>Construimos relaciones entre conceptos y productos para respuestas más precisas.</p>
          </article>
          <article className="card">
            <h3>3. Activa tu widget</h3>
            <p>Integra el chat en tu portal y empieza a atender usuarios con contexto de tu negocio.</p>
          </article>
        </div>
      </section>

      <section id="registro" className="section section-form">
        <div className="form-header">
          <h2>Registra tu negocio</h2>
          <p>Introduce los datos básicos para crear tu cliente y lanzar la generación de conocimiento.</p>
        </div>

        <form className="form" onSubmit={onSubmit}>
          <label>
            Nombre de empresa
            <input
              name="company_name"
              value={form.company_name}
              onChange={onChange}
              placeholder="Ej: Nike España"
              required
            />
          </label>

          <label>
            URL del portal
            <input
              type="url"
              name="url_portal"
              value={form.url_portal}
              onChange={onChange}
              placeholder="https://www.tudominio.com"
              required
            />
          </label>

          <button className="btn btn-primary" type="submit" disabled={loading}>
            {ctaText}
          </button>
        </form>

        {result?.type === 'success' && (
          <div className="alert alert-success">
            <strong>✅ Cliente creado:</strong>
            <div>ID: {result.payload.id}</div>
            <div>Empresa: {result.payload.company_name}</div>
            <div>URL: {result.payload.url_portal}</div>
            <div>{result.payload.message}</div>
          </div>
        )}

        {result?.type === 'error' && (
          <div className="alert alert-error">
            <strong>❌ Error:</strong> {result.message}
          </div>
        )}
      </section>

      <footer className="footer">
        <p>Noctua · Chatbots B2B con memoria y conocimiento real de tu web.</p>
      </footer>
    </div>
  );
}
