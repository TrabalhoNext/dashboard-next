import json
import time
import math
import threading
from datetime import datetime

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
import folium
from streamlit_folium import st_folium


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

st.set_page_config(
    page_title="Dashboard Linha 290",
    layout="wide"
)

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "next/linha290/gps"

INTERVALO_ATUALIZACAO = 5  # segundos


# ============================================================
# PARADAS DA LINHA 290
# ============================================================

PARADAS = [
    {
        "ordem": 1,
        "nome": "Terminal Diadema",
        "lat": -23.682681458564325,
        "lon": -46.62691332328152
    },
    {
        "ordem": 2,
        "nome": "Parada Assembleia",
        "lat": -23.67697409771605,
        "lon": -46.627793033156586
    },
    {
        "ordem": 3,
        "nome": "Parada Divisa",
        "lat": -23.673551659194004,
        "lon": -46.63089933449298
    },
    {
        "ordem": 4,
        "nome": "Parada Vila Clara",
        "lat": -23.670446876785558,
        "lon": -46.63259010672355
    },
    {
        "ordem": 5,
        "nome": "Parada Bom Clima",
        "lat": -23.669120531442708,
        "lon": -46.63486429031358
    },
    {
        "ordem": 6,
        "nome": "Parada São José",
        "lat": -23.664882066923965,
        "lon": -46.63779830145058
    },
    {
        "ordem": 7,
        "nome": "Parada Americanópolis",
        "lat": -23.66095067269106,
        "lon": -46.637240408622645
    },
    {
        "ordem": 8,
        "nome": "Parada Faccini",
        "lat": -23.656897096071692,
        "lon": -46.63611395876546
    },
    {
        "ordem": 9,
        "nome": "Parada Encontro",
        "lat": -23.652614165456484,
        "lon": -46.63710571915031
    },
    {
        "ordem": 10,
        "nome": "Parada Cidade Vargas",
        "lat": -23.648791349310596,
        "lon": -46.64064538509645
    },
    {
        "ordem": 11,
        "nome": "Terminal Jabaquara",
        "lat": -23.646183664190886,
        "lon": -46.639878302287805
    }
]


# ============================================================
# FUNÇÕES DE CÁLCULO
# ============================================================

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """
    Calcula distância aproximada entre dois pontos GPS em metros.
    """
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


def encontrar_parada_mais_proxima(latitude, longitude):
    menor_distancia = float("inf")
    parada_mais_proxima = None
    indice_mais_proximo = None

    for indice, parada in enumerate(PARADAS):
        distancia = calcular_distancia_metros(
            latitude,
            longitude,
            parada["lat"],
            parada["lon"]
        )

        if distancia < menor_distancia:
            menor_distancia = distancia
            parada_mais_proxima = parada
            indice_mais_proximo = indice

    return parada_mais_proxima, indice_mais_proximo, menor_distancia


def identificar_sentido(indice_atual, ultimo_indice):
    """
    Identifica o sentido pela variação da posição entre as paradas.
    """
    if ultimo_indice is None:
        return "Aguardando deslocamento"

    if indice_atual > ultimo_indice:
        return "Terminal Diadema → Terminal Jabaquara"

    if indice_atual < ultimo_indice:
        return "Terminal Jabaquara → Terminal Diadema"

    return "Sem alteração"


def identificar_trecho(indice_atual, sentido):
    """
    Define o trecho com base no índice da parada mais próxima e no sentido.
    """
    if sentido == "Terminal Diadema → Terminal Jabaquara":
        if indice_atual < len(PARADAS) - 1:
            origem = PARADAS[indice_atual]["nome"]
            destino = PARADAS[indice_atual + 1]["nome"]
            return f"Entre {origem} e {destino}"
        return "Fim da linha - Terminal Jabaquara"

    if sentido == "Terminal Jabaquara → Terminal Diadema":
        if indice_atual > 0:
            origem = PARADAS[indice_atual]["nome"]
            destino = PARADAS[indice_atual - 1]["nome"]
            return f"Entre {origem} e {destino}"
        return "Fim da linha - Terminal Diadema"

    return "Aguardando deslocamento"


def interpretar_posicao(latitude, longitude, velocidade):
    """
    Interpreta a posição do ônibus com base no GPS.
    """
    parada, indice_atual, distancia = encontrar_parada_mais_proxima(latitude, longitude)

    ultimo_indice = st.session_state.get("ultimo_indice_parada", None)

    sentido = identificar_sentido(indice_atual, ultimo_indice)
    trecho = identificar_trecho(indice_atual, sentido)

    st.session_state["ultimo_indice_parada"] = indice_atual

    # Ajuste de tolerância da parada
    # Se quiser mais rígido, use 30 ou 40 metros.
    # Se quiser mais flexível em teste real, use 80 ou 100 metros.
    RAIO_PARADA_METROS = 80

    if velocidade <= 5 and distancia <= RAIO_PARADA_METROS:
        parada_atual = parada["nome"]
        situacao = "Parado"
    elif velocidade > 5:
        parada_atual = "Em rota"
        situacao = "Em rota"
    else:
        parada_atual = "Fora de parada cadastrada"
        situacao = "Parado fora da parada"

    return {
        "parada_atual": parada_atual,
        "situacao": situacao,
        "sentido": sentido,
        "trecho": trecho,
        "indice_atual": indice_atual,
        "distancia_parada_m": round(distancia, 1)
    }


# ============================================================
# MQTT
# ============================================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        dados = json.loads(payload)

        st.session_state["ultimo_payload_mqtt"] = dados
        st.session_state["ultima_mensagem_recebida"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    except Exception as erro:
        st.session_state["erro_mqtt"] = str(erro)


def iniciar_mqtt():
    if "mqtt_iniciado" not in st.session_state:
        st.session_state["mqtt_iniciado"] = True

        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(MQTT_BROKER, MQTT_PORT, 60)

        thread = threading.Thread(target=client.loop_forever)
        thread.daemon = True
        thread.start()


# ============================================================
# TABELA FIXA
# ============================================================

def criar_tabela_fixa():
    tabela = []

    for parada in PARADAS:
        tabela.append({
            "Ordem": parada["ordem"],
            "Terminal / Parada": parada["nome"],
            "Situação": "",
            "Horário": "",
            "Velocidade": "",
            "Sentido": "",
            "Trecho": ""
        })

    return pd.DataFrame(tabela)


def atualizar_tabela_fixa(df, indice_atual, dados_atualizados):
    """
    Atualiza a tabela fixa sem criar novas linhas.
    Apenas limpa os campos dinâmicos e preenche a linha atual.
    """

    colunas_dinamicas = [
        "Situação",
        "Horário",
        "Velocidade",
        "Sentido",
        "Trecho"
    ]

    for coluna in colunas_dinamicas:
        df[coluna] = ""

    if indice_atual is not None and 0 <= indice_atual < len(df):
        df.loc[indice_atual, "Situação"] = dados_atualizados["situacao"]
        df.loc[indice_atual, "Horário"] = dados_atualizados["hora"]
        df.loc[indice_atual, "Velocidade"] = f'{dados_atualizados["velocidade"]} km/h'
        df.loc[indice_atual, "Sentido"] = dados_atualizados["sentido"]
        df.loc[indice_atual, "Trecho"] = dados_atualizados["trecho"]

    return df


# ============================================================
# MAPA
# ============================================================

def criar_mapa(latitude_atual=None, longitude_atual=None):
    centro_mapa = [-23.6645, -46.6345]

    mapa = folium.Map(
        location=centro_mapa,
        zoom_start=14,
        tiles="OpenStreetMap"
    )

    coordenadas_rota = [(p["lat"], p["lon"]) for p in PARADAS]

    folium.PolyLine(
        locations=coordenadas_rota,
        weight=5,
        opacity=0.8,
        tooltip="Rota Linha 290"
    ).add_to(mapa)

    # Marcadores discretos das paradas
    for parada in PARADAS:
        folium.CircleMarker(
            location=[parada["lat"], parada["lon"]],
            radius=4,
            popup=parada["nome"],
            tooltip=parada["nome"],
            fill=True
        ).add_to(mapa)

    # Marcador do ônibus
    if latitude_atual is not None and longitude_atual is not None:
        folium.Marker(
            location=[latitude_atual, longitude_atual],
            popup="Posição atual do ônibus",
            tooltip="Ônibus"
        ).add_to(mapa)

        mapa.location = [latitude_atual, longitude_atual]

    return mapa


# ============================================================
# INICIALIZAÇÃO DO SESSION STATE
# ============================================================

if "ultimo_payload_mqtt" not in st.session_state:
    st.session_state["ultimo_payload_mqtt"] = {}

if "ultima_mensagem_recebida" not in st.session_state:
    st.session_state["ultima_mensagem_recebida"] = "Aguardando dados"

if "erro_mqtt" not in st.session_state:
    st.session_state["erro_mqtt"] = ""

if "tabela_linha" not in st.session_state:
    st.session_state["tabela_linha"] = criar_tabela_fixa()

if "ultimo_indice_parada" not in st.session_state:
    st.session_state["ultimo_indice_parada"] = None


iniciar_mqtt()


# ============================================================
# LEITURA DO ÚLTIMO DADO RECEBIDO
# ============================================================

payload = st.session_state.get("ultimo_payload_mqtt", {})

latitude = payload.get("latitude", None)
longitude = payload.get("longitude", None)

try:
    latitude = float(latitude) if latitude is not None else None
    longitude = float(longitude) if longitude is not None else None
except:
    latitude = None
    longitude = None

velocidade = payload.get("velocidade", 0)

try:
    velocidade = float(velocidade)
except:
    velocidade = 0

velocidade = int(round(velocidade))

data = payload.get("data", datetime.now().strftime("%d/%m/%Y"))
hora = payload.get("hora", datetime.now().strftime("%H:%M:%S"))

embarque = payload.get("embarque", "Aguardando dados")
desembarque = payload.get("desembarque", "Aguardando dados")
lotacao = payload.get("lotacao", "Aguardando dados")


if latitude is not None and longitude is not None:
    interpretacao = interpretar_posicao(latitude, longitude, velocidade)

    parada_atual = interpretacao["parada_atual"]
    situacao = interpretacao["situacao"]
    sentido = interpretacao["sentido"]
    trecho = interpretacao["trecho"]
    indice_atual = interpretacao["indice_atual"]
    distancia_parada_m = interpretacao["distancia_parada_m"]

else:
    parada_atual = "Aguardando dados"
    situacao = "Aguardando dados"
    sentido = "Aguardando dados"
    trecho = "Aguardando dados"
    indice_atual = None
    distancia_parada_m = "Aguardando dados"


dados_atualizados = {
    "situacao": situacao,
    "hora": hora,
    "velocidade": velocidade,
    "sentido": sentido,
    "trecho": trecho
}

st.session_state["tabela_linha"] = atualizar_tabela_fixa(
    st.session_state["tabela_linha"],
    indice_atual,
    dados_atualizados
)


# ============================================================
# INTERFACE
# ============================================================

st.title("Dashboard Operacional - Linha 290")

st.caption("Monitoramento em tempo real por GPS, MQTT e sistema embarcado Raspberry Pi 5.")


# ============================================================
# CARDS PRINCIPAIS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Parada atual", parada_atual)

with col2:
    st.metric("Situação", situacao)

with col3:
    st.metric("Velocidade", f"{velocidade} km/h")

with col4:
    st.metric("Última atualização", st.session_state["ultima_mensagem_recebida"])


col5, col6, col7 = st.columns(3)

with col5:
    st.metric("Sentido", sentido)

with col6:
    st.metric("Trecho", trecho)

with col7:
    st.metric("Distância da parada", f"{distancia_parada_m} m")


col8, col9, col10 = st.columns(3)

with col8:
    st.metric("Embarque", embarque)

with col9:
    st.metric("Desembarque", desembarque)

with col10:
    st.metric("Lotação atual", lotacao)


# ============================================================
# DADOS GPS
# ============================================================

st.subheader("Dados atuais do GPS")

col11, col12, col13, col14 = st.columns(4)

with col11:
    st.metric("Data", data)

with col12:
    st.metric("Hora", hora)

with col13:
    st.metric("Latitude", latitude if latitude is not None else "Aguardando dados")

with col14:
    st.metric("Longitude", longitude if longitude is not None else "Aguardando dados")


# ============================================================
# TABELA FIXA
# ============================================================

st.subheader("Tabela operacional da linha")

st.dataframe(
    st.session_state["tabela_linha"],
    use_container_width=True,
    hide_index=True
)


# ============================================================
# MAPA
# ============================================================

st.subheader("Mapa da linha 290")

mapa = criar_mapa(latitude, longitude)

st_folium(
    mapa,
    width=None,
    height=500,
    returned_objects=[]
)


# ============================================================
# STATUS MQTT
# ============================================================

with st.expander("Status técnico MQTT"):
    st.write("Broker:", MQTT_BROKER)
    st.write("Tópico:", MQTT_TOPIC)
    st.write("Último payload recebido:")
    st.json(payload)

    if st.session_state["erro_mqtt"]:
        st.error(st.session_state["erro_mqtt"])


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
