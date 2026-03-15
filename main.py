##Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
#NOTE: AI was used to assist the creation of this code

from wifi import load_wifi, connect_wifi, start_ap
from setup_server import start_setup_server
from mqtt_client import connect, publish_discovery, run
from sensors import CheckMoisture
from device_ID import get_device_id
import neopixel
from machine import Pin

np = neopixel.NeoPixel(Pin(18), 2) #Sets up the on-board NeoPixel lights

BROKER = "<PI4 IP Address>"
np[0] = (0,255,0)
np.write()

def setup_mode(): #If there are no stored Wi-Fi credentials
    device_id = get_device_id()
    start_ap(device_id)
    start_setup_server()

def normal_mode(creds): #If there are stored Wi-Fi credentials
    if not connect_wifi(creds["ssid"], creds["password"]):
        setup_mode()
        return

    device_id = get_device_id()
    client = connect(device_id, BROKER)
    publish_discovery(client, device_id)
    print("Starting")
    run(client)

def main(): 
    creds = load_wifi()
    if creds:
        normal_mode(creds)
    else:
        setup_mode()

main()
