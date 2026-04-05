import asyncio
import random
import sys
import math
import time
import gc
import os  # <-- ADICIONADO para ler variável de ambiente
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
import psutil
from typing import Dict, List, Optional
import logging
import subprocess
import traceback
import hashlib

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SITE_BASE = "https://cinecitoklkk.blogspot.com"

# ===== CONFIGURACAO DO NAVEGADOR (HÍBRIDO) =====
NAVEGADOR = "chromium"   # Opções: "chromium", "firefox"

# ===== OTIMIZACOES DE RAM =====
NUM_USUARIOS = 10
MAX_CONCURRENT_BROWSERS = 2
USUARIOS_POR_BROWSER = 5
MAX_RAM_MB = 1200
RAM_LIMITE_POR_BROWSER = 150

# ===== OTIMIZACOES ADICIONAIS =====
RESTART_BROWSER_AFTER_VISITS = 50
CLEANUP_INTERVAL = 300
MAX_CONTEXTS_PER_BROWSER = 4
GC_THRESHOLD = 500

gc.set_threshold(GC_THRESHOLD, GC_THRESHOLD // 10, GC_THRESHOLD // 10)

# ===== CONFIGURACOES PARA INTERACOES =====
TEMPO_MINIMO_PAGINA = 15
TEMPO_MAXIMO_PAGINA = 45
INTERACOES_POR_VISITA = 8

# ===== CONFIGURACOES DE TIMEOUT =====
TIMEOUT_NAVEGACAO = 15000
TIMEOUT_CARREGAMENTO = 20000
MAX_TENTATIVAS = 3
TIMEOUT_VISITA = 120

# ===== CONFIGURACAO DO PROXY CELULAR (via cloudflared) =====
# Defina o endereço público gerado pelo cloudflared no Termux.
# Exemplo: PROXY_URL = "http://scoop-lotus-quad-trademark.trycloudflare.com"
# Para desabilitar o proxy, deixe PROXY_URL = None
PROXY_URL = "http://scoop-lotus-quad-trademark.trycloudflare.com"  

# ================= FUNCAO BEZIER =================
def bezier(p0, p1, p2, p3, t):
    return (
        (1-t)**3 * p0 +
        3 * (1-t)**2 * t * p1 +
        3 * (1-t) * t**2 * p2 +
        t**3 * p3
    )

async def mover_mouse_humano(page, start, end):
    x0, y0 = start
    x3, y3 = end

    x1 = x0 + random.randint(-100, 100)
    y1 = y0 + random.randint(0, 150)

    x2 = x3 + random.randint(-100, 100)
    y2 = y3 + random.randint(0, 150)

    steps = random.randint(20, 35)

    for i in range(steps):
        t = i / steps
        x = bezier(x0, x1, x2, x3, t)
        y = bezier(y0, y1, y2, y3, t)

        try:
            await page.mouse.move(x, y)
        except:
            return

        await asyncio.sleep(random.uniform(0.01, 0.03))

# ================= SCRIPT ANTI-FINGERPRINT COMPLETO =================
def get_advanced_anti_fingerprint_script(browser_type):
    """Script anti-detecção avançado - compatível com Chromium e Firefox"""
    
    useragent_data_spoof = """
            // =============================================
            // 0. SPOOFING DE NAVIGATOR.USERAGENTDATA (SÓ CHROMIUM)
            // =============================================
            if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
                const originalGetHighEntropy = navigator.userAgentData.getHighEntropyValues;
                navigator.userAgentData.getHighEntropyValues = async function(hints) {
                    const ua = navigator.userAgent;
                    let platform = "Linux";
                    let platformVersion = "";
                    let architecture = "x86";
                    let bitness = "64";
                    let model = "";
                    let wow64 = false;
                    
                    if (ua.includes("Windows")) {
                        platform = "Windows";
                        platformVersion = "10.0.0";
                        wow64 = Math.random() > 0.7;
                    } else if (ua.includes("Mac OS X")) {
                        platform = "macOS";
                        platformVersion = "10.15.7";
                    } else if (ua.includes("Linux")) {
                        platform = "Linux";
                        platformVersion = "5.15.0";
                    }
                    
                    const brands = [
                        { brand: "Chromium", version: "120" },
                        { brand: "Google Chrome", version: "120" },
                        { brand: "Not=A?Brand", version: "99" }
                    ];
                    const fullVersionList = [
                        { brand: "Chromium", version: "120.0.0.0" },
                        { brand: "Google Chrome", version: "120.0.0.0" }
                    ];
                    
                    const fakeValues = {
                        architecture: architecture,
                        bitness: bitness,
                        brands: brands,
                        fullVersionList: fullVersionList,
                        model: model,
                        platform: platform,
                        platformVersion: platformVersion,
                        wow64: wow64,
                        uaFullVersion: "120.0.0.0"
                    };
                    
                    const result = {};
                    for (const hint of hints) {
                        if (fakeValues.hasOwnProperty(hint)) {
                            result[hint] = fakeValues[hint];
                        }
                    }
                    return Promise.resolve(result);
                };
            }
    """ if browser_type == "chromium" else "// Firefox não suporta userAgentData"
    
    return f"""
        (function() {{
            {useragent_data_spoof}
            
            // =============================================
            // 1. FORÇAR ABA VISÍVEL (EVITA DETECÇÃO HEADLESS)
            // =============================================
            Object.defineProperty(document, 'hidden', {{ get: () => false }});
            Object.defineProperty(document, 'visibilityState', {{ get: () => 'visible' }});
            Object.defineProperty(document, 'webkitHidden', {{ get: () => false }});
            Object.defineProperty(document, 'webkitVisibilityState', {{ get: () => 'visible' }});
            
            // =============================================
            // 2. HARDWARE E SISTEMA OPERACIONAL
            // =============================================
            
            var cpuCores = [4, 8, 12, 16][Math.floor(Math.random() * 4)];
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: function() {{ return cpuCores; }},
                configurable: true
            }});
            
            var deviceMemory = [4, 8, 16][Math.floor(Math.random() * 3)];
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: function() {{ return deviceMemory; }},
                configurable: true
            }});
            
            var maxTouchPoints = Math.random() > 0.8 ? 1 : 0;
            Object.defineProperty(navigator, 'maxTouchPoints', {{
                get: function() {{ return maxTouchPoints; }},
                configurable: true
            }});
            if (navigator.msMaxTouchPoints !== undefined) {{
                Object.defineProperty(navigator, 'msMaxTouchPoints', {{
                    get: function() {{ return maxTouchPoints; }},
                    configurable: true
                }});
            }}
            
            if (maxTouchPoints > 0) {{
                window.ontouchstart = function() {{}};
                document.ontouchstart = function() {{}};
                HTMLElement.prototype.ontouchstart = function() {{}};
            }}
            
            var isWin = navigator.userAgent.indexOf('Windows') > -1;
            var isMac = /Mac OS X/.test(navigator.userAgent);
            var isLinux = /Linux/.test(navigator.userAgent);
            var platform = isWin ? 'Win32' : (isMac ? 'MacIntel' : 'Linux x86_64');
            Object.defineProperty(navigator, 'platform', {{
                get: function() {{ return platform; }},
                configurable: true
            }});
            
            if (navigator.oscpu !== undefined) {{
                var oscpu = isWin ? 'Windows NT 10.0; Win64; x64' : (isMac ? 'Intel Mac OS X 10.15' : 'Linux x86_64');
                Object.defineProperty(navigator, 'oscpu', {{
                    get: function() {{ return oscpu; }},
                    configurable: true
                }});
            }}
            
            // =============================================
            // 3. NAVIGATOR PROPERTIES ESSENCIAIS
            // =============================================
            
            var isFirefox = navigator.userAgent.indexOf('Firefox') > -1;
            var productSub = isFirefox ? '20100101' : '20030107';
            Object.defineProperty(navigator, 'productSub', {{
                get: function() {{ return productSub; }},
                configurable: true
            }});
            
            var vendor = isFirefox ? '' : 'Google Inc.';
            Object.defineProperty(navigator, 'vendor', {{
                get: function() {{ return vendor; }},
                configurable: true
            }});
            
            Object.defineProperty(navigator, 'vendorSub', {{
                get: function() {{ return ''; }},
                configurable: true
            }});
            
            // =============================================
            // 4. REMOVER WEBDRIVER E AUTOMATION
            // =============================================
            
            Object.defineProperty(navigator, 'webdriver', {{
                get: function() {{ return undefined; }},
                configurable: true
            }});
            
            delete navigator.__proto__.webdriver;
            
            if (window.chrome && window.chrome.loadTimes) {{
                Object.defineProperty(window.chrome, 'loadTimes', {{
                    get: function() {{ return undefined; }},
                    configurable: true
                }});
            }}
            
            // =============================================
            // 5. PLUGINS E MIME TYPES REALISTAS
            // =============================================
            
            var pluginsList = [];
            var mimeTypesList = [];
            
            if (isFirefox) {{
                pluginsList = [
                    {{ name: "PDF Viewer", filename: "pdf.js", description: "Portable Document Format" }},
                    {{ name: "Shockwave Flash", filename: "libflashplayer.so", description: "Shockwave Flash 32.0 r0" }},
                    {{ name: "Widevine Content Decryption Module", filename: "libwidevinecdm.so", description: "Enables playback of encrypted media" }}
                ];
                mimeTypesList = [
                    {{ type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" }},
                    {{ type: "application/x-shockwave-flash", suffixes: "swf", description: "Shockwave Flash" }}
                ];
            }} else {{
                pluginsList = [
                    {{ name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format" }},
                    {{ name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: "" }},
                    {{ name: "Native Client", filename: "internal-nacl-plugin", description: "" }},
                    {{ name: "Widevine Content Decryption Module", filename: "widevinecdm", description: "Enables playback of encrypted media" }}
                ];
                mimeTypesList = [
                    {{ type: "application/pdf", suffixes: "pdf", description: "Portable Document Format" }},
                    {{ type: "text/pdf", suffixes: "pdf", description: "" }},
                    {{ type: "application/x-nacl", suffixes: "", description: "Native Client Executable" }},
                    {{ type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable" }}
                ];
            }}
            
            var pluginArray = [];
            for (var i = 0; i < pluginsList.length; i++) {{
                var plugin = {{
                    name: pluginsList[i].name,
                    filename: pluginsList[i].filename,
                    description: pluginsList[i].description,
                    length: 1,
                    item: function(idx) {{ return this[idx]; }},
                    namedItem: function(name) {{ return this[0]; }}
                }};
                plugin[0] = {{
                    type: "application/x-google-chrome-pdf",
                    suffixes: "pdf",
                    description: "Portable Document Format",
                    enabledPlugin: plugin
                }};
                pluginArray.push(plugin);
            }}
            Object.defineProperty(navigator, 'plugins', {{
                get: function() {{ return pluginArray; }},
                configurable: true
            }});
            
            var mimeArray = [];
            for (var i = 0; i < mimeTypesList.length; i++) {{
                mimeArray.push({{
                    type: mimeTypesList[i].type,
                    suffixes: mimeTypesList[i].suffixes,
                    description: mimeTypesList[i].description,
                    enabledPlugin: pluginArray[0]
                }});
            }}
            Object.defineProperty(navigator, 'mimeTypes', {{
                get: function() {{ return mimeArray; }},
                configurable: true
            }});
            
            // =============================================
            // 6. LINGUAS E TIMEZONE
            // =============================================
            
            var languages = ['pt-BR', 'pt', 'en-US', 'en'];
            Object.defineProperty(navigator, 'languages', {{
                get: function() {{ return languages; }},
                configurable: true
            }});
            Object.defineProperty(navigator, 'language', {{
                get: function() {{ return languages[0]; }},
                configurable: true
            }});
            
            var tzOffset = [180, 120, 240][Math.floor(Math.random() * 3)];
            Object.defineProperty(Date.prototype, 'getTimezoneOffset', {{
                value: function() {{ return tzOffset; }},
                configurable: true
            }});
            
            // =============================================
            // 7. PERMISSÕES E NOTIFICAÇÕES
            // =============================================
            
            if (navigator.permissions && navigator.permissions.query) {{
                var originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(params) {{
                    if (params.name === 'notifications') {{
                        return Promise.resolve({{ state: 'default', onchange: null }});
                    }}
                    return originalQuery.call(this, params);
                }};
            }}
            
            if (window.Notification) {{
                Object.defineProperty(Notification, 'permission', {{
                    get: function() {{ return 'default'; }},
                    configurable: true
                }});
                Object.defineProperty(Notification, 'requestPermission', {{
                    value: function(callback) {{ if (callback) callback('default'); return Promise.resolve('default'); }},
                    configurable: true
                }});
            }}
            
            // =============================================
            // 8. ORIENTAÇÃO E TELA
            // =============================================
            
            if (screen.orientation) {{
                var orientations = ['portrait-primary', 'landscape-primary'];
                Object.defineProperty(screen.orientation, 'type', {{
                    get: function() {{ return orientations[Math.floor(Math.random() * orientations.length)]; }},
                    configurable: true
                }});
                Object.defineProperty(screen.orientation, 'angle', {{
                    get: function() {{ return Math.random() > 0.5 ? 0 : 90; }},
                    configurable: true
                }});
            }}
            
            Object.defineProperty(window, 'orientation', {{
                get: function() {{ return screen.orientation.angle || 0; }},
                configurable: true
            }});
            
            Object.defineProperty(window, 'screenTop', {{
                get: function() {{ return 0; }},
                configurable: true
            }});
            Object.defineProperty(window, 'screenLeft', {{
                get: function() {{ return 0; }},
                configurable: true
            }});
            
            // =============================================
            // 9. BATERIA E CONEXÃO
            // =============================================
            
            if (navigator.getBattery) {{
                var originalGetBattery = navigator.getBattery;
                navigator.getBattery = function() {{
                    return originalGetBattery.call(this).then(function(battery) {{
                        Object.defineProperty(battery, 'level', {{
                            get: function() {{ return Math.random() * 0.6 + 0.3; }}
                        }});
                        Object.defineProperty(battery, 'charging', {{
                            get: function() {{ return Math.random() > 0.7; }}
                        }});
                        return battery;
                    }});
                }};
            }}
            
            if (navigator.connection) {{
                var connectionTypes = ['wifi', 'cellular', 'ethernet'];
                Object.defineProperty(navigator.connection, 'effectiveType', {{
                    get: function() {{ return connectionTypes[Math.floor(Math.random() * connectionTypes.length)]; }},
                    configurable: true
                }});
                Object.defineProperty(navigator.connection, 'rtt', {{
                    get: function() {{ return [50, 100, 150, 200][Math.floor(Math.random() * 4)]; }},
                    configurable: true
                }});
                Object.defineProperty(navigator.connection, 'downlink', {{
                    get: function() {{ return (Math.random() * 9 + 1).toFixed(1); }},
                    configurable: true
                }});
                Object.defineProperty(navigator.connection, 'saveData', {{
                    get: function() {{ return false; }},
                    configurable: true
                }});
            }}
            
            // =============================================
            // 10. CANVAS FINGERPRINT COM RUÍDO
            // =============================================
            
            var originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                if (this.width > 100 && this.height > 100) {{
                    var context = this.getContext('2d');
                    if (context) {{
                        var imageData = context.getImageData(0, 0, this.width, this.height);
                        for (var i = 0; i < imageData.data.length; i += 200) {{
                            imageData.data[i] = imageData.data[i] ^ (Math.random() * 3);
                        }}
                        context.putImageData(imageData, 0, 0);
                    }}
                }}
                return originalToDataURL.call(this, type, quality);
            }};
            
            var originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                if (param === 37445) {{
                    return isFirefox ? 'Intel Inc.' : 'Google Inc. (Intel)';
                }}
                if (param === 37446) {{
                    return isFirefox ? 'Intel Iris OpenGL Engine' : 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)';
                }}
                return originalGetParameter.call(this, param);
            }};
            
            // =============================================
            // 11. EVAL E FUNCTIONS
            // =============================================
            
            var nativeEval = window.eval;
            if (nativeEval.toString().length !== 33) {{
                window.eval = function() {{ return nativeEval.apply(this, arguments); }};
                Object.defineProperty(window.eval, 'toString', {{
                    value: function() {{ return 'function eval() {{ [native code] }}'; }},
                    configurable: true
                }});
            }}
            
            var nativeFunctionToString = Function.prototype.toString;
            Function.prototype.toString = function() {{
                if (this === window.eval) return 'function eval() {{ [native code] }}';
                return nativeFunctionToString.call(this);
            }};
            
            // =============================================
            // 12. DETECÇÃO DE DEVTOOLS
            // =============================================
            
            var originalOuterWidth = window.outerWidth;
            var originalInnerWidth = window.innerWidth;
            Object.defineProperty(window, 'outerWidth', {{
                get: function() {{ return originalOuterWidth; }},
                configurable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: function() {{ return window.outerHeight; }},
                configurable: true
            }});
            
            // =============================================
            // 13. REMOVER PROPRIEDADES DE AUTOMAÇÃO
            // =============================================
            
            delete window.__playwright__;
            delete window.__pw_manual;
            delete window.__webdriver_evaluate;
            delete window.__webdriver_script_function;
            delete window.__webdriver_script_func;
            delete window.__selenium_evaluate;
            delete window.__selenium_script_function;
            delete window.__webdriver_unwrapped;
            delete window.__webdriver_wrapped;
            delete window.__webdriver_script_fn;
            delete window.__driver_unwrapped;
            delete window.__driver_wrapped;
            delete window.__webdriver;
            delete window.__selenium;
            delete window.__webDriver;
            delete window.__webdriver_script_func;
            
            // =============================================
            // 14. SIMULAR DOCUMENT MODE
            // =============================================
            
            if (document.documentMode !== undefined) {{
                Object.defineProperty(document, 'documentMode', {{
                    get: function() {{ return undefined; }},
                    configurable: true
                }});
            }}
            
            // =============================================
            // 15. SIMULAR STORAGE
            // =============================================
            
            if (!window.localStorage) {{
                window.localStorage = {{
                    _data: {{}},
                    setItem: function(id, val) {{ this._data[id] = String(val); }},
                    getItem: function(id) {{ return this._data.hasOwnProperty(id) ? this._data[id] : null; }},
                    removeItem: function(id) {{ delete this._data[id]; }},
                    clear: function() {{ this._data = {{}}; }},
                    key: function(i) {{ return Object.keys(this._data)[i]; }},
                    get length() {{ return Object.keys(this._data).length; }}
                }};
            }}
            
            if (!window.sessionStorage) {{
                window.sessionStorage = {{
                    _data: {{}},
                    setItem: function(id, val) {{ this._data[id] = String(val); }},
                    getItem: function(id) {{ return this._data.hasOwnProperty(id) ? this._data[id] : null; }},
                    removeItem: function(id) {{ delete this._data[id]; }},
                    clear: function() {{ this._data = {{}}; }},
                    key: function(i) {{ return Object.keys(this._data)[i]; }},
                    get length() {{ return Object.keys(this._data).length; }}
                }};
            }}
            
            console.log('[Anti-fingerprint] All protections loaded for {browser_type} (tab visible forced)');
        }})();
    """

def get_anti_detection_script(browser_type):
    return get_advanced_anti_fingerprint_script(browser_type)


class MemoryOptimizer:
    def __init__(self, max_ram_mb):
        self.max_ram_mb = max_ram_mb
        self.last_cleanup = time.time()
        
    async def check_and_cleanup(self):
        try:
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            usage_percent = mem_mb / self.max_ram_mb
            if usage_percent > 0.85:
                logger.warning(f"RAM alta: {mem_mb:.0f}MB/{self.max_ram_mb}MB - Forcando limpeza")
                await self.force_cleanup()
                return True
        except:
            pass
        return False
    
    async def force_cleanup(self):
        try:
            gc.collect()
            gc.collect(2)
            try:
                if sys.platform.startswith('linux'):
                    libc = __import__('ctypes').CDLL("libc.so.6")
                    libc.malloc_trim(0)
            except:
                pass
            logger.info("Limpeza de memoria realizada")
        except Exception as e:
            logger.error(f"Erro na limpeza: {e}")
    
    async def periodic_cleanup(self):
        now = time.time()
        if now - self.last_cleanup > CLEANUP_INTERVAL:
            await self.check_and_cleanup()
            self.last_cleanup = now
    
    async def log_memory(self):
        try:
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            logger.debug(f"RAM: {mem_mb:.0f}MB")
        except:
            pass


class StatsTracker:
    def __init__(self):
        self.visitas = 0
        self.erros = 0
        self.popunders = 0
        self.timeouts = 0
        self.tempo_total = 0
        self.usuarios_ativos = 0
        self.ultimo_log = time.time()
        self._lock = asyncio.Lock()
        self.browser_restarts = 0
    
    async def increment_visitas(self):
        async with self._lock:
            self.visitas += 1
    async def increment_erros(self):
        async with self._lock:
            self.erros += 1
    async def increment_popunders(self):
        async with self._lock:
            self.popunders += 1
    async def increment_timeouts(self):
        async with self._lock:
            self.timeouts += 1
    async def add_tempo(self, segundos):
        async with self._lock:
            self.tempo_total += segundos
    async def add_usuario_ativo(self):
        async with self._lock:
            self.usuarios_ativos += 1
    async def remove_usuario_ativo(self):
        async with self._lock:
            self.usuarios_ativos -= 1
    async def increment_restarts(self):
        async with self._lock:
            self.browser_restarts += 1
    async def get_stats(self):
        async with self._lock:
            return {
                'visitas': self.visitas,
                'erros': self.erros,
                'popunders': self.popunders,
                'timeouts': self.timeouts,
                'tempo_total': self.tempo_total,
                'usuarios_ativos': self.usuarios_ativos,
                'browser_restarts': self.browser_restarts
            }
    async def log_stats_periodico(self, memory_optimizer):
        agora = time.time()
        if agora - self.ultimo_log >= 60:
            stats = await self.get_stats()
            await memory_optimizer.log_memory()
            try:
                process = psutil.Process()
                mem_mb = process.memory_info().rss / 1024 / 1024
            except:
                mem_mb = 0
            taxa_sucesso = (stats['visitas'] / (stats['visitas'] + stats['erros']) * 100) if (stats['visitas'] + stats['erros']) > 0 else 0
            media_tempo = stats['tempo_total'] / stats['visitas'] if stats['visitas'] > 0 else 0
            logger.info(f"\n{'='*60}")
            logger.info(f"ESTATISTICAS - {NAVEGADOR.upper()}")
            logger.info(f"   Visitas: {stats['visitas']}")
            logger.info(f"   Popunders: {stats['popunders']}")
            logger.info(f"   Usuarios ativos: {stats['usuarios_ativos']}")
            logger.info(f"   Reinicios: {stats['browser_restarts']}")
            logger.info(f"   Media por visita: {media_tempo:.1f}s")
            logger.info(f"   Taxa de sucesso: {taxa_sucesso:.1f}%")
            logger.info(f"   RAM: {mem_mb:.0f}MB / {MAX_RAM_MB}MB")
            logger.info(f"{'='*60}")
            self.ultimo_log = agora


class ScalableBrowserPool:
    def __init__(self, playwright, num_browsers=6, browser_type="chromium", stats_tracker=None):
        self.playwright = playwright
        self.num_browsers = num_browsers
        self.browser_type = browser_type
        self.stats_tracker = stats_tracker
        self.browsers = []
        self.browser_slots = {}
        self.browser_visits = {}
        self.slots_lock = asyncio.Lock()
        self.available_slots = asyncio.Queue()
        self.running = True
        
    async def initialize(self):
        logger.info(f"Criando {self.num_browsers} browsers {self.browser_type.upper()} (modo ECO)...")
        if self.browser_type == "chromium":
            launch_method = self.playwright.chromium.launch
            args = [
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--js-flags="--max-old-space-size=128"',
                '--memory-pressure-off',
                '--disable-http2',
                '--disable-logging',
                '--log-level=3',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI,BlinkGenPropertyTrees'
            ]
            extra_args = {'args': args}
        elif self.browser_type == "firefox":
            launch_method = self.playwright.firefox.launch
            extra_args = {
                'firefox_user_prefs': {
                    'browser.cache.disk.enable': False,
                    'browser.cache.memory.enable': False,
                    'browser.sessionhistory.max_entries': 3,
                    'dom.ipc.processCount': 1,
                    'javascript.options.mem.max': 64000,
                    'browser.tabs.remote.autostart': False,
                    'browser.tabs.remote.autostart.2': False,
                    'dom.disable_beforeunload': True,
                    'network.http.max-connections': 6,
                    'network.http.max-persistent-connections-per-server': 2
                }
            }
        else:
            raise ValueError(f"Navegador {self.browser_type} nao suportado")
        
        for i in range(self.num_browsers):
            try:
                browser = await launch_method(headless=True, **extra_args)
                self.browsers.append(browser)
                self.browser_slots[browser] = USUARIOS_POR_BROWSER
                self.browser_visits[browser] = 0
                for _ in range(USUARIOS_POR_BROWSER):
                    await self.available_slots.put(browser)
                logger.info(f"   Browser {i+1}/{self.num_browsers} criado (modo ECO)")
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Erro ao criar browser {i+1}: {e}")
                raise
        logger.info(f"Total: {len(self.browsers)} browsers {self.browser_type.upper()}")
    
    async def get_browser(self, usuario_id, attempt=0):
        max_attempts = 3
        try:
            browser = await asyncio.wait_for(self.available_slots.get(), timeout=30.0)
            async with self.slots_lock:
                if browser not in self.browser_slots:
                    logger.warning(f"U{usuario_id}: Browser obsoleto, pegando outro...")
                    await self.available_slots.put(browser)
                    await asyncio.sleep(0.5)
                    if attempt < max_attempts:
                        return await self.get_browser(usuario_id, attempt + 1)
                    else:
                        raise Exception("Max attempts reached")
                self.browser_slots[browser] -= 1
            return browser
        except asyncio.TimeoutError:
            logger.error(f"U{usuario_id}: Timeout aguardando browser")
            raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"U{usuario_id}: Erro ao obter browser: {e}")
            raise
    
    async def return_browser(self, browser, usuario_id):
        try:
            async with self.slots_lock:
                if browser not in self.browser_slots:
                    return
                self.browser_slots[browser] += 1
                self.browser_visits[browser] += 1
                if self.browser_visits[browser] >= RESTART_BROWSER_AFTER_VISITS:
                    logger.warning(f"Reiniciando browser U{usuario_id}")
                    try:
                        await browser.close()
                    except:
                        pass
                    if self.browser_type == "chromium":
                        new_browser = await self.playwright.chromium.launch(headless=True)
                    else:
                        new_browser = await self.playwright.firefox.launch(headless=True)
                    if browser in self.browsers:
                        self.browsers.remove(browser)
                    self.browsers.append(new_browser)
                    del self.browser_slots[browser]
                    del self.browser_visits[browser]
                    self.browser_slots[new_browser] = USUARIOS_POR_BROWSER
                    self.browser_visits[new_browser] = 0
                    for _ in range(USUARIOS_POR_BROWSER):
                        await self.available_slots.put(new_browser)
                    if self.stats_tracker:
                        await self.stats_tracker.increment_restarts()
                    return
            await self.available_slots.put(browser)
        except Exception as e:
            logger.error(f"Erro ao retornar browser: {e}")
    
    async def close_all(self):
        self.running = False
        for browser in self.browsers:
            try:
                await browser.close()
            except:
                pass
        self.browsers.clear()
        self.browser_slots.clear()
        self.browser_visits.clear()
        while not self.available_slots.empty():
            try:
                self.available_slots.get_nowait()
            except:
                pass
        gc.collect()
        logger.info(f"Todos os browsers {self.browser_type.upper()} fechados")


class RateLimiter:
    def __init__(self, max_requests_per_second=5):
        self.max_requests = max_requests_per_second
        self.requests = []
        self.lock = asyncio.Lock()
    async def acquire(self):
        async with self.lock:
            now = time.time()
            self.requests = [r for r in self.requests if r > now - 1]
            if len(self.requests) >= self.max_requests:
                wait_time = 1 - (now - self.requests[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            self.requests = [r for r in self.requests if r > time.time() - 1]
            self.requests.append(time.time())
            return True


def get_user_agent_by_browser(browser_type):
    if browser_type == "chromium":
        chrome_version = random.randint(120, 122)
        return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36'
    else:
        firefox_version = random.randint(115, 117)
        return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{firefox_version}.0) Gecko/20100101 Firefox/{firefox_version}.0'


async def comportamento_humano_realista(page, usuario_id, duracao_segundos):
    inicio = time.time()
    interacoes_realizadas = 0
    try:
        while time.time() - inicio < duracao_segundos:
            acao = random.choice(['scroll', 'read_time', 'move_mouse'])
            try:
                if acao == 'scroll':
                    await page.evaluate(f"window.scrollBy(0, {random.randint(200,500)})")
                    await asyncio.sleep(random.uniform(1, 2))
                    interacoes_realizadas += 1
                elif acao == 'read_time':
                    tempo_leitura = random.uniform(2, 5)
                    await asyncio.sleep(tempo_leitura)
                    interacoes_realizadas += 1
                elif acao == 'move_mouse':
                    pos_x = random.randint(100, 1300)
                    pos_y = random.randint(100, 700)
                    start = (random.randint(200,800), random.randint(200,600))
                    await mover_mouse_humano(page, start, (pos_x, pos_y))
                    await asyncio.sleep(random.uniform(0.5, 1))
                    interacoes_realizadas += 1
                await asyncio.sleep(random.uniform(2, 5))
            except Exception:
                break
    except:
        pass
    return interacoes_realizadas


async def carregar_pagina_com_retry(page, url, usuario_id):
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=TIMEOUT_CARREGAMENTO)
        await asyncio.sleep(random.uniform(0.5, 1))
        return True
    except Exception as e:
        logger.debug(f"U{usuario_id}: Falha ao carregar {url}: {e}")
        return False


async def limpar_contadores_anti_inflate(page, usuario_id, visita_numero):
    """Limpa contadores sb_* a cada 5 visitas para evitar bloqueio"""
    if visita_numero % 5 == 0:
        try:
            await page.evaluate("""
                localStorage.removeItem('sb_count_');
                localStorage.removeItem('sb_page_');
                localStorage.removeItem('sb_main_');
                sessionStorage.removeItem('sb_count_');
                sessionStorage.removeItem('sb_page_');
                sessionStorage.removeItem('sb_main_');
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (key && (key.startsWith('sb_') || key.includes('sb_count'))) {
                        localStorage.removeItem(key);
                    }
                }
                for (var i = 0; i < sessionStorage.length; i++) {
                    var key = sessionStorage.key(i);
                    if (key && (key.startsWith('sb_') || key.includes('sb_count'))) {
                        sessionStorage.removeItem(key);
                    }
                }
            """)
            logger.debug(f"U{usuario_id}: Contadores de limite limpos (visita #{visita_numero})")
        except Exception as e:
            logger.debug(f"U{usuario_id}: Erro ao limpar contadores: {e}")


async def executar_visita(usuario_id, browser_pool, rate_limiter, stats_tracker, browser_type, memory_optimizer, visita_numero):
    browser = None
    context = None
    page = None
    
    paginas = [
        f"{SITE_BASE}/2026/03/blog-post.html?m=1",
        f"{SITE_BASE}/",
    ]
    
    try:
        await memory_optimizer.periodic_cleanup()
        
        try:
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            if mem_mb > MAX_RAM_MB:
                logger.warning(f"U{usuario_id}: RAM alta ({mem_mb:.0f}MB), aguardando 60s...")
                await asyncio.sleep(60)
                return False
        except:
            pass
        
        await rate_limiter.acquire()
        url = random.choice(paginas)
        
        browser = await browser_pool.get_browser(usuario_id)
        
        # ========== CONFIGURACAO DO PROXY ==========
        proxy_config = {"server": PROXY_URL} if PROXY_URL else None
        if proxy_config:
            logger.debug(f"U{usuario_id}: Usando proxy {PROXY_URL}")
        
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent=get_user_agent_by_browser(browser_type),
            ignore_https_errors=True,
            java_script_enabled=True,
            proxy=proxy_config   # <-- ADICIONADO
        )
        
        await context.add_init_script(get_anti_detection_script(browser_type))
        page = await context.new_page()
        
        await limpar_contadores_anti_inflate(page, usuario_id, visita_numero)
        
        carregou = await carregar_pagina_com_retry(page, url, usuario_id)
        if not carregou:
            await stats_tracker.increment_timeouts()
            return False
        
        await asyncio.sleep(random.uniform(2, 4))
        
        # Clique para popunder (coordenadas variadas)
        posicoes_clique = [(random.randint(1200, 1350), random.randint(680, 750)),
                           (random.randint(1150, 1280), random.randint(660, 720)),
                           (random.randint(1250, 1360), random.randint(700, 760))]
        for pos_x, pos_y in posicoes_clique:
            try:
                start = (random.randint(200, 800), random.randint(200, 600))
                await mover_mouse_humano(page, start, (pos_x, pos_y))
                await page.mouse.click(pos_x, pos_y)
                logger.info(f"POPUNDER U{usuario_id}! Visita #{visita_numero}")
                await stats_tracker.increment_popunders()
                break
            except:
                continue
        
        tempo_permanencia = random.uniform(TEMPO_MINIMO_PAGINA, TEMPO_MAXIMO_PAGINA)
        interacoes = await comportamento_humano_realista(page, usuario_id, tempo_permanencia)
        
        await stats_tracker.add_tempo(tempo_permanencia)
        await stats_tracker.increment_visitas()
        
        logger.info(f"OK U{usuario_id} visita #{visita_numero}: {tempo_permanencia:.0f}s (interacoes: {interacoes})")
        
        await stats_tracker.log_stats_periodico(memory_optimizer)
        
        return True
        
    except Exception as e:
        await stats_tracker.increment_erros()
        logger.error(f"ERRO U{usuario_id}: {str(e)[:100]}")
        return False
        
    finally:
        if page:
            try:
                await page.close()
            except:
                pass
        if context:
            try:
                await context.close()
            except:
                pass
        if browser:
            try:
                await browser_pool.return_browser(browser, usuario_id)
            except:
                pass


async def simular_usuario_loop(usuario_id, browser_pool, rate_limiter, stats_tracker, browser_type, memory_optimizer):
    await stats_tracker.add_usuario_ativo()
    visita_numero = 0
    logger.info(f"U{usuario_id}: Iniciando com {browser_type.upper()} (anti-fingerprint MAX)")
    try:
        while True:
            visita_numero += 1
            try:
                sucesso = await asyncio.wait_for(
                    executar_visita(usuario_id, browser_pool, rate_limiter, stats_tracker, browser_type, memory_optimizer, visita_numero),
                    timeout=TIMEOUT_VISITA
                )
                if not sucesso:
                    logger.warning(f"U{usuario_id}: Visita #{visita_numero} falhou")
                if visita_numero % 5 == 0:
                    gc.collect()
                await asyncio.sleep(random.uniform(8, 15))
            except asyncio.TimeoutError:
                logger.warning(f"U{usuario_id}: Timeout na visita #{visita_numero}")
                await stats_tracker.increment_erros()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"U{usuario_id}: Erro no loop: {e}")
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        logger.info(f"U{usuario_id}: Parado")
    except Exception as e:
        logger.error(f"U{usuario_id}: Erro fatal no loop: {e}")
        traceback.print_exc()
    finally:
        await stats_tracker.remove_usuario_ativo()


async def watchdog(memory_optimizer):
    while True:
        try:
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            if mem > MAX_RAM_MB:
                logger.warning(f"RAM alta: {int(mem)}MB -> GC")
                gc.collect()
                gc.collect(2)
            await memory_optimizer.periodic_cleanup()
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        await asyncio.sleep(10)


async def executar_sistema_continuo():
    logger.info(f"{'='*60}")
    logger.info(f"SISTEMA ECO - {NAVEGADOR.upper()} (ANTI-FINGERPRINT MAX)")
    logger.info(f"{SITE_BASE}")
    logger.info(f"Configuracao ECO:")
    logger.info(f"   - Navegador: {NAVEGADOR.upper()}")
    logger.info(f"   - Usuarios: {NUM_USUARIOS}")
    logger.info(f"   - Browsers: {MAX_CONCURRENT_BROWSERS}")
    logger.info(f"   - Usuarios por browser: {USUARIOS_POR_BROWSER}")
    logger.info(f"   - RAM limite: {MAX_RAM_MB}MB")
    logger.info(f"   - Reinicio apos: {RESTART_BROWSER_AFTER_VISITS} visitas")
    logger.info(f"   - Limpeza a cada: {CLEANUP_INTERVAL}s")
    logger.info(f"   - Timeout visita: {TIMEOUT_VISITA}s")
    logger.info(f"   - Anti-fingerprint: MAX (userAgentData, canvas, webgl, plugins, eval, visibility)")
    if PROXY_URL:
        logger.info(f"   - Proxy ativo: {PROXY_URL}")
    else:
        logger.info(f"   - Proxy: DESATIVADO (IP direto)")
    logger.info(f"{'='*60}\n")
    
    stats_tracker = StatsTracker()
    rate_limiter = RateLimiter(max_requests_per_second=5)
    memory_optimizer = MemoryOptimizer(MAX_RAM_MB)
    
    async with async_playwright() as p:
        browser_pool = ScalableBrowserPool(p, MAX_CONCURRENT_BROWSERS, NAVEGADOR, stats_tracker)
        try:
            await browser_pool.initialize()
            asyncio.create_task(watchdog(memory_optimizer))
            logger.info(f"\nINICIANDO {NUM_USUARIOS} USUARIOS...\n")
            tasks = []
            for i in range(1, NUM_USUARIOS + 1):
                task = asyncio.create_task(
                    simular_usuario_loop(i, browser_pool, rate_limiter, stats_tracker, NAVEGADOR, memory_optimizer)
                )
                tasks.append(task)
                await asyncio.sleep(0.5)
            logger.info(f"\nTODOS RODANDO EM MODO ECO!")
            logger.info(f"Pressione Ctrl+C para parar.\n")
            while True:
                for i, task in enumerate(tasks):
                    if task.done():
                        try:
                            task.result()
                        except Exception as e:
                            logger.error(f"Task {i+1} morreu: {e}")
                            new_task = asyncio.create_task(
                                simular_usuario_loop(i+1, browser_pool, rate_limiter, stats_tracker, NAVEGADOR, memory_optimizer)
                            )
                            tasks[i] = new_task
                            logger.info(f"Task {i+1} reiniciada")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("\nParando...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await browser_pool.close_all()
    
    stats = await stats_tracker.get_stats()
    logger.info(f"\n{'='*60}")
    logger.info(f"RELATORIO FINAL ECO")
    logger.info(f"Total de visitas: {stats['visitas']}")
    logger.info(f"Popunders: {stats['popunders']}")
    logger.info(f"Reinicios de browser: {stats['browser_restarts']}")
    logger.info(f"Taxa de sucesso: {(stats['visitas']/(stats['visitas']+stats['erros'])*100) if stats['visitas']+stats['erros']>0 else 0:.1f}%")
    logger.info(f"{'='*60}")


async def main():
    try:
        await executar_sistema_continuo()
    except KeyboardInterrupt:
        logger.info("\nSistema interrompido")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nScript interrompido")
