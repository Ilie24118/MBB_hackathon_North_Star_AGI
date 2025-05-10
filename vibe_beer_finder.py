from flask import Flask, render_template, request, jsonify
import folium
from folium.plugins import MarkerCluster
import json
from datasets import load_dataset
import pandas as pd
from math import radians, cos, sin, asin, sqrt
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Google AI API
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Warning: GOOGLE_API_KEY environment variable not set. Vibe matching will not work.")
else:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

app = Flask(__name__)

def find_pubs(dataset_name="ns2agi/antwerp-osm-navigator"):
    """Load and filter pub data from the dataset"""
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

def generate_vibe_match(vibe, pub_list):
    """
    Use Google's Gemini model to find the pub that best matches the desired vibe
    
    Args:
        vibe (str): The vibe the user is looking for
        pub_list (list): List of pub dictionaries
        
    Returns:
        dict: The pub that best matches the vibe, with an added explanation
    """
    if not api_key:
        # If no API key, just return the first pub with a placeholder message
        pub_list[0]["explanation"] = "API key not set. Unable to match vibe."
        return pub_list[0]
    
    pub_names = [pub["name"] for pub in pub_list[:5]]
    
    prompt = f"""Given the vibe: '{vibe}'. With these 5 pubs located in Antwerp: {pub_names} that are closest to me.
    
    1. Which ONE pub best matches the '{vibe}' vibe? Just give me the name.
    2. Also provide a brief explanation for why this pub matches the vibe.
    
    Format your response as:
    PUB NAME: [name of the selected pub]
    EXPLANATION: [your explanation]
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Parse the response to extract the pub name and explanation
        lines = response_text.strip().split("\n")
        selected_pub_name = None
        explanation = ""
        
        for line in lines:
            if line.startswith("PUB NAME:"):
                selected_pub_name = line.replace("PUB NAME:", "").strip()
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()
            # Collect additional explanation lines
            elif selected_pub_name and not line.startswith("PUB NAME:"):
                explanation += " " + line.strip()
                
        # Find the matching pub from our list
        for pub in pub_list:
            if selected_pub_name and selected_pub_name in pub["name"]:
                pub["explanation"] = explanation
                return pub
        
        # If we couldn't find a match, return the first pub with the explanation
        pub_list[0]["explanation"] = explanation if explanation else "No explanation provided by AI"
        pub_list[0]["note"] = f"AI suggested '{selected_pub_name}' but it couldn't be matched to our data"
        return pub_list[0]
        
    except Exception as e:
        # In case of any error, return the first pub with error info
        pub_list[0]["explanation"] = f"Error matching vibe: {str(e)}"
        return pub_list[0]

def create_pub_map(pub_list, user_location, selected_pub=None):
    """
    Create an interactive map with pubs and highlight the selected one
    
    Args:
        pub_list (list): List of pub dictionaries
        user_location (list): [latitude, longitude] of the user
        selected_pub (dict, optional): The pub selected for the user's vibe
        
    Returns:
        str: Filename of saved HTML map
    """
    # Create map centered on user location
    m = folium.Map(location=user_location, zoom_start=15)
    
    # Add user location marker
    folium.Marker(
        location=user_location,
        popup="Your Location",
        icon=folium.Icon(color="red", icon="user", prefix="fa")
    ).add_to(m)
    
    # Create marker cluster for better performance with many markers
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add each pub to the map
    for pub in pub_list:
        # Extract coordinates
        lat, lon = pub["coordinates"]
        
        # Determine if this is the selected pub
        is_selected = selected_pub and pub["id"] == selected_pub["id"]
        
        # Create popup with pub info
        popup_text = f"<b>Name:</b> {pub['name']}<br>"
        popup_text += f"<b>Distance:</b> {pub['distance']}<br>"
        
        # Add explanation if this is the selected pub
        if is_selected and "explanation" in pub:
            popup_text += f"<b>Matches Your Vibe:</b> {pub['explanation']}<br>"
        
        # Add other available info
        for k, v in pub.items():
            if k not in ["name", "distance", "distance_value", "coordinates", "id", "explanation", "note"]:
                popup_text += f"<b>{k}:</b> {v}<br>"
        
        # Use different icon for selected pub
        icon_color = "blue" if is_selected else "green"
        
        folium.Marker(
            location=[lat, lon],
            popup=popup_text,
            icon=folium.Icon(color=icon_color, icon="beer", prefix="fa")
        ).add_to(marker_cluster)
    
    # Save map to static folder
    map_file = "static/pub_map.html"
    os.makedirs(os.path.dirname(map_file), exist_ok=True)
    m.save(map_file)
    
    return "pub_map.html"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Get form data
            latitude = float(request.form.get('latitude'))
            longitude = float(request.form.get('longitude'))
            vibe = request.form.get('vibe')
            
            # Get nearby pubs
            location = [latitude, longitude]
            pub_list = get_top_pubs(location)
            
            if not pub_list:
                return render_template('error.html', 
                                    message="No pubs found in this area.")
            
            # Find the pub that matches the vibe
            vibe_match = generate_vibe_match(vibe, pub_list)
            
            # Create the map
            map_file = create_pub_map(pub_list, location, vibe_match)
            
            return render_template('results.html', 
                                latitude=latitude, 
                                longitude=longitude, 
                                vibe=vibe,
                                pub_list=pub_list,
                                vibe_match=vibe_match,
                                map_file=map_file)
        except Exception as e:
            return render_template('error.html', message=f"Error: {str(e)}")
            
    return render_template('index.html')

# Add a route to handle the case when the user wants to use their current location
@app.route('/api/pubs', methods=['POST'])
def get_pubs_api():
    try:
        data = request.json
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        vibe = data.get('vibe')
        
        location = [latitude, longitude]
        pub_list = get_top_pubs(location)
        
        if not pub_list:
            return jsonify({"error": "No pubs found in this area."})
        
        vibe_match = generate_vibe_match(vibe, pub_list)
        
        return jsonify({
            "pubs": pub_list,
            "vibe_match": vibe_match
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/table')
def hello_world():
    return render_template('table.html')

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True)