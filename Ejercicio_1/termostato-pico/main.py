from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import dht, machine, json
import random
import ujson
import machine

CONFIG_FILE = "config.json"

id = ""
for b in machine.unique_id():
    id += "{:02X}".format(b)
print("El ID del dispositivo actual es: {}".format(id))


def guardar_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            ujson.dump({"setpoint": setpoint, "periodo": periodo, "modo": modo, "relay": relay_state}, f)
        print("Configuracion guardada")
    except Exception as e:
        print("No se pudo guardar la configuracion:", e)

def cargar_config():
    global setpoint, periodo, modo, relay_state
    try:
        with open(CONFIG_FILE, "r") as f:
            data = ujson.load(f)
            setpoint = data.get("setpoint", 25)  # Valor por defecto 25°C
            periodo = data.get("periodo", 10)  # Periodo por defecto 10s
            modo = data.get("modo", 0)  # Modo manual por defecto
            relay_state = data.get("relay", 0)  # Relé apagado por defecto
        print("Configuracion cargada:", data)
    except Exception as e:
        print("No se encontro configuracion previa. Usando valores por defecto.")
        guardar_config()


# class FakeDHT22:
#     def measure(self):
#         pass  # No hace nada, solo simula la medición
    
#     def temperature(self):
#         return round(random.uniform(20, 30), 2)  # Simula valores entre 20°C y 30°C
    
#     def humidity(self):
#         return round(random.uniform(40, 70), 2)  # Simula valores de humedad entre 40% y 70%

# d = FakeDHT22()  # Reemplaza el sensor real por el simulado

# class FakePin:
#     def __init__(self, pin, mode=None):
#         self.state = 0  # Estado inicial apagado
    
#     def value(self, val=None):
#         if val is not None:
#             self.state = val
#             print(f"[SIMULACION] Relay {'ENCENDIDO' if val else 'APAGADO'}")
#         return self.state

# relay = FakePin(15)
#led = FakePin(2)
 

# Variables globales
setpoint = 25  # Setpoint inicial
periodo = 10  # Periodo de muestreo
modo = 0  # 0: Manual, 1: Automático
relay_state = 0  # Estado inicial del relé

cargar_config()  # Intentar cargar la configuración guardada

# Configuración de pines
SENSOR_PIN = 16
RELAY_PIN = 15

d = dht.DHT11(machine.Pin(SENSOR_PIN))
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
led = machine.Pin("LED", machine.Pin.OUT)
relay.value(relay_state)
async def destellar_led():
    for _ in range(5):  # Parpadear 5 veces
        led.on()
        await asyncio.sleep(0.3)  # LED encendido 300ms
        led.off()
        await asyncio.sleep(0.3)  # LED apagado 300ms

def sub_cb(topic, msg, retained):
    global setpoint, periodo, modo, relay_state
    topic = topic.decode()
    msg = msg.decode()
    
    if topic.endswith("/setpoint"):
        setpoint = int(msg)
        print(f"Nuevo setpoint: {setpoint}°C")
    elif topic.endswith("/periodo"):
        periodo = int(msg)
        print(f"Nuevo periodo: {periodo}s")
    elif topic.endswith("/modo"):
        modo = int(msg)
        print(f"Nuevo modo: {'Automatico' if modo == 1 else 'Manual'}")
    elif topic.endswith("/relay"):
        relay_state = int(msg)
        relay.value(relay_state)
        print(f"Relay {'ENCENDIDO' if relay_state else 'APAGADO'}")
    elif topic.endswith("/destello"):
        print("Destello activado")
        asyncio.create_task(destellar_led())
    
    guardar_config()  # Guardar cambios en el archivo


async def wifi_han(state):
    print('WiFi', 'conectado' if state else 'desconectado')
    await asyncio.sleep(1)

async def conn_han(client):
    base_topic = "D3B1D0A8558CF93D"
    for sub in ["setpoint", "periodo", "destello", "modo", "relay"]:
        await client.subscribe(f"{base_topic}/{sub}", 1)

async def main(client):
    global relay_state
    await client.connect()
    await asyncio.sleep(2)
    
    while True:
        try:
            d.measure()
            temp = d.temperature()
            hum = d.humidity()
            
            if modo == 1:  # Automático
                relay_state = 1 if temp >= setpoint else 0
                relay.value(relay_state)
            
            data = {
                "temperatura": temp,
                "humedad": hum,
                "setpoint": setpoint,
                "periodo": periodo,
                "modo": modo,
                "relay": relay_state
            }
            await client.publish("D3B1D0A8558CF93D", json.dumps(data), qos=1)
            
        except OSError:
            print("Error al leer el sensor")
        
        await asyncio.sleep(periodo)

config.update({
    'subs_cb': sub_cb,
    'connect_coro': conn_han,
    'wifi_coro': wifi_han,
    'ssl': True
})

MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
