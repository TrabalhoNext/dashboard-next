from dash import Dash, html, dcc, Input, Output, dash_table
import plotly.graph_objects as go
from math import radians, sin, cos, sqrt, atan2
import paho.mqtt.client as mqtt
import json
import threading

app = Dash(__name__)
server = app.server
app.title = "Dashboard Next Mobilidade"

import os

BROKER = os.getenv("MQTT_HOST", "localhost")
PORTA = int(os.getenv("MQTT_PORT", "1883"))
TOPICO = os.getenv("MQTT_TOPIC", "next/linha290/dados") 
dados_lock = threading.Lock()


PARADAS_DECLARADAS = [
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
    {"nome": "Terminal Jabaquara", "lat": -23.646183664190886, "lon": -46.639878302287805}
]

def criar_tabela_operacional_inicial():
    tabela = []
    for parada in PARADAS_DECLARADAS:
        tabela.append({
            "parada_terminal": parada["nome"],
            "horario": "--:--:--",
            "embarque": 0,
            "desembarque": 0,
            "pessoas_no_onibus": 0
        })
    return tabela

eventos_operacionais = criar_tabela_operacional_inicial()

dados_onibus = {
    "linha": "290",
    "situacao": "Em movimento",
    "sentido": "Diadema → Jabaquara",
    "trecho_real": "Aguardando dados MQTT",
    "horario": "--:--:--",
    "embarque": 0,
    "desembarque": 0,
    "pessoas_no_onibus": 0,
    "latitude": -23.682681458564325,
    "longitude": -46.62691332328152
}

def card_style():
    return {
        "backgroundColor": "white",
        "padding": "20px",
        "borderRadius": "12px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.1)",
        "textAlign": "center",
        "fontFamily": "Arial",
        "color": "#1f2d3d"
    }

def box_style():
    return {
        "backgroundColor": "white",
        "padding": "20px",
        "borderRadius": "12px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.1)"
    }

def montar_card(titulo, valor):
    return [
        html.Div(
            titulo,
            style={
                "fontSize": "18px",
                "fontWeight": "bold",
                "marginBottom": "10px"
            }
        ),
        html.Div(
            str(valor),
            style={
                "fontSize": "20px",
                "fontWeight": "bold"
            }
        )
    ]

def distancia_metros(lat1, lon1, lat2, lon2):
    raio_terra = 6371000

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return raio_terra * c

def encontrar_parada_mais_proxima(lat_onibus, lon_onibus):
    parada_mais_proxima = None
    menor_distancia = float("inf")

    for parada in PARADAS_DECLARADAS:
        dist = distancia_metros(lat_onibus, lon_onibus, parada["lat"], parada["lon"])
        if dist < menor_distancia:
            menor_distancia = dist
            parada_mais_proxima = parada["nome"]

    return parada_mais_proxima, menor_distancia

def obter_parada_atual_por_estado(situacao, latitude, longitude):
    situacao = str(situacao).strip().lower()

    if situacao != "parado":
        return "Em deslocamento"

    parada, distancia = encontrar_parada_mais_proxima(latitude, longitude)

    if distancia <= 120:
        return parada

    return "Parada não identificada"

def atualizar_tabela_operacional(nome_parada, horario, embarque, desembarque, pessoas_no_onibus):
    for linha in eventos_operacionais:
        if linha["parada_terminal"] == nome_parada:
            linha["horario"] = horario
            linha["embarque"] = embarque
            linha["desembarque"] = desembarque
            linha["pessoas_no_onibus"] = pessoas_no_onibus
            break

def criar_grafico_resumo():
    with dados_lock:
        categorias = ["Embarque", "Desembarque", "Pessoas no Ônibus"]
        valores = [
            dados_onibus["embarque"],
            dados_onibus["desembarque"],
            dados_onibus["pessoas_no_onibus"]
        ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=categorias,
                y=valores,
                text=valores,
                textposition="outside"
            )
        ]
    )

    fig.update_layout(
        title="Resumo Operacional Atual",
        template="plotly_white",
        height=360,
        margin=dict(l=40, r=20, t=60, b=40),
        yaxis_title="Quantidade"
    )

    return fig

def criar_mapa():
    with dados_lock:
        latitude = dados_onibus["latitude"]
        longitude = dados_onibus["longitude"]
        linha = dados_onibus["linha"]

    fig = go.Figure(
        go.Scattermap(
            lat=[latitude],
            lon=[longitude],
            mode="markers+text",
            text=[f"Linha {linha}"],
            textposition="top right"
        )
    )

    fig.update_layout(
        title="Mapa da Posição Atual do Ônibus",
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        map=dict(
            style="open-street-map",
            center=dict(
                lat=latitude,
                lon=longitude
            ),
            zoom=13
        )
    )

    return fig

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Conectado ao broker MQTT com sucesso.")
        client.subscribe(TOPICO)
        print(f"Inscrito no tópico: {TOPICO}")
    else:
        print(f"Falha ao conectar ao broker. Código: {reason_code}")

def on_message(client, userdata, msg):
    try:
        mensagem = json.loads(msg.payload.decode("utf-8"))
        print("Mensagem MQTT recebida:")
        print(mensagem)

        with dados_lock:
            dados_onibus["linha"] = mensagem.get("linha", dados_onibus["linha"])
            dados_onibus["situacao"] = mensagem.get("situacao", dados_onibus["situacao"])
            dados_onibus["sentido"] = mensagem.get("sentido", dados_onibus["sentido"])
            dados_onibus["trecho_real"] = mensagem.get("trecho_real", dados_onibus["trecho_real"])
            dados_onibus["horario"] = mensagem.get("horario", dados_onibus["horario"])
            dados_onibus["embarque"] = mensagem.get("embarque", dados_onibus["embarque"])
            dados_onibus["desembarque"] = mensagem.get("desembarque", dados_onibus["desembarque"])
            dados_onibus["pessoas_no_onibus"] = mensagem.get("pessoas_no_onibus", dados_onibus["pessoas_no_onibus"])
            dados_onibus["latitude"] = mensagem.get("latitude", dados_onibus["latitude"])
            dados_onibus["longitude"] = mensagem.get("longitude", dados_onibus["longitude"])

            situacao = str(dados_onibus["situacao"]).strip().lower()
            latitude = float(dados_onibus["latitude"])
            longitude = float(dados_onibus["longitude"])
            horario = dados_onibus["horario"]
            embarque = dados_onibus["embarque"]
            desembarque = dados_onibus["desembarque"]
            pessoas = dados_onibus["pessoas_no_onibus"]

        if situacao == "parado":
            parada, distancia = encontrar_parada_mais_proxima(latitude, longitude)
            if distancia <= 120:
                atualizar_tabela_operacional(
                    nome_parada=parada,
                    horario=horario,
                    embarque=embarque,
                    desembarque=desembarque,
                    pessoas_no_onibus=pessoas
                )

    except Exception as e:
        print(f"Erro ao processar mensagem MQTT: {e}")

def iniciar_mqtt():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(BROKER, PORTA, 60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"Não foi possível conectar ao MQTT agora: {e}")
        return None

mqtt_client = iniciar_mqtt()

app.layout = html.Div(
    style={
        "fontFamily": "Arial",
        "backgroundColor": "#f4f6f9",
        "padding": "20px",
        "minHeight": "100vh"
    },
    children=[
        html.H1(
            "Painel de Controle Next Mobilidade",
            style={
                "textAlign": "center",
                "color": "#1f2d3d",
                "marginBottom": "10px"
            }
        ),

        html.P(
            "Estrutura inicial preparada para receber dados do ônibus via MQTT",
            style={
                "textAlign": "center",
                "fontSize": "18px",
                "marginBottom": "30px"
            }
        ),

        dcc.Interval(
            id="atualizacao",
            interval=1000,
            n_intervals=0
        ),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(3, 1fr)",
                "gap": "15px",
                "marginBottom": "30px"
            },
            children=[
                html.Div(id="card_onibus", style=card_style()),
                html.Div(id="card_parada_atual", style=card_style()),
                html.Div(id="card_sentido", style=card_style()),
                html.Div(id="card_trecho_real", style=card_style()),
                html.Div(id="card_horario", style=card_style()),
                html.Div(id="card_localizacao", style=card_style()),
                html.Div(id="card_embarque", style=card_style()),
                html.Div(id="card_desembarque", style=card_style()),
                html.Div(id="card_pessoas", style=card_style())
            ]
        ),

        html.Div(
            style={**box_style(), "marginBottom": "20px"},
            children=[
                html.H3(
                    "Tabela Operacional por Parada/Terminal",
                    style={
                        "marginTop": "0",
                        "color": "#1f2d3d",
                        "fontFamily": "Arial"
                    }
                ),
                dash_table.DataTable(
                    id="tabela_operacional",
                    columns=[
                        {"name": "Parada/Terminal", "id": "parada_terminal"},
                        {"name": "Horário", "id": "horario"},
                        {"name": "Embarque", "id": "embarque"},
                        {"name": "Desembarque", "id": "desembarque"},
                        {"name": "Pessoas no Ônibus", "id": "pessoas_no_onibus"}
                    ],
                    data=eventos_operacionais,
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#1f2d3d",
                        "color": "white",
                        "fontWeight": "bold",
                        "textAlign": "center",
                        "fontFamily": "Arial"
                    },
                    style_cell={
                        "textAlign": "center",
                        "padding": "12px",
                        "fontFamily": "Arial",
                        "fontSize": "15px",
                        "whiteSpace": "normal",
                        "height": "auto"
                    },
                    style_data={
                        "backgroundColor": "white",
                        "color": "#1f2d3d"
                    },
                    style_data_conditional=[
                        {
                            "if": {"row_index": "odd"},
                            "backgroundColor": "#f7f9fc"
                        }
                    ]
                )
            ]
        ),

        html.Div(
            style={**box_style(), "marginBottom": "20px"},
            children=[
                dcc.Graph(id="grafico_mapa")
            ]
        ),

        html.Div(
            style=box_style(),
            children=[
                dcc.Graph(id="grafico_resumo")
            ]
        )
    ]
)

@app.callback(
    Output("card_onibus", "children"),
    Output("card_parada_atual", "children"),
    Output("card_sentido", "children"),
    Output("card_trecho_real", "children"),
    Output("card_horario", "children"),
    Output("card_localizacao", "children"),
    Output("card_embarque", "children"),
    Output("card_desembarque", "children"),
    Output("card_pessoas", "children"),
    Output("tabela_operacional", "data"),
    Output("grafico_mapa", "figure"),
    Output("grafico_resumo", "figure"),
    Input("atualizacao", "n_intervals")
)
def atualizar_dashboard(n):
    with dados_lock:
        linha = dados_onibus["linha"]
        situacao = dados_onibus["situacao"]
        sentido = dados_onibus["sentido"]
        trecho_real = dados_onibus["trecho_real"]
        horario = dados_onibus["horario"]
        embarque = dados_onibus["embarque"]
        desembarque = dados_onibus["desembarque"]
        pessoas = dados_onibus["pessoas_no_onibus"]
        latitude = dados_onibus["latitude"]
        longitude = dados_onibus["longitude"]

    localizacao = f"Lat: {latitude} | Lon: {longitude}"
    parada_atual = obter_parada_atual_por_estado(situacao, latitude, longitude)

    return (
        montar_card("Ônibus", f"Linha {linha}"),
        montar_card("Parada Atual", parada_atual),
        montar_card("Sentido", sentido),
        montar_card("Trecho Real", trecho_real),
        montar_card("Horário", horario),
        montar_card("Localização", localizacao),
        montar_card("Embarque", embarque),
        montar_card("Desembarque", desembarque),
        montar_card("Pessoas no Ônibus", pessoas),
        [dict(linha) for linha in eventos_operacionais],
        criar_mapa(),
        criar_grafico_resumo()
    )

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050, use_reloader=False)