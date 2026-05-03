import json
import time
import math
import html
import threading
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
import folium
from streamlit_folium import st_folium


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

st.set_page_config(
    page_title="Painel de Controle Next Mobilidade",
    layout="wide"
)

MQTT_BROKER = st.secrets["mqtt"]["broker"]
MQTT_PORT = int(st.secrets["mqtt"]["porta"])
MQTT_TOPIC = st.secrets["mqtt"]["topico"]
MQTT_USUARIO = st.secrets["mqtt"]["usuario"]
MQTT_SENHA = st.secrets["mqtt"]["senha"]

INTERVALO_ATUALIZACAO = 3

RAIO_PARADA_ATUAL_METROS = 15
RAIO_SAIDA_TERMINAL_METROS = 10
VELOCIDADE_MINIMA_SENTIDO = 2


# ============================================================
# PARADAS DA LINHA 290
# ============================================================

PARADAS = [
    {"nome": "Terminal Diadema", "lat": -23.682681458564325, "lon": -46.62691332328152},
    {"nome": "Parada Assembleia", "lat": -23.67697409771605, "lon": -46.627793033156586},
    {"nome": "Parada Divisa", "lat": -23.673551659194004, "lon": -46.63089933449298},
    {"nome": "Parada Vila Clara", "lat": -23.670446876785558, "lon": -46.63259010672355},
    {"nome": "Parada Bom Clima", "lat": -23.669120531442708, "lon": -46.63486429031358},
    {"nome": "Parada São José", "lat": -23.664882066923965, "lon": -46.63779830145058},
    {"nome": "Parada Americanópolis", "lat": -23.66095067269106, "lon": -46.637240408622645},
    {"nome": "Parada Faccini", "lat": -23.656897096071692, "lon": -46.63611395876546},
    {"nome": "Parada Encontro", "lat": -23.652614165456484, "lon": -46.63710571915031},
    {"nome": "Parada Cidade Vargas", "lat": -23.648791349310596, "lon": -46.64064538509645},
    {"nome": "Terminal Jabaquara", "lat": -23.646183664190886, "lon": -46.639878302287805},
]


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def obter_valor(dados, chaves, padrao=None):
    for chave in chaves:
        valor = dados.get(chave)
        if valor is not None and valor != "":
            return valor
    return padrao

def converter_float(valor):
    if valor in [None, "", "Aguardando dados"]:
        return None
    try:
        if isinstance(valor, str):
            valor = valor.replace("km/h", "").replace("km", "").replace("°", "").replace(",", ".").strip()
        return float(valor)
    except:
        return None

def ajustar_data_hora(data_valor, hora_valor):
    if not data_valor: data_valor = "Aguardando dados"
    if not hora_valor: hora_valor = "Aguardando dados"
    try:
        hora_texto = str(hora_valor).strip()
        if "T" in hora_texto:
            dt = datetime.fromisoformat(hora_texto.replace("Z", "+00:00"))
            tz = ZoneInfo("America/Sao_Paulo") if ZoneInfo else timezone(timedelta(hours=-3))
            dt = dt.astimezone(tz)
            return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M:%S")
        return str(data_valor), str(hora_valor)
    except:
        return str(data_valor), str(hora_valor)

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlon/2)**2
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def calcular_progresso_rota(lat, lon):
    lat_ref, lon_ref = PARADAS[0]["lat"], PARADAS[0]["lon"]
    def to_xy(la, lo):
        x = math.radians(lo - lon_ref) * 6371000 * math.cos(math.radians(lat_ref))
        y = math.radians(la - lat_ref) * 6371000
        return x, y
    px, py = to_xy(lat, lon)
    melhor_dist, melhor_idx, prog_acumulado, melhor_prog = float("inf"), 0, 0, 0
    for i in range(len(PARADAS)-1):
        x1, y1 = to_xy(PARADAS[i]["lat"], PARADAS[i]["lon"])
        x2, y2 = to_xy(PARADAS[i+1]["lat"], PARADAS[i+1]["lon"])
        dx, dy = x2-x1, y2-y1
        seg_len = math.sqrt(dx**2 + dy**2)
        if seg_len == 0: continue
        t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / (seg_len**2)))
        dist = math.sqrt((px-(x1+t*dx))**2 + (py-(y1+t*dy))**2)
        if dist < melhor_dist:
            melhor_dist, melhor_idx, melhor_prog = dist, i, prog_acumulado + (t*seg_len)
        prog_acumulado += seg_len
    return f"Entre {PARADAS[melhor_idx]['nome']} e {PARADAS[melhor_idx+1]['nome']}", melhor_idx, melhor_prog

def identificar_sentido(lat, lon, prog_atual, idx_trecho, heading, vel):
    # Lógica de Terminais
    d_diadema = calcular_distancia_metros(lat, lon, PARADAS[0]["lat"], PARADAS[0]["lon"])
    d_jabaquara = calcular_distancia_metros(lat, lon, PARADAS[-1]["lat"], PARADAS[-1]["lon"])
    
    if d_diadema <= RAIO_SAIDA_TERMINAL_METROS:
        st.session_state.terminal_referencia, st.session_state.sentido_atual = "diadema", "Aguardando saída do Terminal Diadema"
    elif d_jabaquara <= RAIO_SAIDA_TERMINAL_METROS:
        st.session_state.terminal_referencia, st.session_state.sentido_atual = "jabaquara", "Aguardando saída do Terminal Jabaquara"
    
    # Saída do Terminal
    ref = st.session_state.get("terminal_referencia")
    if ref == "diadema" and d_diadema > RAIO_SAIDA_TERMINAL_METROS: st.session_state.sentido_atual = "Sentido Jabaquara"
    elif ref == "jabaquara" and d_jabaquara > RAIO_SAIDA_TERMINAL_METROS: st.session_state.sentido_atual = "Sentido Diadema"

    # Heading (Se disponível e em movimento)
    if heading is not None and vel >= VELOCIDADE_MINIMA_SENTIDO and 0 <= idx_trecho < len(PARADAS)-1:
        def bearing(l1, o1, l2, o2):
            l1r, l2r = math.radians(l1), math.radians(l2)
            dl = math.radians(o2-o1)
            x = math.sin(dl) * math.cos(l2r)
            y = math.cos(l1r)*math.sin(l2r) - math.sin(l1r)*math.cos(l2r)*math.cos(dl)
            return math.degrees(math.atan2(x, y)) % 360
        b_jab = bearing(PARADAS[idx_trecho]["lat"], PARADAS[idx_trecho]["lon"], PARADAS[idx_trecho+1]["lat"], PARADAS[idx_trecho+1]["lon"])
        diff_jab = abs((heading - b_jab + 180) % 360 - 180)
        if diff_jab <= 75: st.session_state.sentido_atual = "Sentido Jabaquara"
        elif diff_jab >= 105: st.session_state.sentido_atual = "Sentido Diadema"

    return st.session_state.get("sentido_atual", "Aguardando deslocamento")

def exibir_card(titulo, valor):
    st.markdown(f"""
        <div class="card-next">
            <div class="card-title-next">{html.escape(str(titulo))}</div>
            <div class="card-value-next">{html.escape(str(valor)).replace('\n', '<br>')}</div>
        </div>
    """, unsafe_allow_html=True)


# ============================================================
# MQTT
# ============================================================

class EstadoMQTT:
    def __init__(self):
        self.lock = threading.Lock()
        self.payload, self.ultima_msg, self.erro, self.conectado = {}, "Aguardando dados", "", False

    def on_connect(self, client, userdata, flags, rc, props):
        with self.lock: self.conectado = (rc == 0)
        if rc == 0: client.subscribe(MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            dados = json.loads(msg.payload.decode())
            with self.lock:
                self.payload, self.erro = dados, ""
                self.ultima_msg = datetime.now().strftime("%H:%M:%S")
        except Exception as e: self.erro = str(e)

@st.cache_resource
def iniciar_mqtt():
    est = EstadoMQTT()
    cli = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    cli.username_pw_set(MQTT_USUARIO, MQTT_SENHA)
    cli.tls_set()
    cli.on_connect, cli.on_message = est.on_connect, est.on_message
    cli.connect_async(MQTT_BROKER, MQTT_PORT, 30)
    cli.loop_start()
    return est


# ============================================================
# EXECUÇÃO E INTERFACE
# ============================================================

# Session State
for key in ["progresso_rota_anterior", "sentido_atual", "terminal_referencia"]:
    if key not in st.session_state: st.session_state[key] = None

est_mqtt = iniciar_mqtt()
snap = est_mqtt.snapshot()
payload = snap["payload"]

# Processamento de Dados
lat = converter_float(obter_valor(payload, ["lat", "latitude"]))
lon = converter_float(obter_valor(payload, ["lon", "longitude", "lng"]))
vel = int(round(converter_float(obter_valor(payload, ["speed", "velocidade"])) or 0))
head = converter_float(obter_valor(payload, ["heading", "course", "direcao"]))
data, hora = ajustar_data_hora(obter_valor(payload, ["data"]), obter_valor(payload, ["hora", "time"]))

# Lógica de Rota
if lat and lon:
    trecho, idx_trecho, prog = calcular_progresso_rota(lat, lon)
    sentido = identificar_sentido(lat, lon, prog, idx_trecho, head, vel)
    st.session_state.progresso_rota_anterior = prog
    
    # Próxima Parada
    if "Jabaquara" in sentido and idx_trecho < len(PARADAS)-1:
        proxima = PARADAS[idx_trecho+1]["nome"]
    elif "Diadema" in sentido and idx_trecho > 0:
        proxima = PARADAS[idx_trecho]["nome"]
    else:
        proxima = "Calculando..."
else:
    trecho = sentido = proxima = "Aguardando dados"

# CSS
st.markdown("""
    <style>
        .block-container { padding-top: 1.2rem; }
        .card-next {
            border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 12px;
            padding: 12px; height: 100px; background: rgba(255, 255, 255, 0.02);
            display: flex; flex-direction: column; justify-content: center;
        }
        .card-title-next { font-size: 0.8rem; opacity: 0.7; margin-bottom: 4px; text-transform: uppercase; }
        .card-value-next { font-size: 1.1rem; font-weight: 600; color: #f0f2f6; }
    </style>
""", unsafe_allow_html=True)

st.title("Painel de Controle Next Mobilidade | Linha 290")

# Grade de Cards (3x3)
c1, c2, c3 = st.columns(3)
with c1: exibir_card("Sentido Atual", sentido)
with c2: exibir_card("Velocidade", f"{vel} km/h")
with c3: exibir_card("Data e Hora", f"{data} {hora}")

c4, c5, c6 = st.columns(3)
with c4: exibir_card("Trecho da Via", trecho)
with c5: exibir_card("Próxima Parada", proxima)
with c6: exibir_card("Lotação", obter_valor(payload, ["lotacao"], "Aguardando..."))

# Tabela e Mapa
st.subheader("Operação em Tempo Real")
col_map, col_tab = st.columns([2, 1])

with col_map:
    m = folium.Map(location=[lat, lon] if lat else [-23.66, -46.63], zoom_start=15)
    folium.PolyLine([(p["lat"], p["lon"]) for p in PARADAS], color="#2E86C1", weight=4, opacity=0.6).add_to(m)
    for p in PARADAS: folium.CircleMarker([p["lat"], p["lon"]], radius=3, color="white", fill=True).add_to(m)
    if lat: folium.Marker([lat, lon], popup=f"Ônibus: {lat},{lon}", icon=folium.Icon(color="blue", icon="bus", prefix="fa")).add_to(m)
    st_folium(m, width="100%", height=400, returned_objects=[])

with col_tab:
    df = pd.DataFrame([{"Parada": p["nome"], "Status": "Ok"} for p in PARADAS])
    st.dataframe(df, use_container_width=True, hide_index=True, height=400)

# Footer Técnico
with st.expander("Diagnóstico MQTT"):
    st.json(snap)

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
