import pika
import time
import json
import requests
import os
from google.transit import gtfs_realtime_pb2

OCCUPANCY_MAP = {
    0: "EMPTY", 1: "MANY_SEATS_AVAILABLE", 2: "FEW_SEATS_AVAILABLE",
    3: "STANDING_ROOM_ONLY", 4: "CRUSHED_STANDING_ROOM_ONLY",
    5: "FULL", 6: "NOT_ACCEPTING_PASSENGERS"
}

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
BUS_UPDATE_QUEUE_NAME = 'bus_update'
URL = "https://bustime.ttc.ca/gtfsrt/vehicles"
ROUTES = [39, 36, 29, 110, 97]

def fetch_ttc_vehicles(route_id):
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    vehicles = []
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            v = entity.vehicle
            if v.trip.route_id == str(route_id):
                vehicles.append({
                    "vehicle_id": v.vehicle.id,
                    "route": v.trip.route_id,
                    "lat": v.position.latitude,
                    "lon": v.position.longitude,
                    "bearing": v.position.bearing,
                    "occupancy_status": OCCUPANCY_MAP.get(v.occupancy_status, "UNKNOWN")
                })
    return vehicles

if __name__ == '__main__':
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=BUS_UPDATE_QUEUE_NAME)

    print("Producer running...")
    while True:
        try:
            route_vehicles = {}
            for route_id in ROUTES:
                vehicles = fetch_ttc_vehicles(route_id)
                route_vehicles[str(route_id)] = vehicles

            data = {"route_vehicles": route_vehicles}
            channel.basic_publish(
                exchange="",
                routing_key=BUS_UPDATE_QUEUE_NAME,
                body=json.dumps(data)
            )
            print("Sent bus update")
        except Exception as e:
            print(f"Producer error: {e}")
        time.sleep(10)
