import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def poly(coords, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [coords]}}

def fc(features):
    return {"type": "FeatureCollection", "features": features}

copernicus_burnt = fc([
    poly([[23.90,37.79],[23.98,37.80],[23.99,37.75],[23.92,37.74],[23.90,37.79]], source="Copernicus EMSR", label="Observed burnt event area")
])
buildings = fc([
    poly([[23.93,37.78],[23.945,37.782],[23.944,37.775],[23.928,37.774],[23.93,37.78]], obj_type="998-Others", label="Built-up area near burn perimeter"),
    poly([[23.965,37.79],[23.978,37.792],[23.977,37.786],[23.963,37.784],[23.965,37.79]], obj_type="998-Others", label="Village settlement"),
])
natural_landcover = fc([
    poly([[23.90,37.76],[23.94,37.77],[23.93,37.745],[23.89,37.74],[23.90,37.76]], obj_type="3-Forests and Semi-natural Areas", label="Forest / semi-natural land"),
    poly([[23.95,37.78],[23.985,37.795],[23.99,37.77],[23.955,37.76],[23.95,37.78]], obj_type="2-Agricultural Areas", label="Cropland"),
])
fireclr_mask = fc([
    poly([[23.905,37.785],[23.97,37.795],[23.975,37.755],[23.915,37.745],[23.905,37.785]], model="FireCLR", label="FireCLR predicted burn mask")
])
sam_mask = fc([
    poly([[23.90,37.788],[23.975,37.80],[23.985,37.752],[23.912,37.742],[23.90,37.788]], model="SAMGeo", label="SAMGeo predicted burn mask")
])
diff_clr = fc([
    poly([[23.975,37.755],[23.99,37.75],[23.985,37.74],[23.97,37.745],[23.975,37.755]], label="Copernicus vs FireCLR difference")
])
diff_sam = fc([
    poly([[23.985,37.752],[23.99,37.75],[23.987,37.744],[23.98,37.746],[23.985,37.752]], label="Copernicus vs SAMGeo difference")
])

layers = {
    "copernicus_burnt.geojson": copernicus_burnt,
    "buildings.geojson": buildings,
    "natural_landcover.geojson": natural_landcover,
    "fireclr_mask.geojson": fireclr_mask,
    "sam_mask.geojson": sam_mask,
    "diff_clr.geojson": diff_clr,
    "diff_sam.geojson": diff_sam,
}
for name, data in layers.items():
    with open(os.path.join(DATA_DIR, name), "w") as f:
        json.dump(data, f)
print(f"Wrote {len(layers)} sample GeoJSON layers to {DATA_DIR}")
