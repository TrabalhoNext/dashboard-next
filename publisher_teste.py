import json
import time
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORTA = 1883
TOPICO = "next/linha290/dados"

# ---------------------------------------------------
# PARADAS REAIS DA LINHA 290
# ---------------------------------------------------
PARADAS = [
    {"nome": "Terminal Diadema", "lat": -23.682681458564325, "lon": -46.62691332328152, "embarque": 4, "desembarque": 0},
    {"nome": "Parada Assembleia", "lat": -23.67697409771605, "lon": -46.627793033156586, "embarque": 3, "desembarque": 1},
    {"nome": "Parada Divisa", "lat": -23.673551659194004, "lon": -46.63089933449298, "embarque": 2, "desembarque": 1},
    {"nome": "Parada Vila Clara", "lat": -23.670446876785558, "lon": -46.63259010672355, "embarque": 1, "desembarque": 0},
    {"nome": "Parada Bom Clima", "lat": -23.669120531442708, "lon": -46.63486429031358, "embarque": 3, "desembarque": 2},
    {"nome": "Parada São José", "lat": -23.664882066923965, "lon": -46.63779830145058, "embarque": 2, "desembarque": 1},
    {"nome": "Parada Americanópolis", "lat": -23.66095067269106, "lon": -46.637240408622645, "embarque": 1, "desembarque": 2},
    {"nome": "Parada Faccini", "lat": -23.656897096071692, "lon": -46.63611395876546, "embarque": 2, "desembarque": 1},
    {"nome": "Parada Encontro", "lat": -23.652614165456484, "lon": -46.63710571915031, "embarque": 1, "desembarque": 3},
    {"nome": "Parada Cidade Vargas", "lat": -23.648791349310596, "lon": -46.64064538509645, "embarque": 1, "desembarque": 2},
    {"nome": "Terminal Jabaquara", "lat": -23.646183664190886, "lon": -46.639878302287805, "embarque": 0, "desembarque": 5}
]

# ---------------------------------------------------
# DIREÇÃO DA ROTA
# ---------------------------------------------------
SENTIDO = "Diadema → Jabaquara"

# ---------------------------------------------------
# FUNÇÃO DE CONEXÃO MQTT
# ---------------------------------------------------
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Conectado ao broker MQTT com sucesso.")
    else:
        print(f"Falha ao conectar. Código: {reason_code}")

# ---------------------------------------------------
# PUBLICAR MENSAGEM
# ---------------------------------------------------
def publicar(client, mensagem):
    mensagem_json = json.dumps(mensagem, ensure_ascii=False)
    resultado = client.publish(TOPICO, mensagem_json)

    if resultado.rc == 0:
        print("Mensagem enviada com sucesso:")
        print(mensagem_json)
        print("-" * 60)
    else:
        print("Erro ao enviar mensagem.")

# ---------------------------------------------------
# CALCULAR PONTO MÉDIO ENTRE DUAS PARADAS
# ---------------------------------------------------
def ponto_medio(parada_atual, proxima_parada):
    lat = (parada_atual["lat"] + proxima_parada["lat"]) / 2
    lon = (parada_atual["lon"] + proxima_parada["lon"]) / 2
    return lat, lon

# ---------------------------------------------------
# CLIENTE MQTT
# ---------------------------------------------------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect

print("Tentando conectar ao broker...")
client.connect(BROKER, PORTA, 60)
client.loop_start()

# ---------------------------------------------------
# LÓGICA DA SIMULAÇÃO
# ---------------------------------------------------
pessoas_no_onibus = 0

try:
    # passa por todas as paradas da rota
    for i in range(len(PARADAS)):
        parada_atual = PARADAS[i]

        # atualiza quantidade de pessoas ao parar na parada
        pessoas_no_onibus += parada_atual["embarque"]
        pessoas_no_onibus -= parada_atual["desembarque"]

        if pessoas_no_onibus < 0:
            pessoas_no_onibus = 0

        # monta trecho real quando está parado
        if i == 0:
            trecho_real = f"Início da rota em {parada_atual['nome']}"
        else:
            trecho_real = f"{PARADAS[i-1]['nome']} → {parada_atual['nome']}"

        # publica mensagem de ônibus parado na parada
        mensagem_parado = {
            "linha": "290",
            "situacao": "Parado",
            "sentido": SENTIDO,
            "trecho_real": trecho_real,
            "embarque": parada_atual["embarque"],
            "desembarque": parada_atual["desembarque"],
            "pessoas_no_onibus": pessoas_no_onibus,
            "latitude": parada_atual["lat"],
            "longitude": parada_atual["lon"],
            "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

        publicar(client, mensagem_parado)
        time.sleep(5)

        # se ainda existe próxima parada, publica mensagem em movimento
        if i < len(PARADAS) - 1:
            proxima_parada = PARADAS[i + 1]
            lat_meio, lon_meio = ponto_medio(parada_atual, proxima_parada)

            mensagem_movimento = {
                "linha": "290",
                "situacao": "Em movimento",
                "sentido": SENTIDO,
                "trecho_real": f"{parada_atual['nome']} → {proxima_parada['nome']}",
                "embarque": 0,
                "desembarque": 0,
                "pessoas_no_onibus": pessoas_no_onibus,
                "latitude": lat_meio,
                "longitude": lon_meio,
                "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }

            publicar(client, mensagem_movimento)
            time.sleep(5)

    print("Simulação concluída.")

except KeyboardInterrupt:
    print("\nEncerrando publisher...")

finally:
    client.loop_stop()
    client.disconnect()