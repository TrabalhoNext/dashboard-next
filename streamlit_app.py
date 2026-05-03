import json
import time
import math
import html
import threading
from datetime import datetime, timezone, timedelta

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

INTERVALO_ATUALIZACAO = 3

RAIO_PARADA_ATUAL_METROS = 15
RAIO_SAIDA_TERMINAL_METROS = 10
VELOCIDADE_MINIMA_SENTIDO = 2


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
    if valor is None or valor == "" or valor == "Aguardando dados":
        return None

    try:
        if isinstance(valor, str):
            valor = (
                valor.replace("km/h", "")
                .replace("km", "")
                .replace("°", "")
                .replace(",", ".")
                .strip()
            )
        return float(valor)
    except Exception:
        return None


def valor_tabela(valor):
    if valor is None or valor == "" or valor == "Aguardando dados":
        return ""
    return str(valor)


def agora_sao_paulo():
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
    return datetime.utcnow() - timedelta(hours=3)


def ajustar_data_hora(data_valor, hora_valor):
    if not data_valor:
        data_valor = "Aguardando dados"

    if not hora_valor:
        hora_valor = "Aguardando dados"

    try:
        hora_texto = str(hora_valor).strip()

        if "T" in hora_texto:
            data_hora = datetime.fromisoformat(hora_texto.replace("Z", "+00:00"))

            if data_hora.tzinfo is None:
                data_hora = data_hora.replace(tzinfo=timezone.utc)

            if ZoneInfo is not None:
                data_hora = data_hora.astimezone(ZoneInfo("America/Sao_Paulo"))
            else:
                data_hora = data_hora.astimezone(timezone(timedelta(hours=-3)))

            return data_hora.strftime("%d/%m/%Y"), data_hora.strftime("%H:%M:%S")

        return str(data_valor), str(hora_valor)

    except Exception:
        return str(data_valor), str(hora_valor)


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


def converter_para_xy_metros(lat, lon, lat_ref, lon_ref):
    raio_terra = 6371000

    x = math.radians(lon - lon_ref) * raio_terra * math.cos(math.radians(lat_ref))
    y = math.radians(lat - lat_ref) * raio_terra

    return x, y


def calcular_progresso_rota(latitude, longitude):
    lat_ref = PARADAS[0]["lat"]
    lon_ref = PARADAS[0]["lon"]

    px, py = converter_para_xy_metros(latitude, longitude, lat_ref, lon_ref)

    melhor_distancia = float("inf")
    melhor_indice = 0
    melhor_progresso = 0

    progresso_acumulado = 0

    for i in range(len(PARADAS) - 1):
        p1 = PARADAS[i]
        p2 = PARADAS[i + 1]

        x1, y1 = converter_para_xy_metros(p1["lat"], p1["lon"], lat_ref, lon_ref)
        x2, y2 = converter_para_xy_metros(p2["lat"], p2["lon"], lat_ref, lon_ref)

        dx = x2 - x1
        dy = y2 - y1

        comprimento_segmento = math.sqrt(dx ** 2 + dy ** 2)

        if comprimento_segmento == 0:
            continue

        t = ((px - x1) * dx + (py - y1) * dy) / (comprimento_segmento ** 2)
        t = max(0, min(1, t))

        proj_x = x1 + t * dx
        proj_y = y1 + t * dy

        distancia_segmento = math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
        progresso_ponto = progresso_acumulado + (t * comprimento_segmento)

        if distancia_segmento < melhor_distancia:
            melhor_distancia = distancia_segmento
            melhor_indice = i
            melhor_progresso = progresso_ponto

        progresso_acumulado += comprimento_segmento

    origem = PARADAS[melhor_indice]["nome"]
    destino = PARADAS[melhor_indice + 1]["nome"]

    trecho = f"Entre {origem} e {destino}"

    return trecho, melhor_indice, melhor_progresso, melhor_distancia


def identificar_parada_atual(latitude, longitude):
    parada, indice, distancia = encontrar_parada_mais_proxima(latitude, longitude)

    if distancia <= RAIO_PARADA_ATUAL_METROS:
        return parada["nome"], indice, distancia

    return "Em rota", indice, distancia


def normalizar_angulo(graus):
    if graus is None:
        return None
    return graus % 360


def diferenca_angular(angulo1, angulo2):
    return abs((angulo1 - angulo2 + 180) % 360 - 180)


def calcular_bearing(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_rad)

    y = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    )

    bearing = math.degrees(math.atan2(x, y))

    return normalizar_angulo(bearing)


def obter_heading_payload(payload):
    heading = converter_float(
        obter_valor(
            payload,
            [
                "heading",
                "course",
                "bearing",
                "direcao",
                "direção",
                "rumo",
                "azimute",
                "gps_heading",
                "gps_course"
            ]
        )
    )

    if heading is None:
        return None

    return normalizar_angulo(heading)


def identificar_sentido(
    latitude,
    longitude,
    progresso_atual,
    indice_trecho=None,
    heading=None,
    velocidade=None
):
    terminal_diadema = PARADAS[0]
    terminal_jabaquara = PARADAS[-1]

    if velocidade is None:
        velocidade = 0

    distancia_diadema = calcular_distancia_metros(
        latitude,
        longitude,
        terminal_diadema["lat"],
        terminal_diadema["lon"]
    )

    distancia_jabaquara = calcular_distancia_metros(
        latitude,
        longitude,
        terminal_jabaquara["lat"],
        terminal_jabaquara["lon"]
    )

    if distancia_diadema <= RAIO_SAIDA_TERMINAL_METROS:
        st.session_state["terminal_referencia"] = "diadema"
        st.session_state["sentido_atual"] = "Aguardando saída do Terminal Diadema"
        return st.session_state["sentido_atual"]

    if distancia_jabaquara <= RAIO_SAIDA_TERMINAL_METROS:
        st.session_state["terminal_referencia"] = "jabaquara"
        st.session_state["sentido_atual"] = "Aguardando saída do Terminal Jabaquara"
        return st.session_state["sentido_atual"]

    terminal_referencia = st.session_state.get("terminal_referencia")

    if terminal_referencia == "diadema" and distancia_diadema > RAIO_SAIDA_TERMINAL_METROS:
        st.session_state["sentido_atual"] = "Sentido Terminal Jabaquara"

    elif terminal_referencia == "jabaquara" and distancia_jabaquara > RAIO_SAIDA_TERMINAL_METROS:
        st.session_state["sentido_atual"] = "Sentido Terminal Diadema"

    if (
        heading is not None
        and indice_trecho is not None
        and 0 <= indice_trecho < len(PARADAS) - 1
        and velocidade >= VELOCIDADE_MINIMA_SENTIDO
    ):
        parada_origem = PARADAS[indice_trecho]
        parada_destino = PARADAS[indice_trecho + 1]

        bearing_sentido_jabaquara = calcular_bearing(
            parada_origem["lat"],
            parada_origem["lon"],
            parada_destino["lat"],
            parada_destino["lon"]
        )

        bearing_sentido_diadema = normalizar_angulo(
            bearing_sentido_jabaquara + 180
        )

        diferenca_jabaquara = diferenca_angular(
            heading,
            bearing_sentido_jabaquara
        )

        diferenca_diadema = diferenca_angular(
            heading,
            bearing_sentido_diadema
        )

        if min(diferenca_jabaquara, diferenca_diadema) <= 75:
            if diferenca_jabaquara <= diferenca_diadema:
                st.session_state["sentido_atual"] = "Sentido Terminal Jabaquara"
            else:
                st.session_state["sentido_atual"] = "Sentido Terminal Diadema"

            return st.session_state["sentido_atual"]

    progresso_anterior = st.session_state.get("progresso_rota_anterior")

    if progresso_anterior is not None and velocidade >= VELOCIDADE_MINIMA_SENTIDO:
        diferenca_progresso = progresso_atual - progresso_anterior

        if diferenca_progresso > RAIO_SAIDA_TERMINAL_METROS:
            st.session_state["sentido_atual"] = "Sentido Terminal Jabaquara"

        elif diferenca_progresso < -RAIO_SAIDA_TERMINAL_METROS:
            st.session_state["sentido_atual"] = "Sentido Terminal Diadema"

    return st.session_state.get("sentido_atual", "Aguardando deslocamento")


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
        self.client = None

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

    estado.client = client

    return estado


# ============================================================
# TABELA OPERACIONAL
# ============================================================

def criar_tabela_operacional(
    data_hora,
    indice_atual,
    embarque_atual="",
    desembarque_atual="",
    lotacao_atual=""
):
    linhas = []

    for indice, parada in enumerate(PARADAS):
        if indice_atual is not None and indice == indice_atual:
            data_hora_linha = "" if data_hora == "Aguardando dados" else data_hora
            embarque_linha = embarque_atual
            desembarque_linha = desembarque_atual
            lotacao_linha = lotacao_atual
        else:
            data_hora_linha = ""
            embarque_linha = ""
            desembarque_linha = ""
            lotacao_linha = ""

        linhas.append({
            "Data e Hora": data_hora_linha,
            "Terminal / Parada": parada["nome"],
            "Embarque": embarque_linha,
            "Desembarque": desembarque_linha,
            "Lotação Atual": lotacao_linha
        })

    return pd.DataFrame(linhas)


# ============================================================
# MAPA
# ============================================================

def criar_mapa(latitude_atual=None, longitude_atual=None):
    if latitude_atual is not None and longitude_atual is not None:
        centro_mapa = [latitude_atual, longitude_atual]
        zoom = 16
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
        opacity=0.8,
        popup="Linha 290 - Terminal Diadema / Terminal Jabaquara"
    ).add_to(mapa)

    for parada in PARADAS:
        folium.CircleMarker(
            location=[parada["lat"], parada["lon"]],
            radius=4,
            fill=True,
            fill_opacity=0.9,
            opacity=0.9,
            popup=parada["nome"]
        ).add_to(mapa)

    if latitude_atual is not None and longitude_atual is not None:
        folium.Marker(
            location=[latitude_atual, longitude_atual],
            popup=f"Posição atual do ônibus<br>Lat: {latitude_atual:.6f}<br>Lon: {longitude_atual:.6f}"
        ).add_to(mapa)

    return mapa


# ============================================================
# INICIALIZAÇÃO DO SESSION STATE
# ============================================================

if "progresso_rota_anterior" not in st.session_state:
    st.session_state["progresso_rota_anterior"] = None

if "sentido_atual" not in st.session_state:
    st.session_state["sentido_atual"] = "Aguardando deslocamento"

if "terminal_referencia" not in st.session_state:
    st.session_state["terminal_referencia"] = None


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

heading = obter_heading_payload(payload)

if velocidade_float is not None:
    velocidade = int(round(velocidade_float))
    velocidade_card = f"{velocidade} km/h"
else:
    velocidade = 0
    velocidade_card = "Aguardando dados"


data = obter_valor(
    payload,
    ["data", "date"],
    "Aguardando dados"
)

hora = obter_valor(
    payload,
    ["hora", "hora_local", "hora_brasil", "time"],
    "Aguardando dados"
)

data, hora = ajustar_data_hora(data, hora)

if data != "Aguardando dados" and hora != "Aguardando dados":
    data_hora = f"{data} {hora}"
else:
    data_hora = "Aguardando dados"


embarque_payload = obter_valor(
    payload,
    ["embarque", "embarques", "boarding", "entrada", "entradas"],
    None
)

desembarque_payload = obter_valor(
    payload,
    ["desembarque", "desembarques", "alighting", "saida", "saidas"],
    None
)

lotacao_payload = obter_valor(
    payload,
    ["lotacao", "lotação", "lotacao_atual", "lotação_atual", "ocupacao", "ocupação"],
    None
)


# ============================================================
# CÁLCULOS DO DASHBOARD
# ============================================================

if latitude is not None and longitude is not None:
    parada_atual, indice_parada_proxima, distancia_parada = identificar_parada_atual(
        latitude,
        longitude
    )

    trecho, indice_trecho, progresso_rota, distancia_trecho = calcular_progresso_rota(
        latitude,
        longitude
    )

    sentido = identificar_sentido(
        latitude,
        longitude,
        progresso_rota,
        indice_trecho=indice_trecho,
        heading=heading,
        velocidade=velocidade
    )

    st.session_state["progresso_rota_anterior"] = progresso_rota

    latitude_longitude = f"Lat: {latitude:.6f}\nLon: {longitude:.6f}"

    if parada_atual == "Em rota":
        indice_tabela = None
    else:
        indice_tabela = indice_parada_proxima

else:
    parada_atual = "Aguardando dados"
    indice_parada_proxima = None
    indice_tabela = None
    trecho = "Aguardando dados"
    sentido = "Aguardando dados"
    latitude_longitude = "Aguardando dados"


tabela_operacional = criar_tabela_operacional(
    data_hora=data_hora,
    indice_atual=indice_tabela,
    embarque_atual=valor_tabela(embarque_payload),
    desembarque_atual=valor_tabela(desembarque_payload),
    lotacao_atual=valor_tabela(lotacao_payload)
)


# ============================================================
# ESTILO VISUAL
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }

        .card-next {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 12px;
            padding: 10px 13px;
            height: 104px;
            max-height: 104px;
            margin-bottom: 10px;
            background: rgba(255, 255, 255, 0.02);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }

        .card-title-next {
            font-size: 0.78rem;
            opacity: 0.75;
            margin-bottom: 5px;
            line-height: 1.15;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .card-value-next {
            font-size: clamp(0.92rem, 1.05vw, 1.18rem);
            font-weight: 500;
            line-height: 1.18;
            word-break: break-word;
            white-space: normal;
        }

        div[data-testid="stDataFrame"] {
            font-size: 0.95rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# INTERFACE
# ============================================================

st.title("Painel de Controle Next Mobilidade")


# ============================================================
# CARDS PRINCIPAIS
# APENAS 6 CARDS, SEM REDUNDÂNCIA
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    exibir_card("Parada Atual", parada_atual)

with col2:
    exibir_card("Velocidade", velocidade_card)

with col3:
    exibir_card("Data e Hora", data_hora)


col4, col5, col6 = st.columns(3)

with col4:
    exibir_card("Latitude / Longitude", latitude_longitude)

with col5:
    exibir_card("Sentido", sentido)

with col6:
    exibir_card("Trecho", trecho)


# ============================================================
# TABELA OPERACIONAL
# ============================================================

st.subheader("Tabela operacional da linha")

st.dataframe(
    tabela_operacional,
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
    height=520,
    returned_objects=[]
)


# ============================================================
# STATUS TÉCNICO MQTT
# ============================================================

with st.expander("Status técnico MQTT"):
    st.write("Broker:", MQTT_BROKER)
    st.write("Porta:", MQTT_PORT)
    st.write("Tópico:", MQTT_TOPIC)
    st.write("Conectado:", "Sim" if snapshot["conectado"] else "Não")
    st.write("Última mensagem recebida:", snapshot["ultima_mensagem"])

    if heading is not None:
        st.write("Heading / Direção GPS:", f"{heading:.1f}°")
    else:
        st.write("Heading / Direção GPS:", "Aguardando dados")

    st.write("Último payload recebido:")
    st.json(payload)

    if snapshot["erro"]:
        st.error(snapshot["erro"])


# ============================================================
# ATUALIZAÇÃO AUTOMÁTICA
# ============================================================

time.sleep(INTERVALO_ATUALIZACAO)
st.rerun()
