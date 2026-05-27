import json
import ssl
import time
import threading
from datetime import datetime

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


# ============================================================
# CONFIGURAÇÃO DO DASHBOARD - BANCA NEXT MOBILIDADE
# ============================================================

PARADA = "Fatec São Bernardo do Campo - Adib Moisés Dib"
LATITUDE = -23.69579
LONGITUDE = -46.54645

INTERVALO_ATUALIZACAO_SEGUNDOS = 3


# ============================================================
# MQTT / HIVEMQ
#
# No GitHub, não coloque senha diretamente no código.
# Configure a senha no Streamlit Cloud em:
# App > Settings > Secrets
#
# Exemplo de secrets:
#
# [mqtt]
# broker = "5031204390404922a3a816878ccfd1f4.s1.eu.hivemq.cloud"
# port = 8883
# user = "Linha290"
# password = "SUA_SENHA_DO_HIVEMQ"
# topic = "next/linha290/gps"
# ============================================================

def ler_secret(secao, chave, padrao=""):
    try:
        return st.secrets.get(secao, {}).get(chave, padrao)
    except Exception:
        return padrao


MQTT_BROKER = ler_secret(
    "mqtt",
    "broker",
    "5031204390404922a3a816878ccfd1f4.s1.eu.hivemq.cloud",
)

MQTT_PORT = int(ler_secret("mqtt", "port", 8883))
MQTT_USER = ler_secret("mqtt", "user", "Linha290")
MQTT_PASSWORD = ler_secret("mqtt", "password", "")
MQTT_TOPIC = ler_secret("mqtt", "topic", "next/linha290/gps")


# ============================================================
# FUNÇÕES DE APOIO
# ============================================================

def agora_brasil():
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))

    return datetime.now()


def campo_nao_configurado(valor):
    if valor is None:
        return True

    texto = str(valor).strip()

    if texto == "":
        return True

    marcadores = [
        "SEU_",
        "SUA_",
        "COLE_AQUI",
        "PREENCHA",
        "COLOQUE",
    ]

    return any(marcador in texto for marcador in marcadores)


def mqtt_configurado():
    campos = [
        MQTT_BROKER,
        MQTT_USER,
        MQTT_PASSWORD,
        MQTT_TOPIC,
    ]

    return not any(campo_nao_configurado(campo) for campo in campos)


# ============================================================
# CLIENTE MQTT EM SEGUNDO PLANO
# ============================================================

class MQTTDashboardClient:
    def __init__(self, broker, port, user, password, topic):
        self.broker = broker
        self.port = port
        self.user = user
        self.password = password
        self.topic = topic

        self.lock = threading.Lock()

        self.dados = {
            "embarque": 0,
            "lotacao": 0,
            "ultima_mensagem": None,
            "payload_bruto": "",
            "conectado": False,
            "status": "Aguardando conexão com o HiveMQ",
        }

        self.client = mqtt.Client(
            client_id=f"dashboard_next_banca_{int(time.time())}"
        )

        self.client.username_pw_set(self.user, self.password)
        self.client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.iniciar()

    def iniciar(self):
        try:
            self.client.connect_async(
                self.broker,
                self.port,
                keepalive=60,
            )
            self.client.loop_start()

            with self.lock:
                self.dados["status"] = "Conectando ao HiveMQ..."

        except Exception as erro:
            with self.lock:
                self.dados["conectado"] = False
                self.dados["status"] = f"Erro ao conectar ao HiveMQ: {erro}"

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(self.topic, qos=1)

            with self.lock:
                self.dados["conectado"] = True
                self.dados["status"] = f"Conectado ao HiveMQ | Tópico: {self.topic}"
        else:
            with self.lock:
                self.dados["conectado"] = False
                self.dados["status"] = f"Falha na conexão MQTT. Código: {rc}"

    def on_disconnect(self, client, userdata, rc, properties=None):
        with self.lock:
            self.dados["conectado"] = False
            self.dados["status"] = "Desconectado do HiveMQ"

    def on_message(self, client, userdata, msg):
        try:
            payload_texto = msg.payload.decode("utf-8")
            payload = json.loads(payload_texto)

            embarque = int(payload.get("embarque", 0))
            lotacao = int(payload.get("lotacao", 0))

            instante = agora_brasil().strftime("%d/%m/%Y %H:%M:%S")

            with self.lock:
                self.dados["embarque"] = embarque
                self.dados["lotacao"] = lotacao
                self.dados["ultima_mensagem"] = instante
                self.dados["payload_bruto"] = payload_texto
                self.dados["conectado"] = True
                self.dados["status"] = f"Mensagem recebida em {instante}"

        except Exception as erro:
            with self.lock:
                self.dados["status"] = f"Erro ao processar mensagem MQTT: {erro}"

    def obter_dados(self):
        with self.lock:
            return dict(self.dados)


@st.cache_resource
def obter_cliente_mqtt(broker, port, user, password, topic):
    return MQTTDashboardClient(
        broker=broker,
        port=port,
        user=user,
        password=password,
        topic=topic,
    )


# ============================================================
# CONFIGURAÇÃO VISUAL
# ============================================================

st.set_page_config(
    page_title="Painel de Controle Next Mobilidade",
    page_icon="🚌",
    layout="wide",
)


st.markdown(
    """
    <style>
        .main {
            background-color: #f5f6fa;
        }

        .titulo-principal {
            font-size: 34px;
            font-weight: 800;
            color: #111827;
            margin-bottom: 0px;
        }

        .subtitulo {
            font-size: 18px;
            color: #4b5563;
            margin-top: 0px;
            margin-bottom: 25px;
        }

        .card {
            background-color: white;
            padding: 22px;
            border-radius: 18px;
            border: 1px solid #e5e7eb;
            box-shadow: 0px 4px 14px rgba(0, 0, 0, 0.06);
            min-height: 135px;
        }

        .card-titulo {
            font-size: 15px;
            color: #6b7280;
            font-weight: 700;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .card-valor {
            font-size: 30px;
            color: #111827;
            font-weight: 800;
            line-height: 1.15;
        }

        .card-valor-menor {
            font-size: 22px;
            color: #111827;
            font-weight: 700;
            line-height: 1.25;
        }

        .status-ok {
            background-color: #ecfdf5;
            color: #065f46;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid #a7f3d0;
            font-weight: 600;
        }

        .status-alerta {
            background-color: #fffbeb;
            color: #92400e;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid #fde68a;
            font-weight: 600;
        }

        .rodape {
            color: #6b7280;
            font-size: 13px;
            margin-top: 20px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LEITURA MQTT
# ============================================================

if mqtt_configurado():
    cliente_mqtt = obter_cliente_mqtt(
        MQTT_BROKER,
        MQTT_PORT,
        MQTT_USER,
        MQTT_PASSWORD,
        MQTT_TOPIC,
    )
    dados = cliente_mqtt.obter_dados()
else:
    dados = {
        "embarque": 0,
        "lotacao": 0,
        "ultima_mensagem": None,
        "payload_bruto": "",
        "conectado": False,
        "status": "Senha do HiveMQ não configurada no Streamlit Secrets",
    }


# ============================================================
# CABEÇALHO
# ============================================================

agora = agora_brasil()
data_atual = agora.strftime("%d/%m/%Y")
hora_atual = agora.strftime("%H:%M:%S")

st.markdown(
    '<div class="titulo-principal">Painel de Controle Next Mobilidade</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitulo">Demonstração da banca - monitoramento de embarque e lotação em tempo real</div>',
    unsafe_allow_html=True,
)


# ============================================================
# STATUS MQTT
# ============================================================

if dados["conectado"]:
    st.markdown(
        f'<div class="status-ok">MQTT: {dados["status"]}</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="status-alerta">MQTT: {dados["status"]}</div>',
        unsafe_allow_html=True,
    )

st.write("")


# ============================================================
# CARDS PRINCIPAIS
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-titulo">Parada</div>
            <div class="card-valor-menor">{PARADA}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-titulo">Coordenadas</div>
            <div class="card-valor-menor">
                Latitude: {LATITUDE}<br>
                Longitude: {LONGITUDE}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-titulo">Data e hora</div>
            <div class="card-valor-menor">
                {data_atual}<br>
                {hora_atual}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

col4, col5 = st.columns(2)

with col4:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-titulo">Embarque</div>
            <div class="card-valor">{int(dados["embarque"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f"""
        <div class="card">
            <div class="card-titulo">Lotação acumulada</div>
            <div class="card-valor">{int(dados["lotacao"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# INFORMAÇÕES COMPLEMENTARES
# ============================================================

st.write("")

col6, col7 = st.columns(2)

with col6:
    st.subheader("Localização da demonstração")

    mapa_df = pd.DataFrame(
        {
            "latitude": [LATITUDE],
            "longitude": [LONGITUDE],
        }
    )

    st.map(
        mapa_df,
        latitude="latitude",
        longitude="longitude",
        zoom=16,
    )

with col7:
    st.subheader("Última mensagem recebida")

    ultima = dados.get("ultima_mensagem")

    if ultima:
        st.write(f"**Recebida em:** {ultima}")
    else:
        st.write("Nenhuma mensagem recebida ainda.")

    st.write("**Tópico MQTT:**")
    st.code(MQTT_TOPIC)

    st.write("**Payload recebido:**")
    if dados.get("payload_bruto"):
        st.code(dados["payload_bruto"], language="json")
    else:
        st.code('{"embarque": 0, "lotacao": 0}', language="json")


st.markdown(
    """
    <div class="rodape">
        Dashboard atualizado automaticamente. A data e a hora são geradas pelo Streamlit, 
        enquanto embarque e lotação são recebidos via MQTT/HiveMQ.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO_SEGUNDOS)
st.rerun()
