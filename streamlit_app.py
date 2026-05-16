import json
import time
import html
import threading
from datetime import datetime, timedelta
 
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
 
import streamlit as st
import paho.mqtt.client as mqtt
 
 
# ============================================================
# CONFIGURACOES GERAIS
# ============================================================
 
st.set_page_config(
    page_title="Painel Next Mobilidade",
    layout="wide"
)
 
MQTT_BROKER = st.secrets["mqtt"]["broker"]
MQTT_PORT = int(st.secrets["mqtt"]["porta"])
MQTT_TOPIC = st.secrets["mqtt"]["topico"]
MQTT_USUARIO = st.secrets["mqtt"]["usuario"]
MQTT_SENHA = st.secrets["mqtt"]["senha"]
 
INTERVALO_ATUALIZACAO = 1
 
 
# ============================================================
# FUNCOES AUXILIARES
# ============================================================
 
def obter_valor(dados, chaves, padrao=None):
    for chave in chaves:
        valor = dados.get(chave)
        if valor is not None and valor != "":
            return valor
    return padrao
 
 
def agora_sao_paulo():
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
 
    return datetime.utcnow() - timedelta(hours=3)
 
 
def codigo_reason_code(reason_code):
    try:
        return int(reason_code)
    except Exception:
        texto = str(reason_code).lower()
 
        if "success" in texto or texto == "0":
            return 0
 
        return -1
 
 
def montar_subtitulo(dados):
    subtitulo = obter_valor(dados, ["subtitulo_linha"], None)
 
    if subtitulo:
        return subtitulo
 
    sentido = obter_valor(dados, ["sentido"], "")
 
    if sentido == "Terminal Diadema - Terminal Jabaquara":
        return "Linha 290 Terminal Diadema - Terminal Jabaquara"
 
    if sentido == "Terminal Jabaquara - Terminal Diadema":
        return "Linha 290 Terminal Jabaquara - Terminal Diadema"
 
    return "Linha 290 - Aguardando sentido"
 
 
def montar_parada(dados):
    parada = obter_valor(
        dados,
        ["parada_atual", "parada"],
        "Aguardando dados"
    )
 
    if not parada:
        return "Aguardando dados"
 
    return parada
 
 
def montar_coordenadas(dados):
    latitude = obter_valor(dados, ["latitude", "lat"], None)
    longitude = obter_valor(dados, ["longitude", "lon", "lng"], None)
 
    if latitude is None or longitude is None:
        return "Aguardando dados"
 
    try:
        latitude = float(latitude)
        longitude = float(longitude)
 
        return f"Latitude: {latitude:.6f}\nLongitude: {longitude:.6f}"
 
    except Exception:
        return f"Latitude: {latitude}\nLongitude: {longitude}"
 
 
def montar_data_hora(dados):
    data = obter_valor(dados, ["data"], None)
    hora = obter_valor(dados, ["hora"], None)
 
    if data and hora:
        return f"Data: {data}\nHora: {hora}"
 
    data_hora = obter_valor(dados, ["data_hora"], None)
 
    if data_hora:
        partes = str(data_hora).split(" ")
        if len(partes) >= 2:
            return f"Data: {partes[0]}\nHora: {partes[1]}"
        return str(data_hora)
 
    agora = agora_sao_paulo()
    return f"Data: {agora.strftime('%d/%m/%Y')}\nHora: {agora.strftime('%H:%M:%S')}"
 
 
def montar_velocidade(dados):
    velocidade = obter_valor(
        dados,
        ["velocidade", "velocidade_numero", "speed", "velocidade_kmh"],
        None
    )
 
    if velocidade is None:
        return "Aguardando dados"
 
    try:
        if isinstance(velocidade, str):
            if "km/h" in velocidade:
                return velocidade
 
            velocidade = velocidade.replace(",", ".").strip()
 
        return f"{int(round(float(velocidade)))} km/h"
 
    except Exception:
        return str(velocidade)
 
 
def montar_embarque(dados):
    valor = obter_valor(
        dados,
        ["embarque", "embarque_parada"],
        0
    )
 
    try:
        return str(int(valor))
    except Exception:
        return str(valor)
 
 
def montar_lotacao(dados):
    valor = obter_valor(
        dados,
        ["lotacao_atual", "lotacao", "ocupacao"],
        "Aguardando dados"
    )
 
    try:
        return str(int(valor))
    except Exception:
        return str(valor)
 
 
def exibir_card(titulo, valor):
    titulo = html.escape(str(titulo))
    valor = html.escape(str(valor)).replace("\n", "<br>")
 
    st.markdown(
        f"""
        <div class="card-next">
            <div class="card-title-next">{titulo}</div>
            <div class="card-value-next">{valor}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
 
 
# ============================================================
# MQTT
# ============================================================
 
class EstadoMQTT:
    def __init__(self):
        self.lock = threading.Lock()
        self.payload = {}
        self.erro = ""
        self.conectado = False
 
    def on_connect(self, client, userdata, flags, reason_code, properties):
        codigo = codigo_reason_code(reason_code)
 
        with self.lock:
            self.conectado = codigo == 0
            self.erro = "" if codigo == 0 else f"Falha de conexao MQTT. Codigo: {reason_code}"
 
        if codigo == 0:
            client.subscribe(MQTT_TOPIC)
 
    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        codigo = codigo_reason_code(reason_code)
 
        with self.lock:
            self.conectado = False
 
            if codigo != 0:
                self.erro = f"MQTT desconectado inesperadamente. Codigo: {reason_code}"
 
    def on_message(self, client, userdata, msg):
        try:
            texto = msg.payload.decode("utf-8")
            dados = json.loads(texto)
 
            with self.lock:
                self.payload = dados
                self.erro = ""
 
        except Exception as erro:
            with self.lock:
                self.erro = f"Erro ao ler payload MQTT: {erro}"
 
    def snapshot(self):
        with self.lock:
            return {
                "payload": dict(self.payload),
                "erro": self.erro,
                "conectado": self.conectado
            }
 
 
@st.cache_resource
def iniciar_mqtt():
    estado = EstadoMQTT()
 
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"dashboard_next_{int(time.time())}"
    )
 
    client.username_pw_set(MQTT_USUARIO, MQTT_SENHA)
    client.tls_set()
 
    client.on_connect = estado.on_connect
    client.on_disconnect = estado.on_disconnect
    client.on_message = estado.on_message
 
    client.connect_async(MQTT_BROKER, MQTT_PORT, 30)
    client.loop_start()
 
    return estado
 
 
# ============================================================
# INICIALIZACAO MQTT
# ============================================================
 
estado_mqtt = iniciar_mqtt()
snapshot = estado_mqtt.snapshot()
payload = snapshot["payload"]
 
 
# ============================================================
# DADOS DOS CARDS
# ============================================================
 
subtitulo = montar_subtitulo(payload)
parada_card = montar_parada(payload)
coordenadas_card = montar_coordenadas(payload)
data_hora_card = montar_data_hora(payload)
velocidade_card = montar_velocidade(payload)
embarque_card = montar_embarque(payload)
lotacao_card = montar_lotacao(payload)
 
 
# ============================================================
# ESTILO VISUAL
# ============================================================
 
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 3.2rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }
 
        .titulo-next {
            width: 100%;
            font-size: clamp(1.85rem, 2.6vw, 2.65rem);
            font-weight: 700;
            margin-top: 0.5rem;
            margin-bottom: 0.35rem;
            color: #31333F;
            text-align: center;
            line-height: 1.25;
            white-space: normal;
            overflow: visible;
        }
 
        .subtitulo-next {
            width: 100%;
            font-size: clamp(1rem, 1.4vw, 1.35rem);
            font-weight: 400;
            margin-bottom: 2rem;
            color: rgba(49, 51, 63, 0.78);
            text-align: center;
            line-height: 1.35;
            white-space: normal;
            overflow: visible;
        }
 
        .card-next {
            border: 3px solid rgba(49, 51, 63, 0.38);
            border-radius: 15px;
            padding: 18px 20px;
            min-height: 135px;
            margin-bottom: 16px;
            background: rgba(255, 255, 255, 0.02);
            overflow: visible;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
 
        .card-title-next {
            font-size: 1.08rem;
            font-weight: 700;
            opacity: 0.95;
            margin-bottom: 10px;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #31333F;
        }
 
        .card-value-next {
            font-size: clamp(1.18rem, 1.55vw, 1.72rem);
            font-weight: 500;
            line-height: 1.38;
            word-break: break-word;
            white-space: normal;
        }
 
        .erro-next {
            font-size: 0.90rem;
            color: #b00020;
            margin-top: 1rem;
            text-align: center;
        }
    </style>
    """,
    unsafe_allow_html=True
)
 
 
# ============================================================
# INTERFACE
# ============================================================
 
st.markdown(
    '<div class="titulo-next">Painel Next Mobilidade</div>',
    unsafe_allow_html=True
)
 
st.markdown(
    f'<div class="subtitulo-next">{html.escape(str(subtitulo))}</div>',
    unsafe_allow_html=True
)
 
col1, col2 = st.columns(2)
 
with col1:
    exibir_card("Parada", parada_card)
 
with col2:
    exibir_card("Coordenadas", coordenadas_card)
 
col3, col4 = st.columns(2)
 
with col3:
    exibir_card("Data e hora", data_hora_card)
 
with col4:
    exibir_card("Velocidade", velocidade_card)
 
col5, col6 = st.columns(2)
 
with col5:
    exibir_card("Embarque", embarque_card)
 
with col6:
    exibir_card("Lotacao Atual", lotacao_card)
 
 
# ============================================================
# ERRO TECNICO SOMENTE SE OCORRER
# ============================================================
 
if snapshot["erro"]:
    st.markdown(
        f'<div class="erro-next">{html.escape(snapshot["erro"])}</div>',
        unsafe_allow_html=True
    )
 
 
# ============================================================
# ATUALIZACAO AUTOMATICA
# ============================================================
 
time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
 
