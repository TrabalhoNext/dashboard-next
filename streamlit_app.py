
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

# Acessando segredos
MQTT_BROKER = st.secrets["mqtt"]["broker"]
MQTT_PORT = int(st.secrets["mqtt"]["porta"])
MQTT_TOPIC = st.secrets["mqtt"]["topico"]
MQTT_USUARIO = st.secrets["mqtt"]["usuario"]
MQTT_SENHA = st.secrets["mqtt"]["senha"]

INTERVALO_ATUALIZACAO = 3
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
# CLASSE DE ESTADO MQTT (CORRIGIDA)
# ============================================================

class EstadoMQTT:
    def __init__(self):
        self.lock = threading.Lock()
        self.payload = {}
        self.ultima_msg = "Aguardando dados..."
        self.erro = ""
        self.conectado = False

    def on_connect(self, client, userdata, flags, rc, props=None):
        with self.lock:
            self.conectado = (rc == 0)
        if rc == 0:
            client.subscribe(MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            dados = json.loads(msg.payload.decode())
            with self.lock:
                self.payload = dados
                self.ultima_msg = datetime.now().strftime("%H:%M:%S")
                self.erro = ""
        except Exception as e:
            with self.lock:
                self.erro = str(e)

    def snapshot(self):
        with self.lock:
            # Retorna uma cópia segura dos dados atuais
            return {
                "payload": self.payload.copy() if self.payload else {},
                "ultima_mensagem": self.ultima_msg,
                "erro": self.erro,
                "conectado": self.conectado
            }

@st.cache_resource
def iniciar_conexao_mqtt_v2(): # Renomeado para limpar o cache antigo
    est = EstadoMQTT()
    cli = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    cli.username_pw_set(MQTT_USUARIO, MQTT_SENHA)
    cli.tls_set()
    cli.on_connect = est.on_connect
    cli.on_message = est.on_message
    cli.connect_async(MQTT_BROKER, MQTT_PORT, 30)
    cli.loop_start()
    return est

# ============================================================
# LÓGICA DE CÁLCULOS
# ============================================================

def obter_valor(dados, chaves, padrao=None):
    for chave in chaves:
        valor = dados.get(chave)
        if valor is not None and valor != "": return valor
    return padrao

def converter_float(valor):
    if valor in [None, "", "Aguardando dados"]: return None
    try:
        if isinstance(valor, str):
            valor = valor.replace("km/h", "").replace("km", "").replace(",", ".").strip()
        return float(valor)
    except: return None

def calcular_distancia(lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlon/2)**2
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def calcular_progresso(lat, lon):
    lat_ref, lon_ref = PARADAS[0]["lat"], PARADAS[0]["lon"]
    def to_xy(la, lo):
        x = math.radians(lo - lon_ref) * 6371000 * math.cos(math.radians(lat_ref))
        y = math.radians(la - lat_ref) * 6371000
        return x, y
    px, py = to_xy(lat, lon)
    m_dist, m_idx, prog_acum = float("inf"), 0, 0
    m_prog = 0
    for i in range(len(PARADAS)-1):
        x1, y1 = to_xy(PARADAS[i]["lat"], PARADAS[i]["lon"])
        x2, y2 = to_xy(PARADAS[i+1]["lat"], PARADAS[i+1]["lon"])
        dx, dy = x2-x1, y2-y1
        seg_len = math.sqrt(dx**2 + dy**2)
        if seg_len == 0: continue
        t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / (seg_len**2)))
        dist = math.sqrt((px-(x1+t*dx))**2 + (py-(y1+t*dy))**2)
        if dist < m_dist:
            m_dist, m_idx = dist, i
            m_prog = prog_acum + (t*seg_len)
        prog_acum += seg_len
    return f"Entre {PARADAS[m_idx]['nome']} e {PARADAS[m_idx+1]['nome']}", m_idx, m_prog

# ============================================================
# EXECUÇÃO DO DASHBOARD
# ============================================================

# Inicializa Session State
if "sentido_atual" not in st.session_state: st.session_state.sentido_atual = "Aguardando..."
if "term_ref" not in st.session_state: st.session_state.term_ref = None

# Obtém dados do MQTT
est_mqtt = iniciar_conexao_mqtt_v2()
snap = est_mqtt.snapshot() # Chama o método da classe EstadoMQTT
payload = snap["payload"]

# Extração de dados
lat = converter_float(obter_valor(payload, ["lat", "latitude"]))
lon = converter_float(obter_valor(payload, ["lon", "longitude"]))
vel = int(round(converter_float(obter_valor(payload, ["speed", "velocidade"])) or 0))

# Lógica operacional
if lat and lon:
    trecho, idx, prog = calcular_progresso(lat, lon)
    
    # Sentido simplificado para evitar erros
    d_diadema = calcular_distancia(lat, lon, PARADAS[0]["lat"], PARADAS[0]["lon"])
    d_jabaquara = calcular_distancia(lat, lon, PARADAS[-1]["lat"], PARADAS[-1]["lon"])
    
    if d_diadema < 20: st.session_state.sentido_atual = "Sentido Jabaquara"
    if d_jabaquara < 20: st.session_state.sentido_atual = "Sentido Diadema"
    
    proxima = PARADAS[idx+1]["nome"] if "Jabaquara" in st.session_state.sentido_atual else PARADAS[idx]["nome"]
else:
    trecho = proxima = "Aguardando GPS..."

# Interface Visual
st.markdown("""
    <style>
        .card-next {
            border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 10px;
            padding: 15px; background: rgba(255, 255, 255, 0.02); height: 100px;
        }
        .card-title { font-size: 0.8rem; opacity: 0.7; text-transform: uppercase; }
        .card-val { font-size: 1.2rem; font-weight: bold; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("Painel de Controle Next Mobilidade | Linha 290")

def draw_card(title, val):
    st.markdown(f"<div class='card-next'><div class='card-title'>{title}</div><div class='card-val'>{val}</div></div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1: draw_card("Sentido", st.session_state.sentido_atual)
with c2: draw_card("Velocidade", f"{vel} km/h")
with c3: draw_card("Última Atualização", snap["ultima_mensagem"])

c4, c5, c6 = st.columns(3)
with c4: draw_card("Trecho Atual", trecho)
with c5: draw_card("Próxima Parada", proxima)
with c6: draw_card("Lotação", obter_valor(payload, ["lotacao"], "---"))

st.subheader("Visualização Geográfica")
col_map, col_list = st.columns([2, 1])

with col_map:
    centro = [lat, lon] if lat else [-23.66, -46.63]
    m = folium.Map(location=centro, zoom_start=14)
    folium.PolyLine([(p["lat"], p["lon"]) for p in PARADAS], color="blue", weight=3, opacity=0.5).add_to(m)
    if lat:
        folium.Marker([lat, lon], popup="Ônibus", icon=folium.Icon(color="blue", icon="bus", prefix="fa")).add_to(m)
    st_folium(m, width="100%", height=400, returned_objects=[])

with col_list:
    st.dataframe(pd.DataFrame([p["nome"] for p in PARADAS], columns=["Itinerário"]), use_container_width=True, hide_index=True)

with st.expander("Dados Brutos (Debug)"):
    st.write(f"Conectado: {snap['conectado']}")
    st.json(payload)

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
