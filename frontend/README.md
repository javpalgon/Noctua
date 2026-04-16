# Frontend Noctua (sin Vite, sin JSX)

Este frontend usa:
- `index.html`
- `app.js` (React con `React.createElement`, sin JSX)
- `styles.css`
- React/ReactDOM desde CDN.

## Ejecutar en local

Desde la raíz del proyecto:

```bash
cd /home/javi/Escritorio/TFG/Noctua/frontend
python3 -m http.server 3000
```

Abrir en navegador:

- http://localhost:3000/index.html

## Configuración de API

Edita en `index.html`:

```html
<script>
  window.NOCTUA_CONFIG = {
    apiBaseUrl: "http://localhost:8000",
  };
</script>
```

Asegúrate de tener levantada la API de FastAPI en ese host/puerto y CORS habilitado para `http://localhost:3000`.
