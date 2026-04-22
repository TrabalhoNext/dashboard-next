import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="Next Mobilidade Dashboard",
    page_icon="🚌",
    layout="wide"
)

# =========================
# ESTILO VISUAL
# =========================
st.markdown("""
<style>
.main-title {
    font-size: 2.2rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 1rem;
    color: #666;
    margin-bottom: 1.5rem;
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
    font-size: 1.25rem;
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
# DADOS DE DEMONSTRAÇÃO
# =========================

PARADAS = [
    {"ordem": 1, "nome": "Terminal Diadema", "lat": -23.682681458564325, "lon": -46.62691332328152},
    {"ordem": 2, "nome": "Parada Assembleia", "lat": -23.67697409771605, "lon": -46.627793033156586},
    {"ordem": 3, "nome": "Parada Divisa", "lat": -23.673551659194004, "lon": -46.63089933449298},
    {"ordem": 4, "nome": "Parada Vila Clara", "lat": -23.670446876785558, "lon": -46.63259010672355},
    {"ordem": 5, "nome": "Parada Cupecê", "lat": -23.66588383290862, "lon": -46.63728898894579},
    {"ordem": 6, "nome": "Parada Jabaquara 1", "lat": -23.65519735436502, "lon": -46.6418460739921},
    {"ordem": 7, "nome": "Parada Jabaquara 2", "lat": -23.65216223193791, "lon": -46.64074047186951},
    {"ordem": 8, "nome": "Parada Jabaquara 3", "lat": -23.649063115462504, "lon": -46.63955850332983},
    {"ordem": 9, "nome": "Parada Jabaquara 4", "lat": -23.64631977831234, "lon": -46.63850552722162},
    {"ordem": 10, "nome": "Parada Jabaquara 5", "lat": -23.643481093849828, "lon": -46.63738435364447},
    {"ordem": 11, "nome": "Terminal Jabaquara", "lat": -23.640436093181735, "lon": -46.63617672844406},
]

paradas_df = pd.DataFrame(PARADAS)

status_bus = {
    "linha": "290 Diadema - Jabaquara",
    "parada_atual": "Parada Cupecê",
    "sentido": "Terminal Diadema → Terminal Jabaquara",
    "trecho": "Parada Cupecê → Parada Jabaquara 1",
    "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    "latitude": -23.660900,
    "longitude": -46.640200,
    "embarque": 6,
    "desembarque": 1,
    "pessoas_onibus": 23,
    "situacao": "Parado"
}

dados_tabela = [
    {
        "Ordem": 1,
        "Parada/Terminal": "Terminal Diadema",
        "Horário": "07:10:00",
        "Situação": "Parado",
        "Trecho": "Terminal Diadema → Parada Assembleia",
        "Embarque": 8,
        "Desembarque": 0,
        "Pessoas no ônibus": 8
    },
    {
        "Ordem": 2,
        "Parada/Terminal": "Parada Assembleia",
        "Horário": "07:18:00",
        "Situação": "Parado",
        "Trecho": "Parada Assembleia → Parada Divisa",
        "Embarque": 4,
        "Desembarque": 1,
        "Pessoas no ônibus": 11
    },
    {
        "Ordem": 3,
        "Parada/Terminal": "Parada Divisa",
        "Horário": "07:28:00",
        "Situação": "Parado",
        "Trecho": "Parada Divisa → Parada Vila Clara",
        "Embarque": 7,
        "Desembarque": 2,
        "Pessoas no ônibus": 16
    },
    {
        "Ordem": 4,
        "Parada/Terminal": "Parada Vila Clara",
        "Horário": "07:34:00",
        "Situação": "Parado",
        "Trecho": "Parada Vila Clara → Parada Cupecê",
        "Embarque": 5,
        "Desembarque": 3,
        "Pessoas no ônibus": 18
    },
    {
        "Ordem": 5,
        "Parada/Terminal": "Parada Cupecê",
        "Horário": "07:40:00",
        "Situação": "Parado",
        "Trecho": "Parada Cupecê → Parada Jabaquara 1",
        "Embarque": 6,
        "Desembarque": 1,
        "Pessoas no ônibus": 23
    },
    {
        "Ordem": 6,
        "Parada/Terminal": "Parada Jabaquara 1",
        "Horário": "07:48:00",
        "Situação": "Parado",
        "Trecho": "Parada Jabaquara 1 → Parada Jabaquara 2",
        "Embarque": 3,
        "Desembarque": 4,
        "Pessoas no ônibus": 22
    },
    {
        "Ordem": 7,
        "Parada/Terminal": "Parada Jabaquara 2",
        "Horário": "07:52:00",
        "Situação": "Parado",
        "Trecho": "Parada Jabaquara 2 → Parada Jabaquara 3",
        "Embarque": 2,
        "Desembarque": 2,
        "Pessoas no ônibus": 22
    },
    {
        "Ordem": 8,
        "Parada/Terminal": "Parada Jabaquara 3",
        "Horário": "07:56:00",
        "Situação": "Parado",
        "Trecho": "Parada Jabaquara 3 → Parada Jabaquara 4",
        "Embarque": 1,
        "Desembarque": 3,
        "Pessoas no ônibus": 20
    },
    {
        "Ordem": 9,
        "Parada/Terminal": "Parada Jabaquara 4",
        "Horário": "08:00:00",
        "Situação": "Parado",
        "Trecho": "Parada Jabaquara 4 → Parada Jabaquara 5",
        "Embarque": 2,
        "Desembarque": 4,
        "Pessoas no ônibus": 18
    },
    {
        "Ordem": 10,
        "Parada/Terminal": "Parada Jabaquara 5",
        "Horário": "08:05:00",
        "Situação": "Parado",
        "Trecho": "Parada Jabaquara 5 → Terminal Jabaquara",
        "Embarque": 1,
        "Desembarque": 5,
        "Pessoas no ônibus": 14
    },
    {
        "Ordem": 11,
        "Parada/Terminal": "Terminal Jabaquara",
        "Horário": "08:12:00",
        "Situação": "Parado",
        "Trecho": "Terminal Jabaquara",
        "Embarque": 0,
        "Desembarque": 14,
        "Pessoas no ônibus": 0
    }
]

df_operacional = pd.DataFrame(dados_tabela)

# =========================
# TÍTULO
# =========================
st.markdown('<div class="main-title">Painel de Controle Next Mobilidade</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Dashboard operacional para monitoramento da linha com dados de GPS, embarque, desembarque, pessoas no ônibus e localização em mapa.</div>',
    unsafe_allow_html=True
)

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
        <div class="card-value">{status_bus["parada_atual"]}</div>
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
        <div class="card-title">Embarque</div>
        <div class="card-value">{status_bus["embarque"]}</div>
    </div>
    """, unsafe_allow_html=True)

with col8:
    st.markdown(f"""
    <div class="card">
        <div class="card-title">Desembarque</div>
        <div class="card-value">{status_bus["desembarque"]}</div>
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
        xaxis_title="Paradas e terminais",
        yaxis_title="Embarque e desembarque",
        yaxis2=dict(
            title="Pessoas no ônibus",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        margin=dict(l=20, r=20, t=20, b=20)
    )

    st.plotly_chart(fig_fluxo, use_container_width=True)

# =========================
# TABELA OPERACIONAL
# =========================
st.markdown('<div class="section-title">Tabela operacional por parada</div>', unsafe_allow_html=True)

st.dataframe(
    df_operacional,
    use_container_width=True,
    hide_index=True
)
