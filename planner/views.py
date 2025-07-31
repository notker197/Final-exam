import requests
from django.shortcuts import render
from datetime import datetime
from pymongo import MongoClient
from django.http import HttpResponse

# --- Claves API ---
RAPIDAPI_KEY = "e06ab1173amsh8e8d0f49aaa4f75p1c97d5jsna1370a790887"
OPENWEATHER_KEY = "6514118c19bf337b8e111a3ce7f973ade"
ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImY0ZmU0NDI3MTEzOWQxMjkzODFmYzllMDVkZDAxZWIyMTk4NzMyNjY1YzNiNjZmNGI0MDVlZjc4IiwiaCI6Im11cm11cjY0In0="

# --- MongoDB Connection ---
MONGO_URL = "mongodb://3.81.171.79:27017"
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client.travel_db
history_collection = db.history
city_cache = db.city_coords

# --- Get Cities from GeoDB or fallback ---
def get_bc_cities():
    url = "https://wft-geo-db.p.rapidapi.com/v1/geo/countries/CA/regions/BC/cities?limit=20"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return get_fallback_cities()
        data = response.json().get("data", [])
        return [city["name"] for city in data] if data else get_fallback_cities()
    except:
        return get_fallback_cities()

def get_fallback_cities():
    return [
        "Vancouver", "Victoria", "Burnaby", "Richmond", "Surrey", 
        "Langley", "Abbotsford", "Coquitlam", "Kelowna", "Kamloops",
        "Prince George", "Nanaimo", "Chilliwack", "Vernon", "Penticton",
        "Mission", "North Vancouver", "New Westminster", "White Rock", "Delta"
    ]

# --- Index View ---
def index(request):
    cities = get_bc_cities()
    return render(request, "index.html", {"cities": cities})

# --- Get Coordinates with Cache ---
def get_coords(city):
    try:
        cached = city_cache.find_one({"city": city.lower()})
        if cached:
            return cached["lat"], cached["lon"]

        geo_url = f"https://wft-geo-db.p.rapidapi.com/v1/geo/countries/CA/regions/BC/cities?namePrefix={city}"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com"
        }
        geo = requests.get(geo_url, headers=headers)
        if geo.status_code != 200:
            raise Exception(f"Geo API error: {geo.status_code}")
        data = geo.json().get("data", [])
        if not data:
            raise Exception(f"No data for {city}")

        # Prefer exact match if possible
        for item in data:
            if item["name"].lower() == city.lower():
                lat, lon = item["latitude"], item["longitude"]
                break
        else:
            item = data[0]
            lat, lon = item["latitude"], item["longitude"]

        city_cache.insert_one({"city": city.lower(), "lat": lat, "lon": lon})
        return lat, lon

    except Exception as e:
        print(f"Error getting coordinates for {city}: {e}")
        fallback_coords = {
            "vancouver": (49.2827, -123.1207),
            "victoria": (48.4284, -123.3656),
            "burnaby": (49.2488, -122.9805),
            "richmond": (49.1666, -123.1336),
            "surrey": (49.1913, -122.8490),
            "langley": (49.1044, -122.6603),
            "abbotsford": (49.0504, -122.3045),
        }
        city_lower = city.lower()
        if city_lower in fallback_coords:
            return fallback_coords[city_lower]
        raise Exception(f"Coordinates unavailable for {city}")

# --- Get Weather ---
def get_weather(city):
    try:
        res = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city},CA&appid={OPENWEATHER_KEY}&units=metric")
        data = res.json()
        return f"{data['main']['temp']}°C, {data['weather'][0]['description']}"
    except Exception as e:
        return f"Weather not available ({e})"

# --- Results View ---
def results(request):
    start = request.GET.get("start_city")
    end = request.GET.get("end_city")

    if not start or not end:
        return HttpResponse("Error: Start and End cities required", status=400)

    try:
        start_coords = get_coords(start)
        end_coords = get_coords(end)
    except Exception as e:
        return HttpResponse(f"Error getting coordinates: {e}", status=400)

    weather_start = get_weather(start)
    weather_end = get_weather(end)

    try:
        headers = {'Authorization': ORS_KEY}
        body = {
            "coordinates": [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]]
        }
        route_response = requests.post("https://api.openrouteservice.org/v2/directions/driving-car", json=body, headers=headers)
        if route_response.status_code != 200:
            raise Exception(f"Route API error: {route_response.status_code}")
        route = route_response.json()
        summary = route["routes"][0]["summary"]
        steps = route["routes"][0]["segments"][0]["steps"]
    except Exception as e:
        return HttpResponse(f"Error getting route: {e}", status=400)

    hour = datetime.now().hour
    advice = "Good time to travel!" if "rain" not in weather_start.lower() and 6 <= hour <= 20 else "Consider delaying due to weather."

    try:
        history_collection.insert_one({
            "start": start,
            "end": end,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "distance": summary["distance"],
            "duration": summary["duration"],
            "advice": advice
        })
    except Exception as e:
        print(f"Mongo history save error: {e}")

    return render(request, "results.html", {
        "start": start,
        "end": end,
        "weather_start": weather_start,
        "weather_end": weather_end,
        "distance": round(summary["distance"] / 1000, 1),
        "duration": round(summary["duration"] / 60, 1),
        "steps": steps,
        "advice": advice
    })

# --- History View ---
def history(request):
    try:
        queries = list(history_collection.find().sort("timestamp", -1))
        return render(request, "history.html", {"queries": queries})
    except Exception as e:
        return HttpResponse(f"Error loading history: {e}", status=500)
