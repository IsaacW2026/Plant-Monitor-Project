#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
# NOTE: AI was used to assist the creation of this.


import os
import ujson
import ubinascii
def get_device_id():
    # If ID already exists, load it
    if "device_id.json" in os.listdir():
        with open("device_id.json") as f:
            return ujson.load(f)["id"]

    # Otherwise generate a new one
    raw = ubinascii.hexlify(os.urandom(6)).decode()
    device_id = "pico-" + raw

    # Save it
    with open("device_id.json", "w") as f:
        ujson.dump({"id": device_id}, f)

    return device_id