#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project

from machine import Pin, ADC
import time
import neopixel
import onewire
import ds18x20



moistureSensor = ADC(Pin(27)) # sets up moisture sensor
levelSensor = ADC(Pin(26)) # sets up water level sensor
pump = Pin(8,Pin.OUT) # sets up water pump
OneWire = ds18x20.DS18X20(onewire.OneWire(Pin(17))) #Sets up temperature sensor, using MicroPython's OneWire library. Sensor connected to Pin 17
np = neopixel.NeoPixel(Pin(18), 2) #Sets up the on-board NeoPixel lights
roms = OneWire.scan() #Variable to store OneWire devices (the temperature sensor)
reserviorEmpty = False

def ReadTemp(): #Function to get temperature sensor value
    
    OneWire.convert_temp() #Converts into degress rather than a voltage.
    temp =  OneWire.read_temp(roms[0])
    #Shows a NeoPixel light based on the temperature
    if temp > 25:
        np[1] = (252, 98, 3)
    elif temp > 20 and temp < 25:
        np[1] = (252, 173, 3)
    elif temp >15 and temp <20:
        np[1] = (171, 235, 226)
    elif temp <15:
        np[1] = (43, 69, 240)
    np.write()
    return temp

def ReadMoisture(): #Function to get moisture value as a percentage
    print("About to read")
    rawMoisture = moistureSensor.read_u16()
    moisturePercentage = ((46500-rawMoisture)/(46500-27670))*100
    print(rawMoisture)
    print(moisturePercentage)
    return moisturePercentage

def CheckMoisture(): #Function to check if the plant needs watering
    global reserviorEmpty
    if moistureSensor.read_u16() > 42000 : #If it is too dry
        print("Too dry")
        if levelSensor.read_u16() > 29000: 
            np[0] = (0,255,0)
            np.write()
            pump.value(1)
            time.sleep(3)
            pump.value(0)
            reserviorEmpty = False
        else: #If there is no water in the reservior
            reserviorEmpty = True
            print("No water")
            np[0] = (255,0,0)
            np.write()
    elif moistureSensor.read_u16() < 36000 : #If it is too wet
        print("Too wet")
    else :
        pump.value(0)

def IsReserviorEmpty(): #Function to return whether reservior is empty
    return reserviorEmpty