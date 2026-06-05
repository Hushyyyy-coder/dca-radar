"""
=====================================================================
 CRYPTO DCA RADAR  —  Vigilante (watcher) con alertas a Telegram
=====================================================================
 Corre solo en la nube (GitHub Actions, cada 30 min por defecto).
 Cuando un activo entra en una zona de tramo (T1/T2/T3) o rompe la
 invalidación, te manda un mensaje a Telegram.

 Para evitar spam: solo avisa cuando la señal CAMBIA respecto a la
 última vez (guarda el estado en estado.json).

 Necesita dos secretos (los configuras en GitHub, ver guía):
   TELEGRAM_TOKEN   -> el token de tu bot
   TELEGRAM_CHAT_ID -> tu chat id
=====================================================================
"""
import os, json, time, requests

# ---- mismos niveles que la app ----
TRAMOS_PCT = [25, 35, 40]
DESCUENTO_TRAMOS_PCT = [0.0, 12.0, 25.0]
USAR_NIVELES_MANUALES = True
NIVELES_MANUALES = {
    "BTC":[61000,53500,44000], "ETH":[1600,1350,1100], "SOL":[64,50,37],
    "HYPE":[56,47,38], "TAO":[190,157,120], "LINK":[7.2,6.0,4.75],
    "ONDO":[0.34,0.285,0.22], "QNT":[65,59,51], "RENDER":[1.65,1.32,0.97],
    "NEAR":[2.0,1.65,1.30], "AVAX":[6.9,6.0,5.0], "ADA":[0.157,0.140,0.115],
    "DOGE":[0.081,0.071,0.060],
}
ACTIVOS = [
    ("BTC","bitcoin",40000),("ETH","ethereum",1000),("SOL","solana",32),
    ("HYPE","hyperliquid",35),("TAO","bittensor",100),("LINK","chainlink",4.2),
    ("ONDO","ondo-finance",0.18),("QNT","quant-network",48),
    ("RENDER","render-token",0.85),("NEAR","near",1.15),
    ("AVAX","avalanche-2",4.5),("ADA","cardano",0.10),("DOGE","dogecoin",0.055),
]
CG = "https://api.coingecko.com/api/v3"
ESTADO_FILE = "estado.json"

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

def precios():
    ids = [a[1] for a in ACTIVOS]
    params = {"vs_currency":"usd","ids":",".join(ids)}
    headers = {"User-Agent":"dca-watcher"}
    for _ in range(3):
        try:
            r = requests.get(f"{CG}/coins/markets", params=params,
                             headers=headers, timeout=30)
            if r.status_code in (429,403): time.sleep(6); continue
            r.raise_for_status()
            return {row["id"]: row.get("current_price") for row in r.json()}
        except Exception:
            time.sleep(5)
    return {}

def tramos_para(tk, precio):
    if USAR_NIVELES_MANUALES and tk in NIVELES_MANUALES:
        return NIVELES_MANUALES[tk]
    return [round(precio*(1-d/100),8) for d in DESCUENTO_TRAMOS_PCT]

def senal(precio, tr, inval):
    t1,t2,t3 = tr
    if precio < inval: return "STOP"
    if precio <= t3:   return "T3"
    if precio <= t2:   return "T2"
    if precio <= t1:   return "T1"
    return "ESPERAR"

def cargar_estado():
    try:
        with open(ESTADO_FILE) as f: return json.load(f)
    except Exception:
        return {}

def guardar_estado(e):
    with open(ESTADO_FILE,"w") as f: json.dump(e,f,indent=2)

def telegram(msg):
    if not TG_TOKEN or not TG_CHAT:
        print("! Faltan TELEGRAM_TOKEN / TELEGRAM_CHAT_ID"); return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id":TG_CHAT,"text":msg,
                                 "parse_mode":"Markdown"}, timeout=20)
    except Exception as ex:
        print("error telegram:", ex)

# Solo avisamos en estas transiciones "interesantes"
RELEVANTES = {"T1","T2","T3","STOP"}

def main():
    # MODO PRUEBA: si la variable TEST vale "1", manda un mensaje de test
    # y termina. Sirve para comprobar que Telegram está bien conectado.
    if os.environ.get("TEST") == "1":
        telegram("✅ *Prueba de Crypto DCA Radar*\n\n"
                 "Si ves este mensaje, el bot está bien conectado. "
                 "A partir de ahora te avisaré cuando un activo entre "
                 "en zona de compra o rompa su invalidación.")
        print("Mensaje de prueba enviado.")
        return

    px = precios()
    if not px:
        print("Sin precios, salgo."); return
    estado = cargar_estado()
    cambios = []

    for tk, cid, inval in ACTIVOS:
        p = px.get(cid)
        if p is None: continue
        tr = tramos_para(tk, p)
        s_actual = senal(p, tr, inval)
        s_previo = estado.get(tk)

        # avisar solo si la señal cambió Y la nueva es relevante
        if s_actual != s_previo and s_actual in RELEVANTES:
            if s_actual == "STOP":
                cambios.append(f"🛑 *{tk}* rompió invalidación "
                               f"(${inval}). Precio ${p:.6g}. DEJAR de promediar.")
            else:
                idx = {"T1":0,"T2":1,"T3":2}[s_actual]
                pct = TRAMOS_PCT[idx]
                cambios.append(f"🟢 *{tk}* entró en *{s_actual}* "
                               f"(${tr[idx]:.6g}). Precio ${p:.6g}. "
                               f"Tramo {pct}% del plan.")
        estado[tk] = s_actual

    if cambios:
        cabecera = "📊 *Crypto DCA Radar — alertas*\n\n"
        telegram(cabecera + "\n".join(cambios))
        print("Enviadas", len(cambios), "alertas.")
    else:
        print("Sin cambios de señal relevantes.")

    guardar_estado(estado)

if __name__ == "__main__":
    main()
