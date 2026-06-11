"""
=====================================================================
 CRYPTO DCA RADAR  —  App web (Streamlit)
=====================================================================
 Se abre en navegador (PC y iPhone). En iPhone: Safari -> Compartir
 -> "Añadir a pantalla de inicio" y queda como una app.

 Esta app SOLO consulta y muestra. Las alertas las manda el
 vigilante (watcher.py) que corre solo en la nube.
=====================================================================
"""
import streamlit as st
import requests, time, datetime as dt
import pandas as pd

# ---------------------------------------------------------------
#  CONFIG  (mismos parámetros que tu script de Colab)
# ---------------------------------------------------------------
CAPITAL_TOTAL = 10000
DIVISA = "USD"
PESO_CATEGORIA_PCT = {"Nucleo": 55, "Lider_vivo": 30, "Beta_debil": 12, "Meme_ciclo": 3}
TRAMOS_PCT = [25, 35, 40]
DESCUENTO_TRAMOS_PCT = [0.0, 12.0, 25.0]

USAR_NIVELES_MANUALES = True
NIVELES_MANUALES = {
    "BTC":  [61000, 53500, 44000], "ETH": [1600, 1350, 1100],
    "SOL":  [64, 50, 37],          "HYPE": [56, 47, 38],
    "TAO":  [190, 157, 120],       "LINK": [7.2, 6.0, 4.75],
    "ONDO": [0.34, 0.285, 0.22],   "QNT":  [65, 59, 51],
    "RENDER":[1.65, 1.32, 0.97],   "NEAR": [2.0, 1.65, 1.30],
    "AVAX": [6.9, 6.0, 5.0],       "ADA":  [0.157, 0.140, 0.115],
    "DOGE": [0.081, 0.071, 0.060],
}

ACTIVOS = [
    ("BTC","bitcoin","Nucleo",40000),       ("ETH","ethereum","Nucleo",1000),
    ("SOL","solana","Nucleo",32),           ("HYPE","hyperliquid","Lider_vivo",35),
    ("TAO","bittensor","Lider_vivo",100),   ("LINK","chainlink","Lider_vivo",4.2),
    ("ONDO","ondo-finance","Lider_vivo",0.18),("QNT","quant-network","Lider_vivo",48),
    ("RENDER","render-token","Beta_debil",0.85),("NEAR","near","Beta_debil",1.15),
    ("AVAX","avalanche-2","Beta_debil",4.5),("ADA","cardano","Beta_debil",0.10),
    ("DOGE","dogecoin","Meme_ciclo",0.055),
]
CG = "https://api.coingecko.com/api/v3"

# Acciones vinculadas a BTC, vía sus tokens tokenizados en CoinGecko (sin clave).
# Cotizan 24/7. MSTRx es líquido; MARAON/RIOTON son ilíquidos (precio orientativo).
# tramos = [T1,T2,T3] e invalidación, como en las cripto (None si no se definen).
ACCIONES = [
    # ticker, coingecko_id, categoria, liquidez, tramos, invalidacion
    ("MSTR", "microstrategy-xstock",              "Accion_BTC", "alta", [115, 105, 92], 82),
    ("MARA", "mara-holdings-ondo-tokenized-stock", "Accion_BTC", "baja", None, None),
    ("RIOT", "riot-platforms-ondo-tokenized-stock","Accion_BTC", "baja", None, None),
]

# ---------------------------------------------------------------
#  FUNCIONES DE DATOS  (cacheadas 5 min para no saturar la API)
# ---------------------------------------------------------------
@st.cache_data(ttl=300)
def market_data():
    ids = [a[1] for a in ACTIVOS]
    params = {"vs_currency":"usd","ids":",".join(ids),
              "price_change_percentage":"24h,7d"}
    headers = {"User-Agent":"dca-radar"}
    out = {}
    for _ in range(3):
        try:
            r = requests.get(f"{CG}/coins/markets", params=params,
                             headers=headers, timeout=30)
            if r.status_code in (429,403):
                time.sleep(5); continue
            r.raise_for_status()
            for row in r.json():
                out[row["id"]] = {
                    "price": row.get("current_price"),
                    "ath": row.get("ath"),
                    "ath_change_pct": row.get("ath_change_percentage"),
                    "chg_7d": row.get("price_change_percentage_7d_in_currency"),
                    "rank": row.get("market_cap_rank"),
                }
            return out
        except Exception:
            time.sleep(4)
    return out

# ---------------------------------------------------------------
#  ACCIONES (Stooq, sin API key) + INDICADORES DE SOBREEXTENSIÓN
# ---------------------------------------------------------------
import numpy as np

@st.cache_data(ttl=300)
def cg_precio(coingecko_id):
    """Último precio de un token (acción tokenizada) vía CoinGecko."""
    try:
        r = requests.get(
            f"{CG}/simple/price",
            params={"ids": coingecko_id, "vs_currencies": "usd"},
            headers={"User-Agent": "dca-radar"}, timeout=20,
        )
        r.raise_for_status()
        return r.json().get(coingecko_id, {}).get("usd")
    except Exception:
        return None

@st.cache_data(ttl=900)
def cg_historico(coingecko_id, dias=120):
    """Cierres diarios recientes de un token (para medias y RSI), vía CoinGecko."""
    try:
        r = requests.get(
            f"{CG}/coins/{coingecko_id}/market_chart",
            params={"vs_currency": "usd", "days": dias, "interval": "daily"},
            headers={"User-Agent": "dca-radar"}, timeout=30,
        )
        r.raise_for_status()
        precios = r.json().get("prices", [])
        cierres = [p[1] for p in precios if p and len(p) == 2]
        return cierres if len(cierres) >= 30 else None
    except Exception:
        return None

def rsi(closes, period=14):
    if not closes or len(closes) < period + 1: return None
    s = pd.Series(closes)
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    val = (100 - (100/(1+rs))).iloc[-1]
    return None if pd.isna(val) else round(float(val), 1)

def dist_media(closes, period=50):
    if not closes or len(closes) < period: return None
    s = pd.Series(closes)
    ma = s.rolling(period).mean().iloc[-1]
    if pd.isna(ma) or ma == 0: return None
    return round((s.iloc[-1]/ma - 1)*100, 1)

def senal_sobreextension(rsi_v, dist_v):
    """
    Indicador DESCRIPTIVO de cuán estirado al alza está un activo.
    NO es una recomendación de ponerse corto ni de operar: solo informa.
    """
    puntos = 0
    if rsi_v is not None and rsi_v >= 70: puntos += 1
    if rsi_v is not None and rsi_v >= 80: puntos += 1
    if dist_v is not None and dist_v >= 20: puntos += 1
    if dist_v is not None and dist_v >= 40: puntos += 1
    if puntos >= 3: return "🔴 Muy estirado"
    if puntos >= 1: return "🟡 Algo estirado"
    return "⚪ Normal"

@st.cache_data(ttl=900)
def fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=15)
        d = r.json()["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:
        return None, None

def tramos_para(tk, precio):
    if USAR_NIVELES_MANUALES and tk in NIVELES_MANUALES:
        return NIVELES_MANUALES[tk]
    return [round(precio*(1-d/100),8) for d in DESCUENTO_TRAMOS_PCT]

def precio_medio(tramos, pesos):
    return round(sum(t*w for t,w in zip(tramos,pesos))/sum(pesos),8)

def senal_tramo(precio, tr, inval):
    t1,t2,t3 = tr
    if precio < inval: return "🛑 STOP (bajo invalidación)"
    if precio <= t3:   return "🟢 T3 activo (zona profunda)"
    if precio <= t2:   return "🟢 T2 activo"
    if precio <= t1:   return "🟡 T1 activo"
    return "⚪ Esperar (sobre T1)"

# ---------------------------------------------------------------
#  INTERFAZ
# ---------------------------------------------------------------
st.set_page_config(page_title="Crypto DCA Radar", page_icon="📊", layout="wide")
st.title("📊 Crypto DCA Radar")
st.caption("No es asesoramiento financiero. Decisiones tuyas. "
           f"Actualizado: {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC")

fg_val, fg_cls = fear_greed()
if fg_val is not None:
    extra = ""
    if fg_val <= 25: extra = " — zona donde suelen ejecutarse T2/T3"
    elif fg_val >= 75: extra = " — codicia: zona de tomar beneficios"
    st.info(f"**Fear & Greed Index: {fg_val} ({fg_cls})**{extra}")

md = market_data()
if not md:
    st.error("No se pudieron cargar precios ahora. Reintenta en 1-2 min.")
    st.stop()

btc7 = md.get("bitcoin",{}).get("chg_7d")
filas = []
for tk, cid, cat, inval in ACTIVOS:
    d = md.get(cid,{})
    p = d.get("price")
    if p is None: continue
    tr = tramos_para(tk,p)
    fr = None if (d.get("chg_7d") is None or btc7 is None) else round(d["chg_7d"]-btc7,1)
    filas.append({
        "Ticker":tk, "Categoría":cat, "Precio":p,
        "Señal hoy":senal_tramo(p,tr,inval),
        "% vs ATH":round(d.get("ath_change_pct") or 0,1),
        "% 7d":round(d.get("chg_7d") or 0,1),
        "FR vs BTC":fr,
        "T1":tr[0], "T2":tr[1], "T3":tr[2],
        "Precio medio 3T":precio_medio(tr,TRAMOS_PCT),
        "Invalidación":inval,
    })

df = pd.DataFrame(filas).sort_values("FR vs BTC", na_position="last").reset_index(drop=True)

# Resaltar señales con color
def color_senal(v):
    if "STOP" in str(v):   return "background-color:#5a1e1e;color:#fff"
    if "T3" in str(v) or "T2" in str(v): return "background-color:#1e4620;color:#fff"
    if "T1" in str(v):     return "background-color:#5a4d1e;color:#fff"
    return ""

st.subheader("Resumen (de peor a mejor fuerza relativa vs BTC)")

# Selector de vista: el usuario elige PC (tabla) o Móvil (tarjetas).
# Por defecto Móvil, que es lo más cómodo en el teléfono.
vista = st.radio(
    "Vista:",
    ["📱 Móvil (tarjetas)", "💻 PC (tabla completa)"],
    horizontal=True,
    label_visibility="collapsed",
)

if "PC" in vista:
    # ---- Vista de tabla completa (PC) ----
    st.dataframe(
        df.style.map(color_senal, subset=["Señal hoy"]),
        use_container_width=True, height=520,
    )
else:
    # ---- Vista de tarjetas (Móvil) ----
    # Cada activo es una tarjeta apilada: precio + señal + % vs ATH de un
    # vistazo, y el detalle (tramos e invalidación) se despliega al tocar.
    def color_fondo(senal):
        if "STOP" in senal: return "#5a1e1e"
        if "T3" in senal or "T2" in senal: return "#1e4620"
        if "T1" in senal: return "#5a4d1e"
        return "#2b2b2b"

    for _, r in df.iterrows():
        bg = color_fondo(r["Señal hoy"])
        # Cabecera de la tarjeta (siempre visible)
        st.markdown(
            f"""
            <div style="background:{bg};border-radius:12px;padding:12px 16px;
                        margin-bottom:6px;color:#fff;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:1.3em;font-weight:700;">{r['Ticker']}</span>
                <span style="font-size:0.85em;opacity:0.85;">{r['Categoría']}</span>
              </div>
              <div style="display:flex;justify-content:space-between;margin-top:6px;">
                <span style="font-size:1.05em;">💲 {r['Precio']:.6g}</span>
                <span style="font-size:0.95em;">📉 {r['% vs ATH']}% vs ATH</span>
              </div>
              <div style="margin-top:6px;font-size:1.0em;font-weight:600;">
                {r['Señal hoy']}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Detalle desplegable al tocar
        with st.expander(f"Ver detalle de {r['Ticker']}"):
            st.write(f"**Fuerza relativa vs BTC (7d):** {r['FR vs BTC']}")
            st.write(f"**Variación 7d:** {r['% 7d']}%")
            st.write("**Tramos de entrada (DCA):**")
            st.write(f"- T1: {r['T1']:.6g}")
            st.write(f"- T2: {r['T2']:.6g}")
            st.write(f"- T3: {r['T3']:.6g}")
            st.write(f"**Precio medio si entran los 3:** {r['Precio medio 3T']:.6g}")
            st.write(f"⚠️ **Invalidación (dejar de promediar):** {r['Invalidación']:.6g}")

# ===============================================================
#  SECCIÓN: ACCIONES VINCULADAS A BTC (MSTR, MARA, RIOT)
# ===============================================================
st.divider()
st.subheader("📈 Acciones vinculadas a BTC")
st.caption("Precios vía sus **tokens tokenizados** (xStocks) en CoinGecko, que cotizan "
           "24/7 y siguen a la acción real. MSTRx es líquido y fiable; MARA/RIOT "
           "tokenizados son ilíquidos, así que su precio es orientativo. "
           "MSTR lleva tramos DCA (T1/T2/T3) como las cripto; recuerda que es un proxy "
           "apalancado de BTC y amplifica los movimientos. Nada de esto es recomendación de operar.")

filas_acc = []
for tk, cg_id, cat, liquidez, tramos, inval in ACCIONES:
    precio = cg_precio(cg_id)
    hist = cg_historico(cg_id)
    rsi_v = rsi(hist) if hist else None
    dist_v = dist_media(hist) if hist else None
    # Señal de tramo DCA si la acción tiene niveles definidos
    if tramos and inval is not None and precio is not None:
        senal_dca = senal_tramo(precio, tramos, inval)
        t1, t2, t3 = tramos
    else:
        senal_dca, t1, t2, t3 = "—", None, None, None
    filas_acc.append({
        "Ticker": tk,
        "Precio": precio,
        "Fiabilidad": "✅ Alta" if liquidez == "alta" else "⚠️ Orientativo",
        "Señal DCA": senal_dca,
        "T1": t1, "T2": t2, "T3": t3,
        "RSI(14)": rsi_v,
        "% vs media50": dist_v,
        "Sobreextensión": senal_sobreextension(rsi_v, dist_v),
    })

dfa = pd.DataFrame(filas_acc)
if dfa["Precio"].notna().any():
    def color_ext(v):
        if "Muy" in str(v): return "background-color:#5a1e1e;color:#fff"
        if "Algo" in str(v): return "background-color:#5a4d1e;color:#fff"
        return ""
    def color_dca(v):
        if "T3" in str(v) or "T2" in str(v): return "background-color:#1e4620;color:#fff"
        if "T1" in str(v): return "background-color:#5a4d1e;color:#fff"
        if "STOP" in str(v): return "background-color:#5a1e1e;color:#fff"
        return ""
    st.dataframe(
        dfa.style.map(color_ext, subset=["Sobreextensión"]).map(color_dca, subset=["Señal DCA"]),
        use_container_width=True, hide_index=True,
    )
    st.caption("**Señal DCA** (solo MSTR): 🟡 T1 = primera zona de compra · 🟢 T2/T3 = zonas "
               "más profundas · 🛑 STOP = bajo invalidación. **Sobreextensión:** 🔴 muy estirado, "
               "🟡 algo, ⚪ normal. Todo es contexto objetivo, no órdenes de comprar/vender ni de "
               "ponerse corto. La decisión es tuya.")
else:
    st.warning("No se pudieron cargar los precios de las acciones ahora mismo "
               "(fallo temporal de CoinGecko). Reintenta en unos minutos.")

# Descargar Excel
@st.cache_data(ttl=300)
def to_excel(_df, _dfa):
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        _df.to_excel(xl, sheet_name="Cripto_DCA", index=False)
        _dfa.to_excel(xl, sheet_name="Acciones_BTC", index=False)
    return buf.getvalue()

st.download_button(
    "⬇️ Descargar Excel",
    data=to_excel(df, dfa),
    file_name=f"crypto_dca_radar_{dt.datetime.utcnow():%Y%m%d_%H%M}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption("Las alertas a Telegram las envía el vigilante en la nube, "
           "no esta pantalla. Refresca para datos nuevos (caché 5 min).")
