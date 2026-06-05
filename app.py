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

# Descargar Excel
@st.cache_data(ttl=300)
def to_excel(_df):
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        _df.to_excel(xl, sheet_name="Plan_DCA", index=False)
    return buf.getvalue()

st.download_button(
    "⬇️ Descargar Excel",
    data=to_excel(df),
    file_name=f"crypto_dca_radar_{dt.datetime.utcnow():%Y%m%d_%H%M}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption("Las alertas a Telegram las envía el vigilante en la nube, "
           "no esta pantalla. Refresca para datos nuevos (caché 5 min).")
