import json
import time
import math
import threading
from datetime import datetime, time as dt_time, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
import folium
from streamlit_folium import st_folium


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

st.set_page_config(
    page_title="Painel de Controle Next Mobilidade",
    layout="wide"
)

MQTT_BROKER = st.secrets["mqtt"]["broker"]
MQTT_PORT = int(st.secrets["mqtt"]["porta"])
MQTT_TOPIC = st.secrets["mqtt"]["topico"]
MQTT_USUARIO = st.secrets["mqtt"]["usuario"]
MQTT_SENHA = st.secrets["mqtt"]["senha"]

INTERVALO_ATUALIZACAO = 3  # segundos
RAIO_PARADA_METROS = 30    # metros


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
# FUNÇÕES AUXILIARES
# ============================================================

def obter_valor(dados, chaves, padrao=None):
    for chave in chaves:
        valor = dados.get(chave)
        if valor is not None and valor != "":
            return valor
    return padrao


def converter_float(valor):
    if valor is None or valor == "" or valor == "Aguardando dados":
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


def converter_data_hora_para_sao_paulo(data_valor, hora_valor):
    if not hora_valor or hora_valor == "Aguardando dados":
        return data_valor, hora_valor

    texto_hora = str(hora_valor).strip()

    try:
        if "T" in texto_hora:
            texto_iso = texto_hora.replace("Z", "+00:00")
            data_hora = datetime.fromisoformat(texto_iso)

            if data_hora.tzinfo is None:
                data_hora = data_hora.replace(tzinfo=timezone.utc)

            if ZoneInfo is not None:
                data_hora_sp = data_hora.astimezone(ZoneInfo("America/Sao_Paulo"))
            else:
                data_hora_sp = data_hora.astimezone(timezone(timedelta(hours=-3)))

            return data_hora_sp.strftime("%d/%m/%Y"), data_hora_sp.strftime("%H:%M:%S")

        return data_valor, hora_valor

    except Exception:
        return data_valor, hora_valor


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
    if ultimo_indice is None:
        return "Aguardando deslocamento"

    if indice_atual > ultimo_indice:
        return "Terminal Diadema → Terminal Jabaquara"

    if indice_atual < ultimo_indice:
        return "Terminal Jabaquara → Terminal Diadema"

    return "Sem alteração"


def identificar_trecho(indice_atual, sentido):
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
    parada, indice_atual, distancia = encontrar_parada_mais_proxima(
        latitude,
        longitude
    )

    ultimo_indice = st.session_state.get("ultimo_indice_parada", None)

    sentido = identificar_sentido(indice_atual, ultimo_indice)
    trecho = identificar_trecho(indice_atual, sentido)

    st.session_state["ultimo_indice_parada"] = indice_atual

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


def codigo_reason_code(reason_code):
    try:
        return int(reason_code)
    except Exception:
        texto = str(reason_code).lower()
        if "success" in texto or texto == "0":
            return 0
        return -1


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

    client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    return estado


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
    if latitude_atual is not None and longitude_atual is not None:
        centro_mapa = [latitude_atual, longitude_atual]
        zoom = 15
    else:
        centro_mapa = [-23.6645, -46.6345]
        zoom = 14

    mapa = folium.Map(
        location=centro_mapa,
        zoom_start=zoom,
        tiles="OpenStreetMap"
    )

    coordenadas_rota = [(p["lat"], p["lon"]) for p in PARADAS]

    folium.PolyLine(
        locations=coordenadas_rota,
        weight=5,
        opacity=0.8
    ).add_to(mapa)

    for parada in PARADAS:
        folium.CircleMarker(
            location=[parada["lat"], parada["lon"]],
            radius=4,
            fill=True,
            fill_opacity=0.9,
            opacity=0.9
        ).add_to(mapa)

    if latitude_atual is not None and longitude_atual is not None:
        folium.Marker(
            location=[latitude_atual, longitude_atual],
            popup="Ônibus"
        ).add_to(mapa)

    return mapa


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if "tabela_linha" not in st.session_state:
    st.session_state["tabela_linha"] = criar_tabela_fixa()

if "ultimo_indice_parada" not in st.session_state:
    st.session_state["ultimo_indice_parada"] = None


estado_mqtt = iniciar_mqtt()
snapshot = estado_mqtt.snapshot()
payload = snapshot["payload"]


# ============================================================
# LEITURA DO ÚLTIMO PAYLOAD RECEBIDO
# ============================================================

latitude = converter_float(
    obter_valor(payload, ["latitude", "lat"])
)

longitude = converter_float(
    obter_valor(payload, ["longitude", "lon", "lng"])
)

velocidade_float = converter_float(
    obter_valor(payload, ["velocidade", "speed"], 0)
)

if velocidade_float is not None:
    velocidade = int(round(velocidade_float))
else:
    velocidade = 0


data = obter_valor(
    payload,
    ["data", "date"],
    "Aguardando dados"
)

hora = obter_valor(
    payload,
    ["hora_local", "hora_brasil", "hora", "time"],
    "Aguardando dados"
)

data, hora = converter_data_hora_para_sao_paulo(data, hora)

embarque = obter_valor(
    payload,
    ["embarque", "embarques"],
    "Aguardando dados"
)

desembarque = obter_valor(
    payload,
    ["desembarque", "desembarques"],
    "Aguardando dados"
)

lotacao = obter_valor(
    payload,
    ["lotacao", "lotação", "lotacao_atual", "lotação_atual"],
    "Aguardando dados"
)


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

st.title("Painel de Controle Next Mobilidade")


# ============================================================
# CARDS PRINCIPAIS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Parada atual", parada_atual)

with col2:
    st.metric("Situação", situacao)

with col3:
    if latitude is not None and longitude is not None:
        st.metric("Velocidade", f"{velocidade} km/h")
    else:
        st.metric("Velocidade", "Aguardando dados")

with col4:
    st.metric("Última atualização", snapshot["ultima_mensagem"])


col5, col6, col7 = st.columns(3)

with col5:
    st.metric("Sentido", sentido)

with col6:
    st.metric("Trecho", trecho)

with col7:
    if isinstance(distancia_parada_m, (int, float)):
        st.metric("Distância da parada", f"{distancia_parada_m} m")
    else:
        st.metric("Distância da parada", distancia_parada_m)


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
    if latitude is not None:
        st.metric("Latitude", latitude)
    else:
        st.metric("Latitude", "Aguardando dados")

with col14:
    if longitude is not None:
        st.metric("Longitude", longitude)
    else:
        st.metric("Longitude", "Aguardando dados")


# ============================================================
# TABELA FIXA
# ============================================================

st.subheader("Tabela operacional da linha")

st.dataframe(
    st.session_state["tabela_linha"],
    width="stretch",
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
    st.write("Porta:", MQTT_PORT)
    st.write("Tópico:", MQTT_TOPIC)
    st.write("Conectado:", "Sim" if snapshot["conectado"] else "Não")
    st.write("Última mensagem recebida:", snapshot["ultima_mensagem"])
    st.write("Último payload recebido:")
    st.json(payload)

    if snapshot["erro"]:
        st.error(snapshot["erro"])


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
