def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def compute_risk_score(weather, nearby_fire_count):
    temp = weather.get("temperature_c")
    humidity = weather.get("humidity_pct")
    wind = weather.get("wind_speed_kmh")

    temp_score = clamp(((temp if temp is not None else 20) - 15) / 25)
    humidity_score = clamp((60 - (humidity if humidity is not None else 50)) / 60)
    wind_score = clamp((wind if wind is not None else 0) / 60)

    if nearby_fire_count is None:
        proximity_score = 0.0
        proximity_note = "Satellite fire-detection check unavailable for this address (no FIRMS_MAP_KEY set)."
    elif nearby_fire_count > 0:
        proximity_score = 1.0
        proximity_note = f"{nearby_fire_count} active satellite fire detection(s) within ~30km right now."
    else:
        proximity_score = 0.0
        proximity_note = "No active satellite fire detections within ~30km right now."

    raw = 100 * (0.3 * temp_score + 0.3 * humidity_score + 0.2 * wind_score + 0.2 * proximity_score)
    score = int(round(clamp(raw, 0, 100)))

    if score >= 75: label = "Extreme"
    elif score >= 50: label = "High"
    elif score >= 25: label = "Moderate"
    else: label = "Low"

    reasons = [
        f"Temperature: {temp}°C" if temp is not None else "Temperature: unavailable",
        f"Relative humidity: {humidity}%" if humidity is not None else "Humidity: unavailable",
        f"Wind speed: {wind} km/h" if wind is not None else "Wind: unavailable",
        proximity_note,
    ]
    return score, label, reasons
