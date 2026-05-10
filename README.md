# 🎬 Video QA Tester — Sistema Completo

**QA automation para YouTube. Genera vistas reales en tus propios videos usando sesiones autenticadas.**

## ✨ Features

| Feature | Descripción |
|---------|-------------|
| 🎬 **Reproducción real** | Navega, hace clic, reproduce 45s+ — cuenta vistas reales |
| 🔑 **Sesiones autenticadas** | Cookies de YouTube reales → bypassea LOGIN_REQUIRED |
| 👥 **Multi-sesión** | Cada perfil = un "usuario" diferente con sus cookies |
| 📡 **Channel Scanner** | Encuentra videos ordenados por popularidad |
| 📊 **Distribuidor** | Asigna N vistas entre los Top M videos |
| 🛡️ **Anti-detección** | Elimina webdriver, plugins falsos, perfiles persistentes |
| 🔍 **Debug** | Screenshots, estado del player, playability status |

## 🚀 WORKFLOW COMPLETO

### 1. Setup inicial (una vez)

```bash
# En el servidor (dev-vps)
cd /home/ubuntu/video-qa-tester
source .venv/bin/activate

# Verificar
python3 -m videoqa.cli.main --help
```

### 2. Exportar cookies frescas desde tu PC

En tu **PC Linux donde tienes Chrome con sesión de YouTube**:

```bash
pip install playwright
python3 -m playwright install chromium

cat > export_cookies.py << 'EOF'
import asyncio
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="chrome")
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.youtube.com")
    input("¿Logueado en YouTube? Presiona Enter...")
    
    cookies = context.cookies()
    with open("cookies_frescas.txt", "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            f.write(f"{c['domain']}\tTRUE\t{c['path']}\t{'TRUE' if c['secure'] else 'FALSE'}\t{int(c.get('expires', 0))}\t{c['name']}\t{c['value']}\n")
    
    print(f"✅ {len(cookies)} cookies exportadas a cookies_frescas.txt")
    browser.close()
EOF

python3 export_cookies.txt
# → Se abre Chrome, ve a YouTube (debe estar logueado)
# → Enter en terminal
# → Se genera cookies_frescas.txt
```

### 3. Subir cookies al servidor

```bash
# En tu PC:
scp cookies_frescas.txt ubuntu@18.213.174.229:~/video-qa-tester/
```

### 4. Importar sesión en el servidor

```bash
# En el dev-vps:
cd video-qa-tester
source .venv/bin/activate

# Importar como sesión
python3 -m videoqa.cli.main sessions import-cookies cookies_frescas.txt

# Verificar
python3 -m videoqa.cli.main sessions list
```

### 5. Probar reproducción

```bash
# Test básico — un solo video
python3 -m videoqa.cli.main test "https://www.youtube.com/watch?v=Wf_q_N7GmGQ" --watch-time 45
```

### 6. Escanear canal + distribuir vistas

```bash
# Escanear canal (top 20 videos por popularidad)
python3 -m videoqa.cli.main scan "@elpepe8659"

# Distribuir 20 vistas entre los top 10 videos
python3 -m videoqa.cli.main distribute "@elpepe8659" --views 20 --top 10
```

## 📋 COMANDOS

| Comando | Descripción |
|---------|-------------|
| `test <url>` | Reproduce un video (single) |
| `scan <channel>` | Escanea canal, muestra top videos |
| `distribute <channel>` | Distribuye N vistas entre top videos |
| `sessions list` | Lista sesiones disponibles |
| `sessions import-cookies <file>` | Importa cookies |
| `sessions import-batch --pattern` | Importa múltiples archivos |
| `debug <url>` | Debug detallado del player |
| `login` | Login interactivo |

## 🔬 ARQUITECTURA

```
cookies_frescas.txt  →  sessions import-cookies  →  profiles/session-N/cookies.json
                                                          ↓
scan @channel  →  top_videos.json  →  distribute --views 20  →  cada sesión ve 1 video
```

Cada sesión (cookies) = 1 usuario diferente.
Cada usuario ve 1 video por 45s.
Con 20 sesiones y 10 videos = 20 vistas distribuidas naturalmente.

## 🛡️ ANTI-DETECCIÓN

- `navigator.webdriver` → `undefined`
- `navigator.plugins` → array realista (PDF, PDF Viewer, Native Client)
- `window.chrome` → objeto runtime completo
- Canvas fingerprint → consistente por sesión
- Perfil persistente → historial, cookies, localStorage
- User-Agent rotatorio por sesión
- Viewport aleatorio por sesión
- Timezone/locale aleatorio

## 🔧 SOLUCIÓN DE PROBLEMAS

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `LOGIN_REQUIRED` | Cookies expiradas | Exportar cookies frescas |
| `Time: 0.0s` | Stream no cargado | Verificar sesión o esperar |
| `networkState: Empty` | IP bloqueada | Usar cuenta autenticada |
| No views in Studio | Watch time < 30s | Usar --watch-time 45 |

## 📂 ESTRUCTURA

```
video-qa-tester/
├── videoqa/
│   ├── core/
│   │   ├── browser.py          # Browser anti-detección + sesiones
│   │   ├── session_manager.py  # Gestor multi-sesión + distribuidor
│   │   ├── interceptor.py      # Interceptor API (experimental)
│   │   └── types.py
│   └── cli/
│       └── main.py             # Todos los comandos CLI
├── profiles/                   # Sesiones guardadas (gitignored)
│   └── session-N/
│       └── cookies.json
├── scripts/
│   └── auto_login.py
├── requirements.txt
└── README.md
```

## 📊 MÉTRICAS ESPERADAS

| Recurso | Por sesión | 20 sesiones | 50 sesiones |
|---------|-----------|-------------|-------------|
| RAM | ~300MB | ~6GB | ~15GB |
| Tiempo/vista | ~60s | ~60s total | ~60s total |
| Vistas/minuto | 1 | 20 | 50 |
| IPs | 1 | 1-20* | 1-50* |

*Con múltiples proxies
