import folium
from folium.plugins import MarkerCluster
import json
from datasets import load_dataset
import pandas as pd
from math import radians, cos, sin, asin, sqrt

import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    exit()

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.0-flash")

def find_pubs(dataset_name="ns2agi/antwerp-osm-navigator"):
    # Load the dataset
    dataset = load_dataset(dataset_name)["train"]
    
    # Function to parse tags and check for pubs
    def is_pub(example):
        try:
            tags = json.loads(example["tags"]) if example["tags"] != '{}' else {}
            return tags.get("amenity") == "pub"
        except:
            return False
    
    # Filter for pubs
    pub_data = dataset.filter(is_pub)
    print(f"Found {len(pub_data)} pubs in Antwerp")
    
    # Convert to pandas DataFrame
    pub_df = pub_data.to_pandas()
    
    # Parse tags properly
    pub_df["tags"] = pub_df["tags"].apply(lambda x: json.loads(x) if x != '{}' else {})
    
    return pub_df

def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of earth in kilometers
    return c * r

def find_nearest_pubs(location, n=5):
    """
    Find the n nearest pubs to the given location
    
    Args:
        location (list): [latitude, longitude]
        n (int): Number of pubs to return
        
    Returns:
        DataFrame: Top n nearest pubs
    """
    # Get all pubs
    pub_df = find_pubs()
    
    # Calculate distance for each pub
    user_lat, user_lon = location
    pub_df['distance'] = pub_df.apply(
        lambda row: haversine(user_lon, user_lat, row['lon'], row['lat']) 
        if pd.notnull(row['lat']) and pd.notnull(row['lon']) else float('inf'), 
        axis=1
    )
    
    # Sort by distance and get top n
    nearest_pubs = pub_df.sort_values('distance').head(n)
    
    return nearest_pubs

def visualize_pubs(nearest_pubs, user_location):
    """
    Visualize the nearest pubs on a map
    
    Args:
        nearest_pubs (DataFrame): DataFrame containing the nearest pubs
        user_location (list): [latitude, longitude] of the user
    """
    # Create map centered on user location
    m = folium.Map(location=user_location, zoom_start=15)
    
    # Create marker cluster for better performance with many markers
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add user location marker
    folium.Marker(
        location=user_location,
        popup="Your Location",
        icon=folium.Icon(color="red", icon="user", prefix="fa")
    ).add_to(m)
    
    # Add each pub to the map
    for idx, pub in nearest_pubs.iterrows():
        if pd.notnull(pub["lat"]) and pd.notnull(pub["lon"]):
            # Get the pub name if available, otherwise use the ID
            pub_name = pub["tags"].get("name", f"Unnamed Pub (ID: {pub['id']})")
            
            # Create popup with pub info
            popup_text = f"<b>Name:</b> {pub_name}<br>"
            popup_text += f"<b>Distance:</b> {pub['distance']:.2f} km<br>"
            
            # Add other available info
            if pub["tags"]:
                for k, v in pub["tags"].items():
                    if k != "name":  # Skip name as we already displayed it
                        popup_text += f"<b>{k}:</b> {v}<br>"
            
            folium.Marker(
                location=[pub["lat"], pub["lon"]],
                popup=popup_text,
                icon=folium.Icon(color="green", icon="beer", prefix="fa")
            ).add_to(marker_cluster)
    
    # Save and display
    m.save("nearest_pubs.html")
    return m

def get_top_pubs(location, n=5):
    """
    Returns the top n nearest pubs to the given location as a list of dictionaries
    
    Args:
        location (list): [latitude, longitude]
        n (int): Number of pubs to return
        
    Returns:
        list: List of dictionaries, each containing pub details (including name and distance)
    """
    nearest_pubs = find_nearest_pubs(location, n)
    
    # Create a list of pub information
    pub_list = []
    for idx, pub in nearest_pubs.iterrows():
        # Get the pub name if available, otherwise use the ID
        pub_name = pub["tags"].get("name", f"Unnamed Pub (ID: {pub['id']})")
        
        # Create dictionary with pub details
        pub_details = {
            "name": pub_name,
            "distance": f"{pub['distance']:.2f} km",
            "distance_value": pub['distance'],
            "coordinates": [pub['lat'], pub['lon']],
            "id": pub['id']
        }
        
        # Add additional info from tags if available
        if pub["tags"]:
            for k, v in pub["tags"].items():
                if k != "name":  # Skip name as we already included it above
                    pub_details[k] = v
        
        pub_list.append(pub_details)
    
    return pub_list


def genrate_vibe(vibe, pubs):

    pub_list_2 = []

    for x in range(5):
        pub_list_2.append(pubs[x]["name"])
        print(pubs[x]["name"])

    print("\nPub list")
    print(f"\n {pub_list_2} \n")

    prompt = f"Given the vibe: {vibe}. With these 5 pubs located in Antwerp: {pub_list_2} that are closeset to me. Give me the one that matches the vibe."

    response = model.generate_content(prompt)


    return response.text

# Example usage:
# To find the 5 nearest pubs to Antwerp's central station:
# 51.22717624808818, 4.413259042361474
location = [51.2271, 4.4132]  
pub_list = get_top_pubs(location)

print(type(pub_list))
print(type(pub_list[1]))

for x in range(5):
    print(pub_list[x]["name"])

print("Top 5 nearest pubs:")
for i, pub in enumerate(pub_list, 1):
    print(f"{i}. {pub}")

print("Promt: \n")
print(genrate_vibe("Cozy", pub_list))

# To visualize on a map:
nearest_pubs = find_nearest_pubs(location)
pub_map = visualize_pubs(nearest_pubs, location)