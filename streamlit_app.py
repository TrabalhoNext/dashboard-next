import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import threading
import uuid
from datetime import datetime


# =========================
# CONFIGURAÇÕES DO DASHBOARD
# =========================

st.set_page_config(
    page_title="Painel Next Mobilidade",
    page_icon="🚌",
    layout="wide"
)

# Dados do HiveMQ/Streamlit Secrets
MQTT_BROKER = st.secrets.get("MQTT_BROKER", "")
MQTT_PORT = int(st.secrets.get("MQTT_PORT", 8883))
MQTT_USERNAME = st.secrets.get("MQTT_USERNAME", "")
MQTT_PASSWORD = st.secrets.get("MQTT_PASSWORD", "")
MQTT_TOPIC = st.secrets.get("MQTT_TOPIC", "next/linha290/gps")

INTERVALO_ATUALIZACAO = 2


# =========================
# ESTADO GLOBAL DO MQTT
# =========================

class EstadoMQTT:
    def __init__(self):
        self.lock = threading.Lock()
        self.conectado = False
        self.ultima_mensagem = None
        self.ultimo_payload_bruto = ""
        self.ultimo_recebimento = None
        self.erro = ""

    def atualizar_mensagem(self, payload_bruto, dados):
        with self.lock:
            self.ultima_mensagem = dados
            self.ultimo_payload_bruto = payload_bruto
            self.ultimo_recebimento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.erro = ""

    def atualizar_status(self, conectado):
        with self.lock:
            self.conectado = conectado

    def atualizar_erro(self, erro):
        with self.lock:
            self.erro = erro

    def obter(self):
        with self.lock:
            return {
                "conectado": self.conectado,
                "ultima_mensagem": self.ultima_mensagem,
                "ultimo_payload_bruto": self.ultimo_payload_bruto,
                "ultimo_recebimento": self.ultimo_recebimento,
                "erro": self.erro
            }


@st.cache_resource
def iniciar_mqtt():
    estado = EstadoMQTT()

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            estado.atualizar_status(True)
            client.subscribe(MQTT_TOPIC)
            print(f"[MQTT] Dashboard conectado e inscrito no tópico: {MQTT_TOPIC}")
        else:
            estado.atualizar_status(False)
            estado.atualizar_erro(f"Falha ao conectar no MQTT. Código: {rc}")

    def on_disconnect(client, userdata, rc, properties=None):
        estado.atualizar_status(False)
        print("[MQTT] Dashboard desconectado")

    def on_message(client, userdata, msg):
        try:
            payload_bruto = msg.payload.decode("utf-8")
            dados = json.loads(payload_bruto)
            estado.atualizar_mensagem(payload_bruto, dados)
            print(f"[MQTT] Mensagem recebida no dashboard: {payload_bruto}")
        except Exception as e:
            estado.atualizar_erro(f"Erro ao ler payload: {e}")

    client_id = f"streamlit_next_{uuid.uuid4().hex[:8]}"

    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id
        )
    except Exception:
        client = mqtt.Client(client_id=client_id)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_PORT == 8883:
        client.tls_set()

    try:
        client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
    except Exception as e:
        estado.atualizar_erro(f"Erro ao iniciar MQTT: {e}")

    return estado


estado_mqtt = iniciar_mqtt()
estado = estado_mqtt.obter()
dados = estado["ultima_mensagem"]


# =========================
# FUNÇÕES AUXILIARES
# =========================

def valor(dicionario, chave, padrao="-"):
    if not dicionario:
        return padrao
    v = dicionario.get(chave, padrao)
    if v is None or v == "":
        return padrao
    return v


def card(titulo, valor_card):
    st.markdown(
        f"""
        <div style="
            border: 2px solid #ddd;
            border-radius: 14px;
            padding: 18px;
            background-color: #ffffff;
            box-shadow: 0px 2px 8px rgba(0,0,0,0.08);
            min-height: 120px;
        ">
            <div style="font-size: 16px; color: #555; font-weight: 600;">
                {titulo}
            </div>
            <div style="font-size: 26px; color: #111; font-weight: 700; margin-top: 12px;">
                {valor_card}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================
# CABEÇALHO
# =========================

st.title("Painel Next Mobilidade")

if dados:
    subtitulo = valor(
        dados,
        "subtitulo_linha",
        valor(dados, "sentido", "Linha 290 Terminal Diadema - Terminal Jabaquara")
    )
else:
    subtitulo = "Linha 290 Terminal Diadema - Terminal Jabaquara"

st.subheader(subtitulo)


# =========================
# DADOS PARA OS CARDS
# =========================

if dados:
    parada = valor(dados, "parada_atual", valor(dados, "parada", "Aguardando"))
    latitude = valor(dados, "latitude")
    longitude = valor(dados, "longitude")
    velocidade = valor(dados, "velocidade")
    data = valor(dados, "data")
    hora = valor(dados, "hora")
    embarque = valor(dados, "embarque", 0)
    lotacao_atual = valor(dados, "lotacao_atual", 0)
else:
    parada = "Aguardando dados"
    latitude = "-"
    longitude = "-"
    velocidade = "-"
    data = "-"
    hora = "-"
    embarque = 0
    lotacao_atual = 0


# =========================
# CARDS PRINCIPAIS
# =========================

col1, col2, col3, col4 = st.columns(4)

with col1:
    card("Parada / Situação", parada)

with col2:
    card("Coordenadas", f"{latitude}<br>{longitude}")

with col3:
    card("Data e hora", f"{data}<br>{hora}")

with col4:
    card("Velocidade", velocidade)

st.write("")

col5, col6 = st.columns(2)

with col5:
    card("Embarque", embarque)

with col6:
    card("Lotação atual", lotacao_atual)


# =========================
# ATUALIZAÇÃO AUTOMÁTICA
# =========================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
