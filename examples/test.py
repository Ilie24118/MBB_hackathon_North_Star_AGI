import folium
from folium.plugins import MarkerCluster
import json
from datasets import load_dataset
import pandas as pd

def find_benches(dataset_name="ns2agi/antwerp-osm-navigator"):
    # Load the dataset
    dataset = load_dataset(dataset_name)["train"]
    
    # Function to parse tags and check for benches
    def is_bench(example):
        try:
            tags = json.loads(example["tags"]) if example["tags"] != '{}' else {}
            return tags.get("amenity") == "waste_basket"
        except:
            return False
    
    # Filter for benches
    bench_data = dataset.filter(is_bench)
    print(f"Found {len(bench_data)} waste_baskets in Antwerp")
    
    # Convert to pandas DataFrame
    bench_df = bench_data.to_pandas()
    
    # Parse tags properly
    bench_df["tags"] = bench_df["tags"].apply(lambda x: json.loads(x) if x != '{}' else {})
    
    return bench_df

# Get all benches
bench_df = find_benches()

def visualize_benches(bench_df):
    # Create map centered on Antwerp
    antwerp_center = [51.2211, 4.3997]
    m = folium.Map(location=antwerp_center, zoom_start=13)
    
    # Create marker cluster for better performance with many markers
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add each bench to the map
    for idx, bench in bench_df.iterrows():
        if pd.notnull(bench["lat"]) and pd.notnull(bench["lon"]):
            # Create popup with bench info
            popup_text = f"<b>waste_basket ID:</b> {bench['id']}<br>"
            if bench["tags"]:
                for k, v in bench["tags"].items():
                    popup_text += f"<b>{k}:</b> {v}<br>"
            
            folium.Marker(
                location=[bench["lat"], bench["lon"]],
                popup=popup_text,
                icon=folium.Icon(color="green", icon="tree-deciduous", prefix="fa")
            ).add_to(marker_cluster)
    
    # Save and display
    m.save("antwerp_waste_basket.html")
    return m

# Visualize the benches
bench_map = visualize_benches(bench_df)
bench_map