#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
# NOTE: AI was used to assist the creation of this file

# wifi.py
import network
import time
import ujson
import os

WIFI_FILE = "wifi.json"

def load_wifi(): #Load WiFi from JSON
    try:
        with open(WIFI_FILE, "r") as f:
            return ujson.load(f)
    except:
        return None

def save_wifi(ssid, password): #Save WiFi to JSON
    with open(WIFI_FILE, "w") as f:
        ujson.dump({"ssid": ssid, "password": password}, f)

def connect_wifi(ssid, password, timeout=25): #If saved WiFi

    # Fully disable AP mode
    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    time.sleep(0.3)

    # Reset STA mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(0.3)
    wlan.active(True)
    time.sleep(0.3)

    print("Connecting to:", ssid)

    wlan.connect(ssid, password)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            print("WiFi timeout")
            return False
        time.sleep(0.5)

    print("Connected:", wlan.ifconfig())
    return True

def start_ap(device_id): #If no saved Wi-Fi
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(
        essid=f"PlantSensor-{device_id}",
        password="plant123"
    )
    print("AP active at:", ap.ifconfig()[0])
    return ap