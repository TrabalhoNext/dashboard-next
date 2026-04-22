import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="Next Mobilidade Dashboard",
    page_icon="🚌",
    layout="wide",
)

st.markdown(
    """
    <style>
    div[data-testid="stMetricLabel"] {
        font-size: 0.95rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================
# DADOS INICIAIS DE DEMONSTRAÇÃO
# =============================
# Esta versão foi preparada para publicação inicial no Streamlit.
# Depois, ela pode ser conectada aos dados reais do GPS, MQTT e contagem.

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

# Valores de demonstração
status_bus = {
    "linha": "290 Diadema - Jabaquara",
    "sentido": "Terminal Diadema → Terminal Jabaquara",
    "trecho": "Parada Cupecê → Parada Jabaquara 1",
    "situacao": "Em movimento",
    "velocidade": 4.2,
    "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    "lat": -23.6609,
    "lon": -46.6402,
    "passageiros_atual": 23,
    "embarques_total": 41,
    "desembarques_total": 18,
}

operacao_df = pd.DataFrame([
    {"Parada": "Terminal Diadema", "Embarques": 8, "Desembarques": 0, "Passageiros após parada": 8},
    {"Parada": "Parada Assembleia", "Embarques": 4, "Desembarques": 1, "Passageiros após parada": 11},
    {"Parada": "Parada Divisa", "Embarques": 7, "Desembarques": 2, "Passageiros após parada": 16},
    {"Parada": "Parada Vila Clara", "Embarques": 5, "Desembarques": 3, "Passageiros após parada": 18},
    {"Parada": "Parada Cupecê", "Embarques": 6, "Desembarques": 1, "Passageiros após parada": 23},
    {"Parada": "Parada Jabaquara 1", "Embarques": 3, "Desembarques": 4, "Passageiros após parada": 22},
])

historico_df = pd.DataFrame([
    {"Horário": "07:10", "Evento": "Saída registrada", "Local": "Terminal Diadema", "Situação": "Em movimento"},
    {"Horário": "07:18", "Evento": "Parada registrada", "Local": "Parada Assembleia", "Situação": "Parado"},
    {"Horário": "07:19", "Evento": "Embarque/Desembarque", "Local": "Parada Assembleia", "Situação": "+4 / -1"},
    {"Horário": "07:28", "Evento": "Parada registrada", "Local": "Parada Divisa", "Situação": "Parado"},
    {"Horário": "07:29", "Evento": "Embarque/Desembarque", "Local": "Parada Divisa", "Situação": "+7 / -2"},
    {"Horário": "07:40", "Evento": "GPS em operação", "Local": "Parada Cupecê → Parada Jabaquara 1", "Situação": "Em movimento"},
])

# =============================
# SIDEBAR
# =============================
st.sidebar.title("Painel de Controle")
st.sidebar.markdown("Projeto Next Mobilidade")

modo_exibicao = st.sidebar.radio(
    "Modo de exibição",
    ["Demonstração", "Operacional"],
    index=0,
)

atualizacao = st.sidebar.slider(
    "Intervalo visual de atualização (segundos)",
    min_value=1,
    max_value=30,
    value=5,
)

st.sidebar.info(
    "Esta primeira versão está preparada para publicação pública. "
    "Depois, o painel poderá ser conectado ao GPS real, MQTT e contagem de pessoas."
)

# =============================
# TOPO
# =============================
st.title("🚌 Dashboard Operacional - Next Mobilidade")
st.caption("Monitoramento da linha, GPS, embarque, desembarque e ocupação do ônibus")

col1, col2 = st.columns(2)
col1.metric("Linha", status_bus["linha"])
col2.metric("Situação", status_bus["situacao"])

col3, col4 = st.columns(2)
col3.metric("Velocidade", f'{status_bus["velocidade"]:.1f} km/h')
col4.metric("Passageiros atuais", status_bus["passageiros_atual"])

col5, col6 = st.columns(2)
col5.metric("Embarques totais", status_bus["embarques_total"])
col6.metric("Desembarques totais", status_bus["desembarques_total"])

col7, col8 = st.columns(2)
col7.metric("Sentido", status_bus["sentido"])
col8.metric("Última atualização", status_bus["horario"])


st.markdown("---")

# =============================
# BLOCO PRINCIPAL
# =============================
a, b = st.columns([1.3, 1])

with a:
    st.subheader("Posição e trajeto da linha")

    mapa_df = pd.concat(
        [
            paradas_df[["nome", "lat", "lon"]].assign(tipo="Paradas"),
            pd.DataFrame([
                {
                    "nome": "Ônibus em operação",
                    "lat": status_bus["lat"],
                    "lon": status_bus["lon"],
                    "tipo": "Ônibus",
                }
            ]),
        ],
        ignore_index=True,
    )

    fig_mapa = px.scatter_mapbox(
        mapa_df,
        lat="lat",
        lon="lon",
        hover_name="nome",
        color="tipo",
        zoom=11.8,
        height=500,
    )
    fig_mapa.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_mapa, use_container_width=True)

with b:
    st.subheader("Resumo operacional")
    st.markdown(f"**Trecho atual:** {status_bus['trecho']}")
    st.markdown(f"**Sentido da viagem:** {status_bus['sentido']}")
    st.markdown(f"**Coordenadas atuais:** {status_bus['lat']}, {status_bus['lon']}")
    st.markdown(f"**Modo do painel:** {modo_exibicao}")
    st.markdown(f"**Atualização visual definida:** {atualizacao} s")

    st.success("Preparado para integrar GPS, contagem de pessoas, embarque e desembarque.")

    st.subheader("Próximos módulos")
    st.write("- Leitura em tempo real do GPS")
    st.write("- Integração com MQTT")
    st.write("- Contagem de passageiros no ônibus")
    st.write("- Embarque e desembarque por parada")
    st.write("- Histórico operacional")

st.markdown("---")

# =============================
# GRÁFICOS
# =============================
g1, g2 = st.columns(2)

with g1:
    st.subheader("Embarques e desembarques por parada")
    grafico_movimento = operacao_df.melt(
        id_vars="Parada",
        value_vars=["Embarques", "Desembarques"],
        var_name="Tipo",
        value_name="Quantidade",
    )
    fig_bar = px.bar(
        grafico_movimento,
        x="Parada",
        y="Quantidade",
        color="Tipo",
        barmode="group",
        height=430,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with g2:
    st.subheader("Ocupação do ônibus após cada parada")
    fig_line = go.Figure()
    fig_line.add_trace(
        go.Scatter(
            x=operacao_df["Parada"],
            y=operacao_df["Passageiros após parada"],
            mode="lines+markers",
            name="Passageiros",
        )
    )
    fig_line.update_layout(height=430, xaxis_title="Parada", yaxis_title="Passageiros")
    st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")

# =============================
# TABELAS
# =============================
t1, t2 = st.columns(2)

with t1:
    st.subheader("Tabela operacional por parada")
    st.dataframe(operacao_df, use_container_width=True, hide_index=True)

with t2:
    st.subheader("Histórico resumido")
    st.dataframe(historico_df, use_container_width=True, hide_index=True)

st.markdown("---")

# =============================
# RODAPÉ
# =============================
st.markdown(
    """
    **Observação:** esta é a base inicial do dashboard em Streamlit para publicação pública.  
    Na próxima etapa, os dados simulados poderão ser substituídos por dados reais vindos do Raspberry Pi 5,
    GPS GY-NEO6MV2, MQTT e do módulo de detecção e contagem de passageiros.
    """
)






  




