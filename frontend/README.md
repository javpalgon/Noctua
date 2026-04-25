# Frontend Noctua (sin Vite, sin JSX)

Este frontend usa:
- `index.html`
- `app.js` (React con `React.createElement`, sin JSX)
- `styles.css`
- React/ReactDOM desde CDN.

## Ejecutar en local

Este proyecto se ejecuta con `npm`, pero **sin Vite** y **sin JSX**.

```bash
cd /home/javi/Escritorio/TFG/Noctua/frontend
npm install
npm run dev
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

## Estado del proyecto (importante)

- ✅ Sin archivos `.jsx`
- ✅ Sin `vite.config.js`
- ✅ React cargado por CDN en `index.html`
- ✅ Lógica principal en `app.js` usando `React.createElement`
