#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
# NOTE: AI was used to assist the creation of this file


import ujson
from umqtt.simple import MQTTClient
from sensors import ReadMoisture, ReadTemp, CheckMoisture, IsReserviorEmpty
import time

# -----------------------------
# CONFIG
# -----------------------------
MQTT_PORT = 1883


# -----------------------------
# CONNECT & SUBSCRIBE
# -----------------------------
def connect(device_id, broker, callback=_default_callback): #Connects to MQTT client
    client = MQTTClient(device_id, broker, port=MQTT_PORT)
    client.set_callback(callback)
    client.connect()
    client.subscribe(f"plants/{device_id}/water_now")
    print("MQTT connected")
    return client

# -----------------------------
# PUBLISH HELPERS
# -----------------------------
def publish_status(client, device_id, moisture, temperature, status):
    payload = ujson.dumps({
        "moisture": moisture,
        "temperature": temperature,
        "reservior_empty" : status
    })
    client.publish(f"plants/{device_id}/status", payload) #Publishes moisture and temperature, and whether or not the reservior is empty

def publish_discovery(client, device_id, firmware="1.0.0"):
    payload = ujson.dumps({
        "id": device_id,
        "sensors": ["moisture", "temperature"],
        "firmware": firmware
    })
    client.publish("plants/discovery", payload)

# -----------------------------
# MAIN LOOP WRAPPER
# -----------------------------
def run(client, interval=15):
    while True:
        moisture = ReadMoisture()
        temperature = ReadTemp()
        empty = IsReserviorEmpty()
        publish_status(client, client.client_id, moisture, temperature, empty)
        CheckMoisture()
        client.check_msg()
        time.sleep(interval)
