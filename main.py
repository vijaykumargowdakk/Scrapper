from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re

app = FastAPI()

# --- THE FIX: ADD CORS MIDDLEWARE ---
# This tells the browser that your React frontend is allowed to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin (localhost, vercel, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, OPTIONS, etc.
    allow_headers=["*"],
)

# Define the expected JSON payload
class VehicleRequest(BaseModel):
    url: str

@app.post("/scrape-images")
def scrape_iaai_images(req: VehicleRequest):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.iaai.com/",
    }
    
    try:
        response = session.get(req.url, impersonate="chrome120", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to bypass firewall")

        soup = BeautifulSoup(response.text, 'html.parser')
        image_keys = []

        # Strategy 1: DeepZoom Div
        deep_zoom = soup.find("div", id="deepzoom")
        if deep_zoom and deep_zoom.get("dimensionsallimagekeys"):
            image_keys = json.loads(deep_zoom["dimensionsallimagekeys"])
        
        # Strategy 2: Regex Fallback
        if not image_keys:
            matches = re.findall(r'\[\{"k":.*?"w":\d+,"h":\d+.*?\}\]', response.text)
            for m in matches:
                try:
                    data = json.loads(m)
                    if data and 'k' in data[0]:
                        image_keys = data
                        break
                except: continue

        if not image_keys:
            raise HTTPException(status_code=404, detail="No image keys found on page")

        # Generate and Verify Links
        valid_links = []
        for img in image_keys:
            key = img.get('k')
            if not key: continue

            primary_link = f"https://vis.iaai.com/resizer?imageKeys={key}&width=1024&height=768"
            check = session.head(primary_link, impersonate="chrome120", headers=headers)
            
            if check.status_code == 200:
                valid_links.append(primary_link)
            else:
                fallback_link = f"https://vis.iaai.com/resizer?imageKeys={key}&width=845&height=633"
                valid_links.append(fallback_link)

        return {"images": valid_links}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
