import json
import time
import math
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

INTERVALO_ATUALIZACAO = 3
RAIO_PARADA_METROS = 10


# ============================================================
# PARADAS DA LINHA 290
# FORMATO: LATITUDE, LONGITUDE
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


def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    raio_terra = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return raio_terra * c


def identificar_parada(latitude, longitude):
    if latitude is None or longitude is None:
        return "Aguardando dados"

    menor_distancia = float("inf")
    parada_mais_proxima = None

    for parada in PARADAS:
        distancia = calcular_distancia_metros(
            latitude,
            longitude,
            parada["lat"],
            parada["lon"]
        )

        if distancia < menor_distancia:
            menor_distancia = distancia
            parada_mais_proxima = parada

    if parada_mais_proxima is not None and menor_distancia <= RAIO_PARADA_METROS:
        return parada_mais_proxima["nome"]

    return "Em rota"


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
# LEITURA DO PAYLOAD MQTT
# ============================================================

latitude = converter_float(
    obter_valor(payload, ["latitude", "lat"])
)

longitude = converter_float(
    obter_valor(payload, ["longitude", "lon", "lng"])
)

velocidade_float = converter_float(
    obter_valor(payload, ["velocidade", "speed", "velocidade_kmh"])
)


# ============================================================
# DADOS DOS CARDS
# ============================================================

parada_card = identificar_parada(latitude, longitude)

data_hora_card = agora_sao_paulo().strftime("%d/%m/%Y %H:%M:%S")

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
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        .titulo-next {
            font-size: 2.4rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: #31333F;
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
# ORDEM: PARADA, DATA/HORA, LATITUDE/LONGITUDE, VELOCIDADE
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
