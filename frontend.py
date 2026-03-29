import os
from flask import Flask, send_file, render_template_string
import folium
import json
from threading import Lock

app = Flask(__name__)

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
RECOMMENDATION_QUEUE_NAME = 'schedule_recommendation'

ROUTE_COLORS = ["blue", "green", "orange", "red", "black"]
ROUTES = [39, 36, 29, 110, 97]
MAP_FILE = "static/toronto_map.html"

shared_data = {"latest": None}
data_lock = Lock()


def get_color(v):
    status = v.get("status")
    if status == "kept":
        try:
            idx = ROUTES.index(int(v["route"]))
            return ROUTE_COLORS[idx]
        except:
            return "blue"
    elif status == "added":
        return "gray"
    elif status == "removed":
        return "red"
    return "purple"


def plot_vehicles_on_map(vehicles):
    m = folium.Map(location=[43.75, -79.35], zoom_start=11.3)
    for v in vehicles:
        try:
            lat = float(v["lat"])
            lon = float(v["lon"])
            color = get_color(v)
            folium.Marker(
                location=[lat, lon],
                popup=f"Vehicle: {v.get('vehicle_id','N/A')}<br>"
                      f"Route: {v.get('route','N/A')}<br>"
                      f"Status: {v.get('status','unknown')}<br>"
                      f"Occupancy: {v.get('occupancy_status','N/A')}",
                icon=folium.Icon(color=color, icon="bus", prefix="fa")
            ).add_to(m)
        except:
            continue
    m.save(MAP_FILE)


@app.route('/')
def dashboard():
    with data_lock:
        data = shared_data["latest"]

    if not data:
        return """
        <h2 style="text-align:center; margin-top:100px; color:#555;">
            Waiting for first recommendation from worker...<br>
            <small>Make sure producer.py and worker.py are running (locally or as Background Workers)</small>
        </h2>
        """

    kept = len(data.get("kept", []))
    removed = len(data.get("removed", []))
    added = len(data.get("xtra", []))
    total = kept + removed + added + len(data.get("OG", []))

    return render_template_string('''
    <h1 style="text-align:center; color:#2c3e50;">TTC Bus Schedule Optimizer</h1>
    
    <div style="display:flex; justify-content:center; gap:30px; margin:30px 0; flex-wrap:wrap;">
        <div style="background:white; padding:20px 40px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1); text-align:center;">
            <h3>Kept</h3><h2 style="color:blue;">{{kept}}</h2>
        </div>
        <div style="background:white; padding:20px 40px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1); text-align:center;">
            <h3>Removed</h3><h2 style="color:red;">{{removed}}</h2>
        </div>
        <div style="background:white; padding:20px 40px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1); text-align:center;">
            <h3>Added</h3><h2 style="color:gray;">{{added}}</h2>
        </div>
        <div style="background:white; padding:20px 40px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1); text-align:center;">
            <h3>Total Vehicles</h3><h2>{{total}}</h2>
        </div>
    </div>

    <iframe id="mapframe" src="/map" style="width:100%; height:780px; border:3px solid #3498db; border-radius:12px;"></iframe>

    <script>
        setInterval(() => {
            document.getElementById("mapframe").src = "/map?ts=" + Date.now();
        }, 8000);
    </script>
    <p style="text-align:center; color:#666; margin-top:10px;">Auto-refreshes every 8 seconds</p>
    ''', kept=kept, removed=removed, added=added, total=total)


@app.route('/map')
def serve_map():
    if os.path.exists(MAP_FILE):
        return send_file(MAP_FILE)
    m = folium.Map(location=[43.75, -79.35], zoom_start=11)
    m.save(MAP_FILE)
    return send_file(MAP_FILE)


if __name__ == '__main__':
    os.makedirs("static", exist_ok=True)
    print("Dashboard running on http://localhost:5000")
    app.run(debug=False, port=5000)
