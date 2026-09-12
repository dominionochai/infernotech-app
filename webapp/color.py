def pink(feature):
    return {"fillColor": "#ff6fae", "color": "#ff2f8f", "weight": 1, "fillOpacity": 0.4}

def green(feature):
    return {"fillColor": "#6fff9e", "color": "#1fbf55", "weight": 1, "fillOpacity": 0.4}

def purple(feature):
    return {"fillColor": "#b98cff", "color": "#7d3fd6", "weight": 1, "fillOpacity": 0.4}

def red(feature):
    return {"fillColor": "#ff6f6f", "color": "#d62f2f", "weight": 1, "fillOpacity": 0.5}

def yellow(feature):
    return {"fillColor": "#fff06f", "color": "#d6c02f", "weight": 1, "fillOpacity": 0.4}

CAT_COLORS = {
    "3-Forests and Semi-natural Areas": "#3f9142",
    "2-Agricultural Areas": "#c9a227",
    "998-Others": "#8a8f98",
}

def cat(feature):
    obj_type = feature.get("properties", {}).get("obj_type", "")
    color = CAT_COLORS.get(obj_type, "#8a8f98")
    return {"fillColor": color, "color": color, "weight": 1, "fillOpacity": 0.35}
