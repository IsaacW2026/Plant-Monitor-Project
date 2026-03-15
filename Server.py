#Developed by Abbeygate Sixth Form College for the PA Raspberry Pi Competition
#Plant Monitor Project
# NOTE: AI was used to help create this project

#Imports
import threading
import time
import json
import sqlite3
from flask import Flask, jsonify, request
from paho.mqtt.client import Client
import requests


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
DB = "plants.db" #tells the program which database to access from
MQTT_BROKER = "localhost" #The MQTT server runs on the same Pi, so we can use localhost
DISCOVERY_TOPIC = "plants/discovery" 
devices = {}   # id -> {info, latest}


#Function that gets called to send a mobile notification
def send_notification(title, message):
    requests.post(URL, data=message)


# DB SETUP
def db_connect():
    return sqlite3.connect(DB, check_same_thread=False)

db = db_connect()
cursor = db.cursor()

# Ensure that the tabels exist, if they don't make new tables in the datavase
cursor.execute("""
CREATE TABLE IF NOT EXISTS devices ( 
    id TEXT PRIMARY KEY,
    info_json TEXT 
)
""") #To store known devices
cursor.execute("""
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    timestamp REAL,
    moisture REAL,
    temperature REAL
)
""") # To store previous readings

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""") # To store API keys and configuration

db.commit()

# Load nfty details from database
def load_settings():
    global URL
    cursor.execute("SELECT value FROM settings WHERE key = 'URL'")
    result = cursor.fetchone()
    URL = result[0] if result else None

load_settings()
def load_devices_from_db(): #Loads existing Picos from database
    cursor.execute("SELECT id, info_json, friendly_name FROM devices")
    for device_id, info_json, friendly_name in cursor.fetchall():
        devices[device_id] = {
            "info": json.loads(info_json),
            "latest": None,
            "friendly_name" : friendly_name or device_id #The name the user gives the device!
        }

load_devices_from_db()

# ---------------------------------------------------
# MQTT CALLBACK
# ---------------------------------------------------
def on_message(client, userdata, msg): #Function called when there is a new MQTT message
    topic = msg.topic 
    payload = msg.payload.decode() #Contents of the message

    # Discovery of new sensor picos
    if topic == DISCOVERY_TOPIC:
        info = json.loads(payload)
        device_id = info["id"]

        if device_id not in devices: #Saves device ID
            devices[device_id] = {
                "info": info,
                "latest": None,
            }

        cursor.execute( #Adds new device IDs to the SQL database
            "INSERT OR REPLACE INTO devices (id, info_json) VALUES (?, ?)",
            (device_id, json.dumps(info))
        )
        db.commit()

        status_topic = f"plants/{device_id}/status"
        client.subscribe(status_topic)
        print(f"[MQTT] Subscribed to {status_topic}") #Subscribes to new device's MQTT feed
        return

    # New reading
    if "/status" in topic:
        device_id = topic.split("/")[1]
        data = json.loads(payload)

        # Get friendly name (fallback to ID)
        name = devices.get(device_id, {}).get("friendly_name", device_id)
        # Attach a timestamp and store as latest
        data["timestamp"] = time.time()
        devices.setdefault(device_id, {"info": {}, "latest": None})
        devices[device_id]["latest"] = data

        #Delete readings older than 7 days, so the database doesn't get too large
        cutoff = time.time() - (7 * 24 * 60 * 60)

        cursor.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))
        
        # Store new values in DB (single insert)
        cursor.execute(
            "INSERT INTO readings (device_id, timestamp, moisture, temperature) VALUES (?, ?, ?, ?)",
            (device_id, data["timestamp"], data["moisture"], data["temperature"])
        )
        db.commit() #Commit to database

        # Send a mobile notification via ntfy if the temperature drops below the threshold
        if (data.get("temperature") is not None and data["temperature"] < 10) or data.get("temperature") is not None and data["temperature"] > 25: 
            send_notification(
                f"Low temperature on {name}",
                f"{name} is at {data['temperature']}°C"
            )
        # Send a mobile notification if the reservior has run out of water
        if (data.get("reservior_empty") is not None and data["reservior_empty"] == True):
            send_notification(
                f"Reservior empty on {name}",
                f"{name} has run out of water"
            )


# ---------------------------------------------------
# MQTT THREAD
# ---------------------------------------------------
def mqtt_thread():
    client = Client() #Initilises MQTT client, for receiving data
    client.on_message = on_message #Tells the MQTT client to call the on_mesage function when a new message is recieved
    client.connect(MQTT_BROKER)

    client.subscribe(DISCOVERY_TOPIC) # Subscribe to topic for finding new devices
    client.loop_forever() #Always recieve new messages

# ---------------------------------------------------
# Webserver
# ---------------------------------------------------
app = Flask(__name__) #Starts a new Flask webserver

@app.get("/api/devices") #Returns the devices to display on the dashboard
def api_devices():
    return jsonify([
        {
            "id": device_id,
            "name": devices[device_id].get("friendly_name", device_id)
        }
        for device_id in devices
    ])

@app.get("/api/<device_id>/latest") #Gets the latest readings from each device
def api_latest(device_id):
    latest = devices[device_id]["latest"]
    if latest:
        return jsonify({
            "moisture": latest.get("moisture"),
            "temperature": latest.get("temperature"),
            "timestamp": latest.get("timestamp"),
            "reservior" : latest.get("reservior_empty") # Using .get() prevents crashes
        })
    return jsonify(None)

@app.get("/api/<device_id>/history") #Gets previous readings from SQL Lite
def api_history(device_id):
    cursor.execute(
        "SELECT timestamp, moisture, temperature FROM readings WHERE device_id = ? ORDER BY timestamp DESC LIMIT 20",
        (device_id,) #Only shows the last 10 readings (uses 20 because mositure and temperature seem to be classed as a different entry)
    )
    rows = cursor.fetchall()

    return jsonify([ #Adds the time for each reading
        {"time": ts * 1000, "moisture": m, "temperature": t}
        for ts, m, t in rows[::-1]
    ])

@app.post("/api/<device_id>/name") #Adds the 'friendly' name to the database
def api_set_name(device_id):
    new_name = request.json.get("name")

    cursor.execute(
        "UPDATE devices SET friendly_name = ? WHERE id = ?",
        (new_name, device_id)
    )
    db.commit()

    # Update in-memory copy
    if device_id in devices:
        devices[device_id]["friendly_name"] = new_name

    return jsonify({"status": "ok", "device": device_id, "name": new_name})

@app.get("/api/settings") #Get current settings
def api_get_settings():
    cursor.execute("SELECT key, value FROM settings")
    settings_dict = {key: value for key, value in cursor.fetchall()}
    return jsonify({
        "URL": settings_dict.get("URL"),
    })

@app.post("/api/settings") #Save settings
def api_save_settings():
    global URL
    data = request.json
    
    # Save Pushover user
    if "URL" in data:
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("URL", data["URL"])
        )
    
    db.commit()
    load_settings()  # Reload settings into memory
    
    return jsonify({"status": "ok"})
@app.delete("/api/device/<device_id>")
def api_delete_device(device_id):
    # Remove from DB
    cursor.execute("DELETE FROM readings WHERE device_id = ?", (device_id,))
    cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    db.commit()

    # Remove from memory
    if device_id in devices:
        del devices[device_id]

    return jsonify({"status": "ok", "deleted": device_id})
# ---------------------------------------------------
# DASHBOARD HTML, used for displaying readings and re-naming the devices
# ---------------------------------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Plant Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
</head>
<body style="font-family: Arial; margin: 40px;background: #DCEAF7;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h1>Plant Sensor Dashboard</h1>
        <a href="/settings" style="padding: 10px 20px; background: #2196F3; color: white; text-decoration: none; border-radius: 4px;">⚙️ Settings</a>
    </div>

    <div id="device-list"></div>

    <script>
        async function loadDevices() {
            const devices = await fetch("/api/devices").then(r => r.json());
            const container = document.getElementById("device-list");
            container.innerHTML = "";
            devices.forEach(device => {
                const id = device.id;
                const name = device.name
                const div = document.createElement("div");
                div.innerHTML = `
                    <h2>${name}</h2>
                    <p>Moisture: <span id="${id}-moisture">--</span></p>
                    <p>Temperature: <span id="${id}-temp">--</span></p>
                    <p>Last update: <span id="${id}-time">--</span></p>
                    <p>Reservior Empty: <span id="${id}-reservior">--</span></p>
                    <input id="${id}-newname" placeholder="Enter new name">
                    <button onclick="renameDevice('${id}')">Save Name</button>
                    <button onclick="deleteDevice('${id}')"
                    style="background:#c62828;color:white;border:none;padding:8px 12px;border-radius:6px;margin-top:10px;">
                    Delete Device
                    </button>
                    <canvas id="${id}-chart" width="600" height="200"></canvas>
                    <div id="${id}-history" style="margin-top:8px;font-size:0.9em;color:#333"></div>
                `;
                container.appendChild(div);

                createChart(id);
            });
        }
        async function loadInitialHistory(id) {
        const hist = await fetch(`/api/${id}/history`).then(r => r.json());
        const chart = charts[id];

        chart.data.labels = hist.map(h => h.time);
        chart.data.datasets[0].data = hist.map(h => h.moisture);
        chart.data.datasets[1].data = hist.map(h => h.temperature);
        chart.update();
        renderHistoryList(id, hist);
    }
    async function deleteDevice(id) {
        if (!confirm(`Delete device "${id}"? This cannot be undone.`)) {
            return;
        }

        await fetch(`/api/device/${id}`, {
            method: "DELETE"
        });

        loadDevices(); // refresh the dashboard
    }
        const charts = {};

    function renderHistoryList(id, hist) {
        const container = document.getElementById(id + "-history");
        if (!container) return;
        if (!hist || hist.length === 0) {
            container.innerHTML = '<em>No history</em>';
            return;
        }

        // Show most recent first
        const rows = hist.slice().reverse().map(h => {
            const d = new Date(h.time);
            return `<div>${d.toLocaleString()} — Moisture: ${h.moisture}, Temp: ${h.temperature}</div>`;
        });

        container.innerHTML = rows.join('');
    }

    function createChart(id) {
        const ctx = document.getElementById(id + "-chart").getContext("2d");
        charts[id] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Moisture',
                        data: [],
                        borderColor: 'blue',
                        borderWidth: 2,
                        yAxisID: 'moistureAxis'
                    },
                    {
                        label: 'Temperature',
                        data: [],
                        borderColor: 'red',
                        borderWidth: 2,
                        yAxisID: 'tempAxis'
                    }
                ]
            },
            options: {
                scales: {
                    x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        tooltipFormat: 'HH:mm:ss',
                        displayFormats: {
                            minute: 'HH:mm'
                        }
                    }
                },
                    moistureAxis: { type: 'linear', position: 'left', min: 0, max: 100 },
                    tempAxis: { type: 'linear', position: 'right', min: 0, max: 40 }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            // Show formatted date/time as the tooltip title
                            title: function(context) {
                                if (!context || !context.length) return '';
                                const item = context[0];
                                let x = null;
                                if (item.parsed && item.parsed.x !== undefined) x = item.parsed.x;
                                else if (item.raw && item.raw.x !== undefined) x = item.raw.x;
                                else if (item.label !== undefined) x = item.label;

                                // Convert numeric strings to number
                                if (typeof x === 'string' && /^\d+$/.test(x)) x = Number(x);

                                const d = new Date(x);
                                if (isNaN(d.getTime())) return '';
                                return d.toLocaleString();
                            },
                            // Keep the default dataset label + value
                            label: function(context) {
                                const v = context.parsed && context.parsed.y !== undefined ? context.parsed.y : context.raw;
                                return context.dataset.label + ': ' + v;
                            }
                        }
                    }
                }
                
            }
            
        });

        // NEW: load history immediately
        loadInitialHistory(id);
    }

        async function update() {
            const devices = await fetch("/api/devices").then(r => r.json());

            for (const dev of devices) {
                const id = dev.id;
                const latest = await fetch(`/api/${id}/latest`).then(r => r.json());
                const hist = await fetch(`/api/${id}/history`).then(r => r.json());

                if (!latest) continue;

                const timeElem = document.getElementById(id + "-time");
                if (timeElem && latest.timestamp) {
                    timeElem.innerText = new Date(latest.timestamp * 1000).toLocaleString();
                }

                const moistElem = document.getElementById(id + "-moisture");
                const tempElem = document.getElementById(id + "-temp");
                const reservoirElem = document.getElementById(id + "-reservior"); // Grab the reservoir span

                if (moistElem) moistElem.innerText = latest.moisture;
                if (tempElem) tempElem.innerText = latest.temperature;

                // Check and update the reservoir status
                if (reservoirElem && latest.reservior !== null && latest.reservior !== undefined) {
                    if (latest.reservior) { 
                        reservoirElem.innerText = "Yes (Empty!)";
                        reservoirElem.style.color = "#c62828"; // Red warning text
                        reservoirElem.style.fontWeight = "bold";
                    } else {
                        reservoirElem.innerText = "No (Full)";
                        reservoirElem.style.color = "green"; // Green okay text
                        reservoirElem.style.fontWeight = "normal";
                    }
                }

                const chart = charts[id];
                if (chart && hist) {
                    chart.data.labels = hist.map(h => h.time);
                    chart.data.datasets[0].data = hist.map(h => h.moisture);
                    chart.data.datasets[1].data = hist.map(h => h.temperature);
                    chart.update();
                    renderHistoryList(id, hist);
                }
            }
        }
        async function renameDevice(id) {
        const newName = document.getElementById(id + "-newname").value;

        await fetch(`/api/${id}/name`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({name: newName})
        });

        loadDevices(); // refresh UI
    }

        loadDevices();
        setInterval(update, 6000);
    </script>
</body>
</html>
"""

@app.get("/")
def dashboard():
    return HTML #Loads the HTML

SETTINGS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Settings - Plant Dashboard</title>
    <style>
        body { font-family: Arial; margin: 40px; background: #DCEAF7; }
        .settings-container { max-width: 500px; }
        input { padding: 8px; margin: 8px 0; width: 100%; box-sizing: border-box; }
        button { padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #45a049; }
        .back-link { display: inline-block; margin-bottom: 20px; text-decoration: none; color: #0066cc; }
        .back-link:hover { text-decoration: underline; }
        .success { color: green; margin-top: 10px; display: none; }
        .error { color: red; margin-top: 10px; display: none; }
        label { display: block; margin-top: 15px; font-weight: bold; }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Back to Dashboard</a>
    <div class="settings-container">
        <h1>Settings</h1>
        <p>Configure your API keys for mobile notifications.</p>
        
        <label for="URL">ntfy topic:</label>
        <input id="URL" placeholder="Enter topic settings">        
        <button onclick="saveSettings()">Save Settings</button>
        
        <div class="success" id="success">✓ Settings saved successfully!</div>
        <div class="error" id="error"></div>
    </div>
    
    <script>
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const data = await response.json();
                
                if (data.URL) {
                    document.getElementById('URL').value = data.URL;
                }
            } catch (err) {
                console.error('Error loading settings:', err);
            }
        }
        
        async function saveSettings() {
            const URL = document.getElementById('URL').value;
            const successDiv = document.getElementById('success');
            const errorDiv = document.getElementById('error');
            
            if (!URL) {
                errorDiv.innerText = 'Please fill in all fields';
                errorDiv.style.display = 'block';
                successDiv.style.display = 'none';
                return;
            }
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        URL: URL,
                    })
                });
                
                if (response.ok) {
                    successDiv.style.display = 'block';
                    errorDiv.style.display = 'none';
                } else {
                    throw new Error('Failed to save settings');
                }
            } catch (err) {
                errorDiv.innerText = 'Error: ' + err.message;
                errorDiv.style.display = 'block';
                successDiv.style.display = 'none';
            }
        }
        
        loadSettings();
    </script>
</body>
</html>
"""

@app.get("/settings")
def settings():
    return SETTINGS_HTML

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
if __name__ == "__main__":
    t = threading.Thread(target=mqtt_thread, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5001)
