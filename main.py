from flask import Flask, render_template, request
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        vibe = request.form.get('vibe')
        # Here you would typically process the data or query a database
        print(f"Received search: Lat {latitude}, Long {longitude}, Vibe: {vibe}")
        return render_template('results.html', 
                             latitude=latitude, 
                             longitude=longitude, 
                             vibe=vibe)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)