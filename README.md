# 🎬 Video QA Tester (Python)

**Automated QA testing for YouTube — genera vistas reales en tus propios videos.**

## ✨ Features

- **Login + sesión persistente** — Loguéate una vez, el sistema guarda las cookies
- **Reproducción real** — Video.play() + 45s de watch time para contar vistas
- **Anti-detección** — Elimina navegator.webdriver, plugins, chrome.runtime falso
- **Multi-instancia** — Corre N sesiones simultáneas
- **Docker** — Aislamiento por contenedor
- **Debug** — Screenshots, estado del player, errores de consola

## 🚀 Quick Start (Guía paso a paso)

### 0. Setup
```bash
# En el dev-vps
cd /home/ubuntu/video-qa-tester
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
```

### 1. Crear cuenta Google de testing

Hazlo en tu navegador normal (NO en el servidor):
1. Ve a https://accounts.google.com/SignUp
2. Crea una cuenta nueva (ej: `micanal.testing.1@gmail.com`)
3. Pon tu celular para verificar
4. Ve a YouTube, suscríbete a tu canal, da like a un video

Guarda el email y contraseña.

### 2. Login en nuestro sistema

```bash
# En el dev-vps, edita las credenciales:
nano .yt-credentials.json

# Pon tu email y contraseña ahí
# Luego ejecuta (se abrirá Chrome visible):
python3 scripts/auto_login.py
```

Te aparecerá Chrome, Google hará login automáticamente.
Si pide 2FA/captcha, resuélvelo manualmente.
**Las cookies se guardan automáticamente.**

### 3. Probar reproducción

```bash
# Con sesión guardada, prueba un video:
python3 -m videoqa.cli.main test "https://www.youtube.com/watch?v=Wf_q_N7GmGQ" --watch-time 45
```

### 4. Múltiples instancias

```bash
# 10 sesiones viendo el mismo video:
python3 -m videoqa.cli.main test "https://www.youtube.com/watch?v=Wf_q_N7GmGQ" --count 10 --watch-time 45
```

## 📋 Comandos

| Comando | Descripción |
|---------|-------------|
| `test <url>` | Reproduce un video (single o multi-instancia) |
| `scan <channel>` | Descubre videos de un canal |
| `debug <url>` | Debug detallado del player |
| `inject <url>` | Modo interceptor de API (experimental) |

## 🔬 Qué hace el sistema

1. **Navega** al video en YouTube
2. **Click** en el player
3. **video.play()** con muted=true
4. **Espera 45s** (umbral de vista de YouTube)
5. **Verifica** que el tiempo avance
6. **Guarda** las cookies para reuso

## 📁 Estructura

```
videoqa/
├── core/
│   ├── browser.py      # Browser anti-detección + sesiones
│   ├── interceptor.py  # Interceptor de API YouTube
│   └── types.py
├── cli/
│   └── main.py         # Todos los comandos
scripts/
├── auto_login.py       # Login automático con guardado de sesión
├── proxy-rotator/      # Rotador de proxies en Rust
```

## 🔧 Requisitos

- Python 3.11+
- Playwright + Chromium
- **Cuenta Google** (para bypassear LOGIN_REQUIRED)
- Docker (para multi-instancia aislada)
