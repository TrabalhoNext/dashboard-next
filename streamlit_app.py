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
# DASHBOARD NEXT MOBILIDADE
# SOMENTE 4 CARDS:
# PARADA, DATA/HORA, LATITUDE/LONGITUDE, VELOCIDADE
# ============================================================


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

def obter_valor(dados, chaves, padrao="Aguardando dados"):
    for chave in chaves:
        valor = dados.get(chave)
        if valor is not None and valor != "":
            return valor
    return padrao


def converter_float(valor):
    if valor is None or valor == "":
        return None

    try:
        if isinstance(valor, str):
            valor = (
                valor.replace("km/h", "")
                .replace("km", "")
                .replace(",", ".")
                .strip()
            )
        return float(valor)
    except Exception:
        return None


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

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        codigo = codigo_reason_code(reason_code)

        with self.lock:
            self.conectado = codigo == 0
            self.erro = "" if codigo == 0 else f"Falha MQTT. Código: {reason_code}"

        if codigo == 0:
            client.subscribe(MQTT_TOPIC)

    def on_disconnect(self, client, userdata, *args):
        with self.lock:
            self.conectado = False

    def on_message(self, client, userdata, msg):
        try:
            texto = msg.payload.decode("utf-8")
            dados = json.loads(texto)

            with self.lock:
                self.payload = dados
                self.erro = ""

        except Exception as erro:
            with self.lock:
                self.erro = str(erro)

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

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"dashboard_next_{int(time.time())}"
        )
    except Exception:
        client = mqtt.Client(
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
# LEITURA DOS DADOS RECEBIDOS DO MQTT
# ============================================================

parada_card = obter_valor(
    payload,
    ["parada_atual", "parada"],
    "Aguardando dados"
)

data = obter_valor(
    payload,
    ["data"],
    ""
)

hora = obter_valor(
    payload,
    ["hora"],
    ""
)

latitude = converter_float(
    obter_valor(payload, ["latitude", "lat"], None)
)

longitude = converter_float(
    obter_valor(payload, ["longitude", "lon", "lng"], None)
)

velocidade_float = converter_float(
    obter_valor(payload, ["velocidade", "speed", "velocidade_kmh"], None)
)


# ============================================================
# FORMATAÇÃO DOS CARDS
# ============================================================

if data != "" and hora != "":
    data_hora_card = f"{data} {hora}"
else:
    data_hora_card = "Aguardando dados"

if latitude is not None and longitude is not None:
    latitude_longitude_card = f"Lat: {latitude:.6f}\nLon: {longitude:.6f}"
else:
    latitude_longitude_card = "Aguardando dados"

if velocidade_float is not None:
    velocidade_card = f"{int(round(velocidade_float))} km/h"
else:
    velocidade_card = "Aguardando dados"


# ============================================================
# ESTILO VISUAL
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 3.2rem;
            padding-bottom: 2rem;
        }

        .titulo-next {
            font-size: 2.4rem;
            font-weight: 700;
            margin-bottom: 1.8rem;
            color: #31333F;
            line-height: 1.3;
            padding-top: 0.4rem;
            overflow: visible;
        }

        .card-next {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 14px;
            padding: 16px 18px;
            height: 120px;
            max-height: 120px;
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
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# INTERFACE
# SOMENTE 4 CARDS
# ============================================================

st.markdown(
    '<div class="titulo-next">Painel Next Mobilidade</div>',
    unsafe_allow_html=True
)

col1, col2 = st.columns(2)

with col1:
    exibir_card("Parada", parada_card)

with col2:
    exibir_card("Data e Hora", data_hora_card)

col3, col4 = st.columns(2)

with col3:
    exibir_card("Latitude / Longitude", latitude_longitude_card)

with col4:
    exibir_card("Velocidade", velocidade_card)


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
