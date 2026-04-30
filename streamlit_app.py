import json
import time
import ssl
import html

import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import pydeck as pdk

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

# Atualização automática do painel a cada 3 minutos
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
# PARADAS E TERMINAIS DA LINHA 290
# =========================

PARADAS = [
    {
        "ordem": 1,
        "nome": "Terminal Diadema",
        "tipo": "Terminal",
        "latitude": -23.682681458564325,
        "longitude": -46.62691332328152
    },
    {
        "ordem": 2,
        "nome": "Parada Assembleia",
        "tipo": "Parada",
        "latitude": -23.67697409771605,
        "longitude": -46.627793033156586
    },
    {
        "ordem": 3,
        "nome": "Parada Divisa",
        "tipo": "Parada",
        "latitude": -23.673551659194004,
        "longitude": -46.63089933449298
    },
    {
        "ordem": 4,
        "nome": "Parada Vila Clara",
        "tipo": "Parada",
        "latitude": -23.670446876785558,
        "longitude": -46.63259010672355
    },
    {
        "ordem": 5,
        "nome": "Parada Bom Clima",
        "tipo": "Parada",
        "latitude": -23.669120531442708,
        "longitude": -46.63486429031358
    },
    {
        "ordem": 6,
        "nome": "Parada São José",
        "tipo": "Parada",
        "latitude": -23.664882066923965,
        "longitude": -46.63779830145058
    },
    {
        "ordem": 7,
        "nome": "Parada Americanópolis",
        "tipo": "Parada",
        "latitude": -23.66095067269106,
        "longitude": -46.637240408622645
    },
    {
        "ordem": 8,
        "nome": "Parada Faccini",
        "tipo": "Parada",
        "latitude": -23.656897096071692,
        "longitude": -46.63611395876546
    },
    {
        "ordem": 9,
        "nome": "Parada Encontro",
        "tipo": "Parada",
        "latitude": -23.652614165456484,
        "longitude": -46.63710571915031
    },
    {
        "ordem": 10,
        "nome": "Parada Cidade Vargas",
        "tipo": "Parada",
        "latitude": -23.648791349310596,
        "longitude": -46.64064538509645
    },
    {
        "ordem": 11,
        "nome": "Terminal Jabaquara",
        "tipo": "Terminal",
        "latitude": -23.646183664190886,
        "longitude": -46.639878302287805
    },
]


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


def converter_float(valor):
    try:
        return float(valor)
    except Exception:
        return None


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


def montar_tabela_operacional(parada_atual, hora, embarque, desembarque, lotacao):
    linhas = []

    for parada in PARADAS:
        nome = parada["nome"]

        if parada_atual == nome:
            horario_linha = hora
            embarque_linha = embarque
            desembarque_linha = desembarque
            lotacao_linha = lotacao
        else:
            horario_linha = "Aguardando dados"
            embarque_linha = "Aguardando dados"
            desembarque_linha = "Aguardando dados"
            lotacao_linha = "Aguardando dados"

        linhas.append({
            "Parada / Terminal": nome,
            "Horário": horario_linha,
            "Embarque": embarque_linha,
            "Desembarque": desembarque_linha,
            "Pessoas no Ônibus": lotacao_linha
        })

    return pd.DataFrame(linhas)


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
            font-size: 40px !important;
            font-weight: 800 !important;
            color: #2b2d3a !important;
            margin-bottom: 28px !important;
        }

        h2, h3 {
            color: #2b2d3a !important;
            font-weight: 800 !important;
        }

        .card {
            background: #f8f9fb;
            border-radius: 16px;
            padding: 20px 22px;
            min-height: 115px;
            box-shadow: 0px 6px 18px rgba(0,0,0,0.07);
            margin-bottom: 18px;
        }

        .card-title {
            color: #5b5b5b;
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 12px;
        }

        .card-value {
            color: #171717;
            font-size: 22px;
            font-weight: 800;
            line-height: 1.35;
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
# DASHBOARD - CARDS
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


col7, col8 = st.columns([1, 2])

with col7:
    card("Velocidade", texto_seguro(velocidade))

with col8:
    fluxo_html = (
        f"Embarque: {texto_seguro(embarque)}<br>"
        f"Desembarque: {texto_seguro(desembarque)}<br>"
        f"Lotação atual: {texto_seguro(lotacao)}"
    )
    card("Fluxo de passageiros", fluxo_html)


# =========================
# TABELA OPERACIONAL
# =========================

st.subheader("Controle de passageiros por parada")

tabela = montar_tabela_operacional(
    parada_atual=parada_atual,
    hora=hora,
    embarque=embarque,
    desembarque=desembarque,
    lotacao=lotacao
)

st.dataframe(
    tabela,
    use_container_width=True,
    hide_index=True
)


# =========================
# MAPA POR ÚLTIMO
# =========================

st.subheader("Localização do ônibus e rota da linha 290")

lat_onibus = converter_float(latitude)
lon_onibus = converter_float(longitude)

df_paradas = pd.DataFrame(PARADAS)
df_paradas["tooltip"] = df_paradas["nome"] + " - " + df_paradas["tipo"]

rota_coordenadas = [
    [p["longitude"], p["latitude"]] for p in PARADAS
]

camadas = [
    pdk.Layer(
        "PathLayer",
        data=[
            {
                "path": rota_coordenadas,
                "tooltip": "Rota da linha 290"
            }
        ],
        get_path="path",
        get_width=5,
        get_color=[0, 90, 200],
        pickable=True
    ),
    pdk.Layer(
        "ScatterplotLayer",
        data=df_paradas,
        get_position="[longitude, latitude]",
        get_radius=65,
        get_fill_color=[30, 120, 220],
        pickable=True
    )
]

if lat_onibus is not None and lon_onibus is not None:
    df_onibus = pd.DataFrame([
        {
            "latitude": lat_onibus,
            "longitude": lon_onibus,
            "tooltip": "Localização atual do ônibus"
        }
    ])

    camadas.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=df_onibus,
            get_position="[longitude, latitude]",
            get_radius=120,
            get_fill_color=[220, 40, 40],
            pickable=True
        )
    )

    centro_lat = lat_onibus
    centro_lon = lon_onibus
    zoom_mapa = 13
else:
    centro_lat = -23.664
    centro_lon = -46.635
    zoom_mapa = 12

view_state = pdk.ViewState(
    latitude=centro_lat,
    longitude=centro_lon,
    zoom=zoom_mapa,
    pitch=0
)

st.pydeck_chart(
    pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=camadas,
        tooltip={"text": "{tooltip}"}
    ),
    use_container_width=True
)
