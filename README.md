# QR TRAP — plataforma web

Simulación educativa de ingeniería social (quishing) · IS811 Seguridad Informática · UNAH Campus Comayagua.

Incluye: generador de QR, página educativa + formulario anónimo, registro anónimo de eventos, base de datos y panel de resultados protegido por clave.

## Probar en tu computadora (2 minutos)
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Abre http://localhost:5000 → clave de prueba: `qrtrap-dev`.
En el panel pulsa **Cargar datos de demostración** para ensayar la presentación (luego **Borrar demostración**).

## Publicar en Render (gratis, sin tarjeta)
1. Sube esta carpeta a un repositorio de GitHub.
2. En render.com: **New → Blueprint** y elige el repositorio (usa `render.yaml`).
3. Cuando lo pida, escribe tu `ADMIN_PASSWORD` (clave larga). `SECRET_KEY` se genera sola.
4. Al terminar tendrás una URL `https://qr-trap-xxxx.onrender.com`. Entra a `/admin`.
5. En **Códigos QR** pega esa URL y descarga/imprime los códigos.

**Importante – persistencia:** en el plan gratuito el disco se borra al reiniciar, así que SQLite perdería datos.
Solución sencilla: crea una base PostgreSQL gratuita (Render o Neon/Supabase) y pon su cadena en la variable `DATABASE_URL`; la app la usa sola. Sin `DATABASE_URL` usa SQLite (`data/qrtrap.db`), ideal para pruebas o un servidor propio/VPS.

Otras opciones: Railway, Fly.io, PythonAnywhere o cualquier VPS con `gunicorn app:app` (ver `Procfile`).

## Variables de entorno
| Variable | Uso |
|---|---|
| `APP_ENV=production` | Activa cookies seguras y exige las dos variables siguientes |
| `ADMIN_PASSWORD` | Clave del panel |
| `SECRET_KEY` | Firma de sesiones y de tokens de visita |
| `DATABASE_URL` | (opcional) PostgreSQL |

## Rutas
- `/q/<curiosidad|utilidad|urgencia|informativa>` — destino del QR (explicación + formulario)
- `/admin` — panel · `/admin/qr` — generador/hoja imprimible · `/admin/export/eventos.csv`, `/admin/export/respuestas.csv`
- `/healthz` — comprobación de salud

## Privacidad y seguridad (para tu informe)
- No se guarda IP, user-agent, cookies ni texto libre; solo variante, tipo de evento, fecha/hora, id aleatorio y respuestas de selección.
- Los visitantes no usan cookies: cada visita lleva un token firmado y con vencimiento (24 h).
- Respuestas validadas contra una lista cerrada; una respuesta por visita.
- CSP estricta (sin scripts ni estilos en línea, sin recursos externos), X-Frame-Options, nosniff, Referrer-Policy, HSTS en producción.
- Login con comparación en tiempo constante, límite de intentos, CSRF y sesión HttpOnly/SameSite.
- Todo se sirve desde el propio servidor (Chart.js incluido): funciona sin internet externo.
- Listo para pasar OWASP ZAP y Nmap (solo contra tu propio servidor).

## Editar los mensajes
Los textos de las 4 estrategias y las preguntas están en `content.py`. Cámbialos cuando el docente y el coordinador aprueben el texto final, antes de imprimir.
