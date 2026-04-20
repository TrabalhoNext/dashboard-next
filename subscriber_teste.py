import paho.mqtt.client as mqtt

BROKER = "localhost"
PORTA = 1883
TOPICO = "next/linha290/dados"

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Conectado ao broker com sucesso.")
        client.subscribe(TOPICO)
        print(f"Inscrito no tópico: {TOPICO}")
    else:
        print(f"Falha ao conectar. Código: {reason_code}")

def on_message(client, userdata, msg):
    print("\nMensagem recebida:")
    print(f"Tópico: {msg.topic}")
    print(f"Conteúdo: {msg.payload.decode('utf-8')}")
    print("-" * 50)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

print("Tentando conectar ao broker...")
client.connect(BROKER, PORTA, 60)

print("Aguardando mensagens...")
client.loop_forever()