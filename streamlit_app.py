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
# CONFIGURAÇÕES GERAIS
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
# FUNÇÕES AUXILIARES
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
    subtitulo = obter_valor(
        dados,
        ["subtitulo_linha"],
        None
    )

    if subtitulo:
        return subtitulo

    sentido = obter_valor(
        dados,
        ["sentido"],
        ""
    )

    if sentido == "Terminal Diadema - Terminal Jabaquara":
        return "Linha 290 Terminal Diadema - Terminal Jabaquara"

    if sentido == "Terminal Jabaquara - Terminal Diadema":
        return "Linha 290 Terminal Jabaquara - Terminal Diadema"

    return "Linha 290"


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
    coordenadas = obter_valor(
        dados,
        ["coordenadas"],
        None
    )

    if coordenadas:
        return coordenadas

    latitude = obter_valor(dados, ["latitude", "lat"], None)
    longitude = obter_valor(dados, ["longitude", "lon", "lng"], None)

    if latitude is None or longitude is None:
        return "Aguardando dados"

    try:
        latitude = float(latitude)
        longitude = float(longitude)

        return f"Lat: {latitude:.6f}\nLon: {longitude:.6f}"

    except Exception:
        return f"{latitude}, {longitude}"


def montar_data_hora(dados):
    data_hora = obter_valor(
        dados,
        ["data_hora"],
        None
    )

    if data_hora:
        return data_hora

    data = obter_valor(dados, ["data"], None)
    hora = obter_valor(dados, ["hora"], None)

    if data and hora:
        return f"{data} {hora}"

    return agora_sao_paulo().strftime("%d/%m/%Y %H:%M:%S")


def montar_embarque(dados):
    valor = obter_valor(
        dados,
        ["embarque", "embarques_total", "total_ciclo_final"],
        0
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
        self.ultima_mensagem = "Aguardando dados"
        self.erro = ""
        self.conectado = False

    def on_connect(self, client, userdata, flags, reason_code, properties):
        codigo = codigo_reason_code(reason_code)

        with self.lock:
            self.conectado = codigo == 0

            if codigo == 0:
                self.erro = ""
            else:
                self.erro = f"Falha de conexão MQTT. Código: {reason_code}"

        if codigo == 0:
            client.subscribe(MQTT_TOPIC)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        codigo = codigo_reason_code(reason_code)

        with self.lock:
            self.conectado = False

            if codigo != 0:
                self.erro = f"MQTT desconectado inesperadamente. Código: {reason_code}"

    def on_message(self, client, userdata, msg):
        try:
            texto = msg.payload.decode("utf-8")
            dados = json.loads(texto)

            with self.lock:
                self.payload = dados
                self.ultima_mensagem = agora_sao_paulo().strftime("%d/%m/%Y %H:%M:%S")
                self.erro = ""

        except Exception as erro:
            with self.lock:
                self.erro = f"Erro ao ler payload MQTT: {erro}"

    def snapshot(self):
        with self.lock:
            return {
                "payload": dict(self.payload),
                "ultima_mensagem": self.ultima_mensagem,
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
# INICIALIZAÇÃO MQTT
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
embarque_card = montar_embarque(payload)


# ============================================================
# ESTILO VISUAL
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        .titulo-next {
            font-size: 2.4rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
            color: #31333F;
            text-align: center;
        }

        .subtitulo-next {
            font-size: 1.15rem;
            font-weight: 400;
            margin-bottom: 1.8rem;
            color: rgba(49, 51, 63, 0.78);
            text-align: center;
        }

        .card-next {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 14px;
            padding: 16px 18px;
            height: 125px;
            max-height: 125px;
            margin-bottom: 14px;
            background: rgba(255, 255, 255, 0.02);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }

        .card-title-next {
            font-size: 0.85rem;
            opacity: 0.75;
            margin-bottom: 7px;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .card-value-next {
            font-size: clamp(1.05rem, 1.35vw, 1.45rem);
            font-weight: 500;
            line-height: 1.22;
            word-break: break-word;
            white-space: normal;
        }

        .status-next {
            font-size: 0.80rem;
            color: rgba(49, 51, 63, 0.62);
            margin-top: 1.2rem;
            text-align: center;
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
    exibir_card("Embarque", embarque_card)


# ============================================================
# STATUS TÉCNICO DISCRETO
# ============================================================

if snapshot["erro"]:
    st.markdown(
        f'<div class="erro-next">{html.escape(snapshot["erro"])}</div>',
        unsafe_allow_html=True
    )
else:
    status = "conectado" if snapshot["conectado"] else "conectando"
    ultima = snapshot["ultima_mensagem"]

    st.markdown(
        f'<div class="status-next">MQTT: {status} | Última mensagem: {html.escape(str(ultima))}</div>',
        unsafe_allow_html=True
    )


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
