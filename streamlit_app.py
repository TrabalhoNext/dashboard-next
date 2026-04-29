import json
import time
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh


# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Next Mobilidade Dashboard",
    page_icon="🚌",
    layout="wide"
)

# Atualização automática do painel
st_autorefresh(interval=3000, key="atualizacao_dashboard")


# =========================
# CONFIGURAÇÃO INTERNA MQTT
# =========================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 8000
MQTT_TOPIC = "next/linha290/onibus01/gps"
MQTT_WEBSOCKET_PATH = "/mqtt"


def ler_dados_reais():
    resultado = {"payload": None}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(MQTT_TOPIC)

    def on_message(client, userdata, msg):
        resultado["payload"] = msg.payload.decode("utf-8")

    client_id = f"dashboard_next_{int(time.time() * 1000)}"

    try:
        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                transport="websockets"
            )
        except Exception:
            client = mqtt.Client(
                client_id=client_id,
                transport="websockets"
            )

        client.ws_set_options(path=MQTT_WEBSOCKET_PATH)

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        inicio = time.time()

        while resultado["payload"] is None and time.time() - inicio < 4:
            time.sleep(0.1)

        client.loop_stop()
        client.disconnect()

        if resultado["payload"]:
            return json.loads(resultado["payload"])

        return None

    except Exception:
        return None


def formatar_horario(timestamp):
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# =========================
# ESTILO VISUAL
# =========================
st.markdown("""
<style>
.main-title {
    font-size: 2.2rem;
    font-weight: 700;
    margin-bottom: 0.8rem;
}
.card {
    background-color: #f8f9fa;
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    margin-bottom: 14px;
    min-height: 110px;
}
.card-title {
    font-size: 0.95rem;
    color: #555;
    margin-bottom: 8px;
    font-weight: 600;
}
.card-value {
    font-size: 1.20rem;
    font-weight: 700;
    color: #111;
    line-height: 1.35;
    word-wrap: break-word;
}
.section-title {
    font-size: 1.35rem;
    font-weight: 700;
    margin-top: 1rem;
    margin-bottom: 0.8rem;
}
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)


# =========================
# PARADAS OFICIAIS DA LINHA
# =========================
PARADAS = [
    {"ordem": 1, "nome": "Terminal Diadema", "lat": -23.682681458564325, "lon": -46.62691332328152},
    {"ordem": 2, "nome": "Parada Assembleia", "lat": -23.67697409771605, "lon": -46.627793033156586},
    {"ordem": 3, "nome": "Parada Divisa", "lat": -23.673551659194004, "lon": -46.63089933449298},
    {"ordem": 4, "nome": "Parada Vila Clara", "lat": -23.670446876785558, "lon": -46.63259010672355},
    {"ordem": 5, "nome": "Parada Bom Clima", "lat": -23.669120531442708, "lon": -46.63486429031358},
    {"ordem": 6, "nome": "Parada São José", "lat": -23.664882066923965, "lon": -46.63779830145058},
    {"ordem": 7, "nome": "Parada Americanópolis", "lat": -23.66095067269106, "lon": -46.637240408622645},
    {"ordem": 8, "nome": "Parada Faccini", "lat": -23.656897096071692, "lon": -46.63611395876546},
    {"ordem": 9, "nome": "Parada Encontro", "lat": -23.652614165456484, "lon": -46.63710571915031},
    {"ordem": 10, "nome": "Parada Cidade Vargas", "lat": -23.648791349310596, "lon": -46.64064538509645},
    {"ordem": 11, "nome": "Terminal Jabaquara", "lat": -23.646183664190886, "lon": -46.639878302287805},
]

paradas_df = pd.DataFrame(PARADAS)


# =========================
# LEITURA DOS DADOS
# =========================
dados_reais = ler_dados_reais()

if "historico_operacional" not in st.session_state:
    st.session_state["historico_operacional"] = []

if dados_reais:
    ultimo_timestamp = dados_reais.get("timestamp", "")

    ja_existe = any(
        item.get("timestamp") == ultimo_timestamp
        for item in st.session_state["historico_operacional"]
    )

    if not ja_existe:
        st.session_state["historico_operacional"].append(dados_reais)

    st.session_state["historico_operacional"] = st.session_state["historico_operacional"][-100:]


# =========================
# STATUS ATUAL DO ÔNIBUS
# =========================
if dados_reais:
    status_bus = {
        "linha": dados_reais.get("linha", "290 Diadema - Jabaquara"),
        "parada_atual": dados_reais.get("parada_atual", "Aguardando dados"),
        "parada_referencia": dados_reais.get("parada_referencia", "Aguardando dados"),
        "sentido": "Terminal Diadema → Terminal Jabaquara",
        "trecho": dados_reais.get("trecho", "Aguardando dados"),
        "horario": formatar_horario(dados_reais.get("timestamp", "")),
        "latitude": float(dados_reais.get("latitude", -23.682681458564325)),
        "longitude": float(dados_reais.get("longitude", -46.62691332328152)),
        "velocidade": float(dados_reais.get("velocidade_kmh", 0)),
        "embarque": int(dados_reais.get("embarque", 0)),
        "desembarque": int(dados_reais.get("desembarque", 0)),
        "pessoas_onibus": int(dados_reais.get("pessoas_onibus", 0)),
        "situacao": dados_reais.get("situacao", "Aguardando dados"),
        "satelites": dados_reais.get("satelites", 0),
    }
else:
    status_bus = {
        "linha": "290 Diadema - Jabaquara",
        "parada_atual": "Aguardando dados",
        "parada_referencia": "Aguardando dados",
        "sentido": "Terminal Diadema → Terminal Jabaquara",
        "trecho": "Aguardando dados",
        "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "latitude": -23.682681458564325,
        "longitude": -46.62691332328152,
        "velocidade": 0,
        "embarque": 0,
        "desembarque": 0,
        "pessoas_onibus": 0,
        "situacao": "Aguardando dados",
        "satelites": 0,
    }

parada_exibida = "Em rota" if status_bus["velocidade"] > 5 else status_bus["parada_atual"]


# =========================
# TABELA OPERACIONAL
# =========================
dados_tabela = []

for parada in PARADAS:
    dados_tabela.append({
        "Ordem": parada["ordem"],
        "Parada/Terminal": parada["nome"],
        "Horário": "-",
        "Situação": "-",
        "Embarque": 0,
        "Desembarque": 0,
        "Pessoas no ônibus": 0
    })

for leitura in st.session_state["historico_operacional"]:
    parada_ref = leitura.get("parada_referencia", "")

    for linha in dados_tabela:
        if linha["Parada/Terminal"] == parada_ref:
            linha["Horário"] = formatar_horario(leitura.get("timestamp", ""))
            linha["Situação"] = leitura.get("situacao", "-")
            linha["Embarque"] = int(leitura.get("embarque", 0))
            linha["Desembarque"] = int(leitura.get("desembarque", 0))
            linha["Pessoas no ônibus"] = int(leitura.get("pessoas_onibus", 0))

df_operacional = pd.DataFrame(dados_tabela)


# =========================
# TÍTULO
# =========================
st.markdown('<div class="main-title">Painel de Controle Next Mobilidade</div>', unsafe_allow_html=True)


# =========================
# CARDS SUPERIORES
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Ônibus / Linha</div>
        <div class="card-value">{status_bus["linha"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Parada atual</div>
        <div class="card-value">{parada_exibida}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Sentido</div>
        <div class="card-value">{status_bus["sentido"]}</div>
    </div>
    """, unsafe_allow_html=True)

col4, col5, col6 = st.columns(3)

with col4:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Trecho</div>
        <div class="card-value">{status_bus["trecho"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Horário</div>
        <div class="card-value">{status_bus["horario"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Localização</div>
        <div class="card-value">Latitude: {status_bus["latitude"]}<br>Longitude: {status_bus["longitude"]}</div>
    </div>
    """, unsafe_allow_html=True)

col7, col8, col9 = st.columns(3)

with col7:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Velocidade</div>
        <div class="card-value">{status_bus["velocidade"]:.1f} km/h</div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Fluxo de passageiros</div>
        <div class="card-value">Embarque: {status_bus["embarque"]}<br>Desembarque: {status_bus["desembarque"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col9:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Pessoas no ônibus</div>
        <div class="card-value">{status_bus["pessoas_onibus"]}</div>
    </div>
    """, unsafe_allow_html=True)


# =========================
# TABELA OPERACIONAL
# =========================
st.markdown('<div class="section-title">Tabela operacional por parada</div>', unsafe_allow_html=True)
st.dataframe(df_operacional, use_container_width=True, hide_index=True)


# =========================
# MAPA + GRÁFICO
# =========================
m1, m2 = st.columns(2)

with m1:
    st.markdown('<div class="section-title">Mapa com localização do ônibus</div>', unsafe_allow_html=True)

    mapa_df = pd.concat(
        [
            paradas_df[["nome", "lat", "lon"]].assign(tipo="Paradas"),
            pd.DataFrame([
                {
                    "nome": "Ônibus em operação",
                    "lat": status_bus["latitude"],
                    "lon": status_bus["longitude"],
                    "tipo": "Ônibus"
                }
            ])
        ],
        ignore_index=True
    )

    fig_mapa = px.scatter_mapbox(
        mapa_df,
        lat="lat",
        lon="lon",
        hover_name="nome",
        color="tipo",
        zoom=11.8,
        height=500
    )

    fig_mapa.update_layout(
        mapbox_style="open-street-map",
        margin=dict(l=0, r=0, t=0, b=0)
    )

    st.plotly_chart(fig_mapa, use_container_width=True)

with m2:
    st.markdown('<div class="section-title">Fluxo de embarque, desembarque e lotação</div>', unsafe_allow_html=True)

    fig_fluxo = go.Figure()

    fig_fluxo.add_trace(
        go.Bar(
            x=df_operacional["Parada/Terminal"],
            y=df_operacional["Embarque"],
            name="Embarque"
        )
    )

    fig_fluxo.add_trace(
        go.Bar(
            x=df_operacional["Parada/Terminal"],
            y=df_operacional["Desembarque"],
            name="Desembarque"
        )
    )

    fig_fluxo.add_trace(
        go.Scatter(
            x=df_operacional["Parada/Terminal"],
            y=df_operacional["Pessoas no ônibus"],
            mode="lines+markers",
            name="Pessoas no ônibus",
            yaxis="y2"
        )
    )

    fig_fluxo.update_layout(
        height=500,
        barmode="group",
        hovermode="x unified",
        xaxis=dict(
            title="Paradas e terminais",
            tickangle=-35,
            categoryorder="array",
            categoryarray=df_operacional["Parada/Terminal"].tolist()
        ),
        yaxis_title="Embarque e desembarque",
        yaxis2=dict(
            title="Pessoas no ônibus",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=20, r=20, t=40, b=80)
    )

    st.plotly_chart(fig_fluxo, use_container_width=True)
