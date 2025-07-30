import requests
from django.shortcuts import render
from datetime import datetime
from pymongo import MongoClient
from django.http import HttpResponse

RAPIDAPI_KEY = "e06ab1173amsh8e8d0f49aaa4f75p1c97d5jsna1370a790887"
OPENWEATHER_KEY = "6514118c19bf337b8e111a3ce7f973ade"
ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImI2ZGViN2Y3NzY0NmI2YWYzNmJmYzk2NmFjOTg5NmYxODIyMTMzYTM3ZmJiM2Y1NGQ2NmU0YjdiIiwiaCI6Im11cm11cjY0In0="

MONGO_URL = "mongodb://13.223.179.86:27017"
client = MongoClient(MONGO_URL)
db = client.travel_db
history_collection = db.history

def get_bc_cities():
    url = "https://wft-geo-db.p.rapidapi.com/v1/geo/countries/CA/regions/BC/cities?limit=20"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com"
    }
    try:
        print("Haciendo llamada a la API de ciudades...")
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error en API: {response.status_code}")
            print(f"Respuesta: {response.text}")
            # Fallback con ciudades hardcodeadas
            return get_fallback_cities()
        
        data = response.json()
        print(f"Respuesta completa: {data}")
        
        cities_data = data.get("data", [])
        print(f"Ciudades encontradas: {len(cities_data)}")
        
        if not cities_data:
            print("No se encontraron ciudades, usando fallback")
            return get_fallback_cities()
        
        cities = [city["name"] for city in cities_data]
        print(f"Lista de ciudades: {cities}")
        return cities
        
    except Exception as e:
        print(f"Error obteniendo ciudades: {e}")
        return get_fallback_cities()

def get_fallback_cities():
    """Ciudades de BC hardcodeadas como fallback"""
    fallback_cities = [
        "Vancouver", "Victoria", "Burnaby", "Richmond", "Surrey", 
        "Langley", "Abbotsford", "Coquitlam", "Kelowna", "Kamloops",
        "Prince George", "Nanaimo", "Chilliwack", "Vernon", "Penticton",
        "Mission", "North Vancouver", "New Westminster", "White Rock", "Delta"
    ]
    print(f"Usando ciudades fallback: {fallback_cities}")
    return fallback_cities

def index(request):
    print("Vista index llamada")
    cities = get_bc_cities()
    print(f"Ciudades enviadas al template: {cities}")
    
    context = {"cities": cities}
    print(f"Context completo: {context}")
    
    return render(request, "index.html", context)

def results(request):
    start = request.GET.get("start_city")
    end = request.GET.get("end_city")
    
    print(f"Ciudad inicio: {start}")
    print(f"Ciudad destino: {end}")
    
    if not start or not end:
        return HttpResponse("Error: Debe proporcionar ciudad de inicio y destino", status=400)

    def get_weather(city):
        try:
            res = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city},CA&appid={OPENWEATHER_KEY}&units=metric")
            data = res.json()
            return f"{data['main']['temp']}°C, {data['weather'][0]['description']}"
        except Exception as e:
            return f"Weather info not available ({e})"

    weather_start = get_weather(start)
    weather_end = get_weather(end)

    def get_coords(city):
        try:
            geo_url = f"https://wft-geo-db.p.rapidapi.com/v1/geo/countries/CA/regions/BC/cities?namePrefix={city}"
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com"
            }
            geo = requests.get(geo_url, headers=headers)
            
            # Verificar si la respuesta es exitosa
            if geo.status_code != 200:
                raise Exception(f"Error en API: {geo.status_code}")
            
            json_data = geo.json()
            data_list = json_data.get("data", [])
            
            # Verificar si hay resultados
            if not data_list:
                raise Exception(f"No se encontraron coordenadas para la ciudad: {city}")
            
            # Buscar una coincidencia exacta o la más cercana
            city_data = None
            for item in data_list:
                if item["name"].lower() == city.lower():
                    city_data = item
                    break
            
            if not city_data:
                city_data = data_list[0]
            
            return city_data["latitude"], city_data["longitude"]
            
        except Exception as e:
            print(f"Error obteniendo coordenadas para {city}: {e}")
            # Coordenadas por defecto para ciudades principales como fallback
            fallback_coords = {
                "vancouver": (49.2827, -123.1207),
                "victoria": (48.4284, -123.3656),
                "burnaby": (49.2488, -122.9805),
                "richmond": (49.1666, -123.1336),
                "surrey": (49.1913, -122.8490),
                "kelowna": (49.8880, -119.4960),
                "kamloops": (50.6745, -120.3273)
            }
            
            city_lower = city.lower()
            if city_lower in fallback_coords:
                print(f"Usando coordenadas fallback para {city}")
                return fallback_coords[city_lower]
            
            raise Exception(f"No se pudieron obtener las coordenadas para {city}: {e}")

    try:
        start_coords = get_coords(start)
        end_coords = get_coords(end)
    except Exception as e:
        return HttpResponse(f"Error obteniendo coordenadas: {e}", status=400)

    try:
        headers = {'Authorization': ORS_KEY}
        body = {
            "coordinates": [[start_coords[1], start_coords[0]], [end_coords[1], end_coords[0]]]
        }
        route_response = requests.post("https://api.openrouteservice.org/v2/directions/driving-car", json=body, headers=headers)
        
        if route_response.status_code != 200:
            raise Exception(f"Error en API de rutas: {route_response.status_code}")
            
        route = route_response.json()
        
        if "features" not in route or not route["features"]:
            raise Exception("Respuesta de ruta inválida")
            
        summary = route["features"][0]["properties"]["summary"]
        steps = route["features"][0]["properties"]["segments"][0]["steps"]
        
    except Exception as e:
        return HttpResponse(f"Error obteniendo ruta: {e}", status=400)

    hour = datetime.now().hour
    advice = "Good time to start your trip!" if "rain" not in weather_start.lower() and 6 <= hour <= 20 else "Consider delaying your trip due to bad weather."

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
        print(f"Error guardando en historial: {e}")

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

def history(request):
    try:
        consultas = list(history_collection.find().sort("timestamp", -1))
        return render(request, "history.html", {"queries": consultas})
    except Exception as e:
        return HttpResponse(f"Error accediendo al historial: {e}", status=500)