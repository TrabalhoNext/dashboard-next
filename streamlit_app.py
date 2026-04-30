import json
import time
import ssl
import html

import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import folium
from streamlit_folium import st_folium

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
# PARADAS E TERMINAIS
# =========================

PARADAS = [
    {"ordem": 1, "nome": "Terminal Diadema", "tipo": "Terminal", "latitude": -23.682681458564325, "longitude": -46.62691332328152},
    {"ordem": 2, "nome": "Parada Assembleia", "tipo": "Parada", "latitude": -23.67697409771605, "longitude": -46.627793033156586},
    {"ordem": 3, "nome": "Parada Divisa", "tipo": "Parada", "latitude": -23.673551659194004, "longitude": -46.63089933449298},
    {"ordem": 4, "nome": "Parada Vila Clara", "tipo": "Parada", "latitude": -23.670446876785558, "longitude": -46.63259010672355},
    {"ordem": 5, "nome": "Parada Bom Clima", "tipo": "Parada", "latitude": -23.669120531442708, "longitude": -46.63486429031358},
    {"ordem": 6, "nome": "Parada São José", "tipo": "Parada", "latitude": -23.664882066923965, "longitude": -46.63779830145058},
    {"ordem": 7, "nome": "Parada Americanópolis", "tipo": "Parada", "latitude": -23.66095067269106, "longitude": -46.637240408622645},
    {"ordem": 8, "nome": "Parada Faccini", "tipo": "Parada", "latitude": -23.656897096071692, "longitude": -46.63611395876546},
    {"ordem": 9, "nome": "Parada Encontro", "tipo": "Parada", "latitude": -23.652614165456484, "longitude": -46.63710571915031},
    {"ordem": 10, "nome": "Parada Cidade Vargas", "tipo": "Parada", "latitude": -23.648791349310596, "longitude": -46.64064538509645},
    {"ordem": 11, "nome": "Terminal Jabaquara", "tipo": "Terminal", "latitude": -23.646183664190886, "longitude": -46.639878302287805},
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


def valor_tabela(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()

    if texto == "":
        return ""

    if texto.lower() == "aguardando dados":
        return ""

    return valor


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


def montar_tabela_operacional(dados, parada_atual, hora, embarque, desembarque, lotacao):
    linhas = []
    tabela_mqtt = None

    if dados and isinstance(dados.get("tabela_paradas"), list):
        tabela_mqtt = dados.get("tabela_paradas")

    for parada in PARADAS:
        nome = parada["nome"]

        horario_linha = ""
        embarque_linha = ""
        desembarque_linha = ""
        lotacao_linha = ""

        if tabela_mqtt:
            for item in tabela_mqtt:
                nome_item = item.get("parada") or item.get("nome") or item.get("ponto")

                if nome_item == nome:
                    horario_linha = valor_tabela(item.get("hora") or item.get("horario"))
                    embarque_linha = valor_tabela(item.get("embarque"))
                    desembarque_linha = valor_tabela(item.get("desembarque"))
                    lotacao_linha = valor_tabela(item.get("lotacao") or item.get("pessoas_onibus"))
                    break

        elif parada_atual == nome:
            horario_linha = valor_tabela(hora)
            embarque_linha = valor_tabela(embarque)
            desembarque_linha = valor_tabela(desembarque)
            lotacao_linha = valor_tabela(lotacao)

        linhas.append({
            "Parada / Terminal": nome,
            "Horário": horario_linha,
            "Embarque": embarque_linha,
            "Desembarque": desembarque_linha,
            "Pessoas no Ônibus": lotacao_linha
        })

    return pd.DataFrame(linhas)


def criar_mapa(lat_onibus, lon_onibus):
    lat_rota = [p["latitude"] for p in PARADAS]
    lon_rota = [p["longitude"] for p in PARADAS]

    centro_lat = sum(lat_rota) / len(lat_rota)
    centro_lon = sum(lon_rota) / len(lon_rota)

    mapa = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True
    )

    coordenadas_rota = [
        [p["latitude"], p["longitude"]] for p in PARADAS
    ]

    folium.PolyLine(
        coordenadas_rota,
        color="#1a73e8",
        weight=7,
        opacity=0.9,
        tooltip="Rota da linha 290"
    ).add_to(mapa)

    for parada in PARADAS:
        cor = "#1a73e8"

        if parada["tipo"] == "Terminal":
            raio = 8
        else:
            raio = 6

        folium.CircleMarker(
            location=[parada["latitude"], parada["longitude"]],
            radius=raio,
            color="#ffffff",
            weight=2,
            fill=True,
            fill_color=cor,
            fill_opacity=1,
            tooltip=f'{parada["nome"]} - {parada["tipo"]}'
        ).add_to(mapa)

    pontos_enquadramento = coordenadas_rota.copy()

    if lat_onibus is not None and lon_onibus is not None:
        folium.Marker(
            location=[lat_onibus, lon_onibus],
            tooltip="Localização atual do ônibus",
            icon=folium.Icon(color="red", icon="bus", prefix="fa")
        ).add_to(mapa)

        pontos_enquadramento.append([lat_onibus, lon_onibus])

    mapa.fit_bounds(pontos_enquadramento, padding=(30, 30))

    return mapa


# =========================
# ESTILO VISUAL
# =========================

st.markdown(
    """
    <style>
        .main {
            background-color: #ffffff;
        }

        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 2rem;
        }

        h1 {
            font-size: 34px !important;
            font-weight: 800 !important;
            color: #2b2d3a !important;
            margin-bottom: 22px !important;
        }

        h2, h3 {
            color: #2b2d3a !important;
            font-weight: 800 !important;
        }

        .card {
            background: #f8f9fb;
            border-radius: 14px;
            padding: 15px 17px;
            min-height: 105px;
            box-shadow: 0px 5px 14px rgba(0,0,0,0.055);
            margin-bottom: 15px;
        }

        .card-title {
            color: #5b5b5b;
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 9px;
        }

        .card-value {
            color: #171717;
            font-size: 19px;
            font-weight: 800;
            line-height: 1.32;
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
    card("Lotação atual", texto_seguro(lotacao))


# =========================
# TABELA OPERACIONAL
# =========================

st.subheader("Controle de passageiros por parada")

tabela = montar_tabela_operacional(
    dados=dados,
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

mapa = criar_mapa(lat_onibus, lon_onibus)

st_folium(
    mapa,
    width=None,
    height=520,
    returned_objects=[]
)
