import json
import time
import ssl
import html

import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None


# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================

st.set_page_config(
    page_title="Next Mobilidade Dashboard",
    page_icon="🚌",
    layout="wide"
)

# Atualização automática a cada 3 minutos
if st_autorefresh:
    st_autorefresh(interval=180000, key="atualizacao_dashboard")


# =========================
# CONFIGURAÇÃO MQTT - HIVEMQ CLOUD
# =========================

MQTT_BROKER = "5031204390404922a3a816878ccfd1f4.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TOPIC = "next/linha290/gps"


def obter_credenciais_mqtt():
    try:
        usuario = st.secrets["mqtt"]["usuario"]
        senha = st.secrets["mqtt"]["senha"]
        return usuario, senha
    except Exception:
        return None, None


# =========================
# LEITURA DOS DADOS VIA MQTT
# =========================

def criar_cliente_mqtt(client_id):
    try:
        return mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311
        )
    except Exception:
        return mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311
        )


def ler_dados_reais():
    usuario, senha = obter_credenciais_mqtt()

    if not usuario or not senha:
        return None

    resultado = {"payload": None}

    def on_connect(client, userdata, flags, reason_code=None, properties=None):
        try:
            client.subscribe(MQTT_TOPIC)
        except Exception:
            pass

    def on_message(client, userdata, msg):
        try:
            resultado["payload"] = msg.payload.decode("utf-8")
        except Exception:
            resultado["payload"] = None

    client_id = f"dashboard_next_{int(time.time() * 1000)}"

    try:
        client = criar_cliente_mqtt(client_id)

        client.username_pw_set(usuario, senha)

        try:
            client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
        except Exception:
            client.tls_set()

        client.tls_insecure_set(False)

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        inicio = time.time()

        while resultado["payload"] is None and time.time() - inicio < 8:
            time.sleep(0.1)

        client.loop_stop()
        client.disconnect()

        if resultado["payload"]:
            return json.loads(resultado["payload"])

        return None

    except Exception:
        return None


# =========================
# FUNÇÕES AUXILIARES
# =========================

def obter_valor(dados, chave):
    if not dados:
        return "Aguardando dados"

    valor = dados.get(chave)

    if valor is None or valor == "":
        return "Aguardando dados"

    return valor


def texto_seguro(valor):
    if valor is None or valor == "":
        return "Aguardando dados"
    return html.escape(str(valor))


def velocidade_numerica(valor):
    try:
        if valor is None:
            return 0.0

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = str(valor)
        texto = texto.replace("km/h", "")
        texto = texto.replace("km", "")
        texto = texto.replace(",", ".")
        texto = texto.strip()

        return float(texto)
    except Exception:
        return 0.0


def card(titulo, conteudo_html):
    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">{html.escape(titulo)}</div>
            <div class="card-value">{conteudo_html}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# =========================
# ESTILO VISUAL
# =========================

st.markdown(
    """
    <style>
        .main {
            background-color: #ffffff;
        }

        h1 {
            font-size: 42px !important;
            font-weight: 800 !important;
            color: #2b2d3a !important;
            margin-bottom: 30px !important;
        }

        h2, h3 {
            color: #2b2d3a !important;
            font-weight: 800 !important;
        }

        .card {
            background: #f8f9fb;
            border-radius: 18px;
            padding: 26px;
            min-height: 135px;
            box-shadow: 0px 8px 24px rgba(0,0,0,0.08);
            margin-bottom: 22px;
        }

        .card-title {
            color: #5b5b5b;
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 18px;
        }

        .card-value {
            color: #171717;
            font-size: 24px;
            font-weight: 800;
            line-height: 1.5;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# =========================
# CARREGAMENTO DOS DADOS
# =========================

dados = ler_dados_reais()

data = obter_valor(dados, "data")
hora = obter_valor(dados, "hora")
latitude = obter_valor(dados, "latitude")
longitude = obter_valor(dados, "longitude")
velocidade = obter_valor(dados, "velocidade")
parada_atual = obter_valor(dados, "parada_atual")
sentido = obter_valor(dados, "sentido")
trecho = obter_valor(dados, "trecho")

embarque = obter_valor(dados, "embarque")
desembarque = obter_valor(dados, "desembarque")
lotacao = obter_valor(dados, "lotacao")

vel_num = velocidade_numerica(velocidade)

if dados:
    if vel_num > 5:
        parada_card = "Em rota"
    else:
        parada_card = parada_atual
else:
    parada_card = "Aguardando dados"

if data != "Aguardando dados" and hora != "Aguardando dados":
    horario_card = f"{data} - {hora}"
elif hora != "Aguardando dados":
    horario_card = hora
else:
    horario_card = "Aguardando dados"


# =========================
# DASHBOARD
# =========================

st.title("Painel de Controle Next Mobilidade")

col1, col2, col3 = st.columns(3)

with col1:
    card("Ônibus / Linha", "290 Diadema - Jabaquara")

with col2:
    card("Parada atual", texto_seguro(parada_card))

with col3:
    card("Sentido", texto_seguro(sentido))


col4, col5, col6 = st.columns(3)

with col4:
    card("Trecho", texto_seguro(trecho))

with col5:
    card("Horário", texto_seguro(horario_card))

with col6:
    localizacao_html = (
        f"Latitude: {texto_seguro(latitude)}<br>"
        f"Longitude: {texto_seguro(longitude)}"
    )
    card("Localização", localizacao_html)


col7, col8, col9 = st.columns(3)

with col7:
    card("Velocidade", texto_seguro(velocidade))

with col8:
    fluxo_html = (
        f"Embarque: {texto_seguro(embarque)}<br>"
        f"Desembarque: {texto_seguro(desembarque)}"
    )
    card("Fluxo de passageiros", fluxo_html)

with col9:
    card("Pessoas no ônibus", texto_seguro(lotacao))


# =========================
# TABELA DAS PARADAS
# =========================

st.subheader("Paradas e terminais cadastrados")

paradas = pd.DataFrame([
    {"Ordem": 1, "Ponto": "Terminal Diadema", "Tipo": "Terminal"},
    {"Ordem": 2, "Ponto": "Parada Assembleia", "Tipo": "Parada"},
    {"Ordem": 3, "Ponto": "Parada Divisa", "Tipo": "Parada"},
    {"Ordem": 4, "Ponto": "Parada Vila Clara", "Tipo": "Parada"},
    {"Ordem": 5, "Ponto": "Parada Bom Clima", "Tipo": "Parada"},
    {"Ordem": 6, "Ponto": "Parada São José", "Tipo": "Parada"},
    {"Ordem": 7, "Ponto": "Parada Americanópolis", "Tipo": "Parada"},
    {"Ordem": 8, "Ponto": "Parada Faccini", "Tipo": "Parada"},
    {"Ordem": 9, "Ponto": "Parada Encontro", "Tipo": "Parada"},
    {"Ordem": 10, "Ponto": "Parada Cidade Vargas", "Tipo": "Parada"},
    {"Ordem": 11, "Ponto": "Terminal Jabaquara", "Tipo": "Terminal"}
])

st.dataframe(
    paradas,
    use_container_width=True,
    hide_index=True
)
