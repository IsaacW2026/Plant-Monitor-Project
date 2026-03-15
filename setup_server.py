#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
#NOTE: AI was used to assist in the creation of this file

import socket
import time
import machine
from wifi import save_wifi

HTML_FORM = """\
HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<body>
<h2>Plant Sensor Setup</h2>
<style>
    body {
        font-family: Arial, sans-serif;
        background: #DCEAF7;
        margin: 0;
        padding: 20px;
    }

    h2 {
        text-align: center;
    }

    form {
        max-width: 350px;
        margin: 0 auto;
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }

    input {
        width: 100%;
        padding: 10px;
        margin-top: 8px;
        margin-bottom: 15px;
        border: 1px solid #ccc;
        border-radius: 8px;
        font-size: 16px;
    }

    input[type="submit"] {
        background: #4CAF50;
        color: white;
        border: none;
        cursor: pointer;
        font-size: 18px;
    }

    input[type="submit"]:active {
        background: #45a049;
    }
</style>
<form method="POST">
  WiFi SSID:<br>
  <input name="ssid"><br>
  Password:<br>
  <input name="password" type="password"><br><br>
  <input type="submit" value="Save">
</form>
</body>
</head>
</html>
"""

def parse_post(body):
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=")
            params[k] = v.replace("+", " ")
    return params

def start_setup_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print("Setup server running on 192.168.4.1")

    while True:
        cl, addr = s.accept()
        req = cl.recv(1024).decode()

        if "POST" in req:
            body = req.split("\r\n\r\n")[1]
            params = parse_post(body)
            ssid = params.get("ssid")
            password = params.get("password")
            save_wifi(ssid, password)
            cl.send("HTTP/1.1 200 OK\r\n\r\nSaved! Rebooting...")
            cl.close()
            time.sleep(1)
            machine.reset()

        cl.send(HTML_FORM)
        cl.close()