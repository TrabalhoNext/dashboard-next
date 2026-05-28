import json
import time
import html
import ssl
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

PARADA_FIXA = "Fatec São Bernardo do Campo - Adib Moisés Dib"
LATITUDE_FIXA = "-23.69579"
LONGITUDE_FIXA = "-46.54645"

INTERVALO_ATUALIZACAO = 3


# ============================================================
# LEITURA SEGURA DOS SECRETS DO STREAMLIT
# ============================================================

def ler_secret_mqtt(nome, padrao=None):
    """
    Lê os dados MQTT do secrets.toml.

    Aceita os dois formatos:

    [mqtt]
    broker = ""
    porta = 8883
    usuario = ""
    senha = ""
    topico = ""

    ou

    [mqtt]
    broker = ""
    port = 8883
    user = ""
    password = ""
    topic = ""
    """

    alternativas = {
        "broker": ["broker", "MQTT_BROKER"],
        "porta": ["porta", "port", "MQTT_PORT"],
        "usuario": ["usuario", "user", "MQTT_USUARIO", "MQTT_USERNAME"],
        "senha": ["senha", "password", "MQTT_SENHA", "MQTT_PASSWORD"],
        "topico": ["topico", "topic", "MQTT_TOPIC"],
    }

    for chave in alternativas.get(nome, [nome]):
        try:
            if "mqtt" in st.secrets and chave in st.secrets["mqtt"]:
                return st.secrets["mqtt"][chave]
        except Exception:
            pass

    for chave in alternativas.get(nome, [nome]):
        try:
            return st.secrets[chave]
        except Exception:
            pass

    return padrao


MQTT_BROKER = str(
    ler_secret_mqtt(
        "broker",
        "5031204390404922a3a816878ccfd1f4.s1.eu.hivemq.cloud"
    )
).strip()

MQTT_PORT = int(ler_secret_mqtt("porta", 8883))
MQTT_TOPIC = str(ler_secret_mqtt("topico", "next/linha290/gps")).strip()
MQTT_USUARIO = str(ler_secret_mqtt("usuario", "Linha290")).strip()
MQTT_SENHA = str(ler_secret_mqtt("senha", "")).strip()


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


def montar_parada():
    return PARADA_FIXA


def montar_coordenadas():
    return f"Latitude: {LATITUDE_FIXA}\nLongitude: {LONGITUDE_FIXA}"

def montar_data_hora():
    agora = agora_sao_paulo()
    return f"Data: {agora.strftime('%d/%m/%Y')}\nHora: {agora.strftime('%H:%M:%S')}"


def montar_embarque(dados):
    valor = obter_valor(
        dados,
        ["embarque", "embarque_parada", "deteccao", "pessoas_detectadas"],
        0
    )

    try:
        return str(int(valor))
    except Exception:
        return str(valor)


def montar_lotacao(dados):
    valor = obter_valor(
        dados,
        ["lotacao_atual", "lotacao", "ocupacao", "lotacao_acumulada"],
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
        self.erro = ""
        self.conectado = False
        self.client = None

    def on_connect(self, client, userdata, flags, reason_code=None, properties=None):
        codigo = codigo_reason_code(reason_code)

        with self.lock:
            self.conectado = codigo == 0
            self.erro = "" if codigo == 0 else f"Falha de conexao MQTT. Codigo: {reason_code}"

        if codigo == 0:
            client.subscribe(MQTT_TOPIC)

    def on_disconnect(self, client, userdata, *args):
        reason_code = 0

        if len(args) == 1:
            reason_code = args[0]
        elif len(args) >= 2:
            reason_code = args[1]

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
                "conectado": self.conectado,
            }


@st.cache_resource
def iniciar_mqtt():
    estado = EstadoMQTT()

    if not MQTT_BROKER:
        estado.erro = "Broker MQTT nao configurado no secrets.toml."
        return estado

    if not MQTT_USUARIO or not MQTT_SENHA:
        estado.erro = "Usuario ou senha MQTT nao configurados no secrets.toml."
        return estado

    try:
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
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

        client.on_connect = estado.on_connect
        client.on_disconnect = estado.on_disconnect
        client.on_message = estado.on_message

        client.reconnect_delay_set(min_delay=1, max_delay=30)

        client.connect_async(MQTT_BROKER, MQTT_PORT, 30)
        client.loop_start()

        estado.client = client

    except Exception as erro:
        estado.erro = f"Erro ao iniciar MQTT no dashboard: {erro}"

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

parada_card = montar_parada()
coordenadas_card = montar_coordenadas()
data_hora_card = montar_data_hora()
embarque_card = montar_embarque(payload)
lotacao_card = montar_lotacao(payload)


# ============================================================
# ESTILO VISUAL ORIGINAL
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
    '<div class="subtitulo-next">Linha 290</div>',
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

col5, col6 = st.columns(2)

with col5:
    exibir_card("Lotação Atual", lotacao_card)

with col6:
    st.empty()


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
