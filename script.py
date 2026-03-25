import requests
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

INTERES_TASAS = [40, 50, 60, 70, 80, 90, 100]
ultimo_umbral_avisado = 0
last_update_id = 0 # Para rastrear mensajes nuevos de Telegram
ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
ultima_tasa_valida = None


def log(msg):
    ts = datetime.now(ARG_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def extraer_panel_cauciones(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("cotizaciones", "data", "items", "resultado", "result"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []

def obtener_token():
    url = "https://api.invertironline.com/token"
    payload = {'username': os.getenv('IOL_USERNAME'), 'password': os.getenv('IOL_PASSWORD'), 'grant_type': 'password'}
    if not payload['username'] or not payload['password']:
        return None, "Faltan IOL_USERNAME o IOL_PASSWORD en variables de entorno"

    try:
        r = requests.post(url, data=payload, timeout=10)
    except requests.RequestException as exc:
        return None, f"Error de red al pedir token: {exc}"

    if r.status_code != 200:
        detalle = ""
        try:
            detalle = r.json()
        except ValueError:
            detalle = r.text[:300]
        return None, f"Token IOL HTTP {r.status_code}: {detalle}"

    try:
        token = r.json().get('access_token')
    except ValueError:
        return None, "Respuesta de token no es JSON"

    if not token:
        return None, "No vino access_token en la respuesta de IOL"

    return token, None

def consultar_tasa_dinamica(token):
    urls = [
        "https://api.invertironline.com/api/v2/Cotizaciones/Cauciones/PESOS",
        "https://api.invertironline.com/api/v2/Cotizaciones/Cauciones/PESOS/1",
        "https://api.invertironline.com/api/v2/Cotizaciones/Cauciones/PESOS/2",
        "https://api.invertironline.com/api/v2/Cotizaciones/Cauciones/PESOS/7",
        "https://api.invertironline.com/api/v2/Cotizaciones/Cauciones/PESOS/14",
    ]
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'User-Agent': 'iol-cauciones-bot/1.0'
    }

    if not token:
        return {"ok": False, "motivo": "Sin token de autenticacion"}

    ultimo_error = None
    hubo_5xx = False
    hubo_auth = False
    hubo_parseo = False
    hubo_red = False
    endpoints_5xx = []

    max_reintentos_5xx = 3
    backoff_base_seg = 1

    for url in urls:
        for intento in range(max_reintentos_5xx):
            try:
                r = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as exc:
                hubo_red = True
                ultimo_error = {
                    "ok": False,
                    "tipo": "red",
                    "motivo": f"Error de red consultando cauciones: {exc}"
                }
                break

            if r.status_code >= 500:
                hubo_5xx = True
                endpoints_5xx.append(url)
                if intento < (max_reintentos_5xx - 1):
                    espera = backoff_base_seg * (2 ** intento)
                    time.sleep(espera)
                    continue

                ultimo_error = {
                    "ok": False,
                    "tipo": "servidor",
                    "motivo": "IOL temporalmente no disponible (HTTP 5xx)",
                    "detalle": f"Endpoint: {url}"
                }
                break

            if r.status_code in (401, 403):
                hubo_auth = True
                detalle = ""
                content_type = r.headers.get('Content-Type', '').lower()
                if 'application/json' in content_type:
                    try:
                        detalle = str(r.json())[:300]
                    except ValueError:
                        detalle = r.text[:120]
                else:
                    detalle = r.text[:120]

                ultimo_error = {
                    "ok": False,
                    "tipo": "auth",
                    "motivo": f"Error de autenticacion/permiso HTTP {r.status_code}",
                    "detalle": detalle or "Token invalido/expirado o alcance insuficiente"
                }
                break

            if r.status_code != 200:
                detalle = ""
                content_type = r.headers.get('Content-Type', '').lower()
                if 'application/json' in content_type:
                    try:
                        detalle = str(r.json())[:300]
                    except ValueError:
                        detalle = r.text[:120]
                else:
                    detalle = f"Respuesta no JSON ({content_type or 'desconocido'})"

                ultimo_error = {
                    "ok": False,
                    "tipo": "http",
                    "motivo": f"Cauciones HTTP {r.status_code}",
                    "detalle": detalle
                }
                break

            try:
                payload = r.json()
            except ValueError:
                hubo_parseo = True
                ultimo_error = {
                    "ok": False,
                    "tipo": "parseo",
                    "motivo": "Respuesta de cauciones no es JSON",
                    "detalle": f"Endpoint: {url}"
                }
                break

            panel = extraer_panel_cauciones(payload)
            mejor_tasa = 0
            mejor_plazo = "N/A"

            for c in panel:
                puntas = c.get('puntas') or []
                if not puntas:
                    continue

                for punta in puntas:
                    tasa_actual = punta.get('tasa', 0)
                    if tasa_actual > mejor_tasa:
                        mejor_tasa = tasa_actual
                        mejor_plazo = c.get('plazo', 'N/A')

            if mejor_tasa > 0:
                return {"ok": True, "tasa": mejor_tasa, "plazo": mejor_plazo}

            ultimo_error = {
                "ok": False,
                "tipo": "sin_puntas",
                "motivo": "Sin puntas con tasa",
                "detalle": f"Endpoint consultado: {url}. Mercado posiblemente cerrado o sin liquidez"
            }
            continue

    if hubo_auth:
        return ultimo_error or {
            "ok": False,
            "tipo": "auth",
            "motivo": "Fallo de autenticacion con API de IOL"
        }

    if hubo_5xx:
        detalle_endpoints = ", ".join(sorted(set(endpoints_5xx))) if endpoints_5xx else "desconocido"
        return ultimo_error or {
            "ok": False,
            "tipo": "servidor",
            "motivo": "IOL temporalmente no disponible (HTTP 5xx)",
            "detalle": f"Endpoints con 5xx: {detalle_endpoints}"
        }

    if hubo_parseo:
        return ultimo_error or {
            "ok": False,
            "tipo": "parseo",
            "motivo": "Respuesta invalida de API de cauciones"
        }

    if hubo_red:
        return ultimo_error or {
            "ok": False,
            "tipo": "red",
            "motivo": "Error de red al consultar cauciones"
        }

    return ultimo_error or {
        "ok": False,
        "tipo": "desconocido",
        "motivo": "No se pudo obtener tasa de cauciones",
        "detalle": "Sin respuesta util de IOL"
    }

def enviar_telegram(mensaje):
    token_tg = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token_tg}/sendMessage"
    requests.post(url, json={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'Markdown'}, timeout=10)


def obtener_mejor_tasa():
    global ultima_tasa_valida

    token, err_token = obtener_token()
    if err_token:
        return None, None, f"No se pudo autenticar en IOL: {err_token}"

    resultado = consultar_tasa_dinamica(token)
    if resultado.get("ok"):
        tasa = resultado.get("tasa")
        plazo = resultado.get("plazo")
        ultima_tasa_valida = {
            "tasa": tasa,
            "plazo": plazo,
            "timestamp": datetime.now(ARG_TZ).strftime("%Y-%m-%d %H:%M:%S")
        }
        return tasa, plazo, None

    tipo_error = resultado.get("tipo", "desconocido")
    motivo = resultado.get("motivo", "Error desconocido")
    detalle = resultado.get("detalle")
    if detalle:
        return None, None, f"[{tipo_error}] {motivo}. {detalle}"
    return None, None, f"[{tipo_error}] {motivo}"

def revisar_comandos():
    global last_update_id
    token_tg = os.getenv('TELEGRAM_TOKEN')
    url = f"https://api.telegram.org/bot{token_tg}/getUpdates"
    try:
        r = requests.get(url, params={'offset': last_update_id + 1, 'timeout': 1}, timeout=10)
        updates = r.json().get('result', [])
        for update in updates:
            last_update_id = update['update_id']
            mensaje_recibido = update.get('message', {}).get('text', '').strip().lower()
            
            if mensaje_recibido in ('/tasa', 'tasa'):
                tasa, plazo, error = obtener_mejor_tasa()
                if tasa:
                    enviar_telegram(f"📊 La mejor tasa actual es: *{tasa}%* (Plazo: {plazo} días)")
                else:
                    if ultima_tasa_valida:
                        enviar_telegram(
                            "📊 Mercado sin tasa en vivo ahora. "
                            f"Ultima valida: *{ultima_tasa_valida['tasa']}%* "
                            f"(Plazo: {ultima_tasa_valida['plazo']} dias, "
                            f"capturada: {ultima_tasa_valida['timestamp']} AR). "
                            f"Motivo: *{error or 'Mercado cerrado o sin puntas'}*"
                        )
                    else:
                        enviar_telegram(f"📊 Estado: *{error or 'Mercado cerrado o sin puntas'}*")
                    
            elif mensaje_recibido in ('/status', 'status'):
                ahora = datetime.now(ARG_TZ)
                en_horario = ahora.weekday() <= 4 and ((ahora.hour > 10 or (ahora.hour == 10 and ahora.minute >= 30)) and ahora.hour < 17)
                enviar_telegram(
                    f"🤖 Bot *Online* | Hora AR: {ahora.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"Horario de mercado: {'SI' if en_horario else 'NO'}"
                )
    except Exception as exc:
        log(f"Error revisando comandos de Telegram: {exc}")

# --- LOOP PRINCIPAL ---
log("Bot iniciado...")
while True:
    ahora = datetime.now(ARG_TZ)
    
    # Siempre revisamos si hay comandos (aunque sea de noche)
    revisar_comandos()

    en_horario_mercado = ahora.weekday() <= 4 and ((ahora.hour > 10 or (ahora.hour == 10 and ahora.minute >= 30)) and ahora.hour < 17)

    if en_horario_mercado:
        tasa, plazo, error = obtener_mejor_tasa()
        if tasa:
            for nivel in reversed(INTERES_TASAS):
                if tasa >= nivel:
                    if ultimo_umbral_avisado != nivel:
                        enviar_telegram(f"💰 *ALERTA*: Tasa en *{tasa}%* a {plazo} días (Nivel {nivel}%)")
                        ultimo_umbral_avisado = nivel
                    break
            if tasa < (ultimo_umbral_avisado - 5):
                ultimo_umbral_avisado = 0
        else:
            log(f"Sin tasa para alertas: {error}")
        time.sleep(60) # Revisamos tasa cada minuto, pero comandos mas seguido
    else:
        time.sleep(10) # Fuera de hora, revisamos comandos cada 10 seg.