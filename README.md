# Land Constraint Checker

A Streamlit web application for visualizing land constraints and special category land designations in the UK.

## Features
- 🗺️ Interactive map with multiple constraint layers
- 📤 Upload and overlay custom shapefiles or GeoPackages
- 🔍 Zoom to layer functionality
- 🎨 Light, clean CartoDB basemap
- 📊 View multiple environmental and planning designations

## Data Layers

### Sensitive Parties
- Canals on the Trust Network
- Dry Docks
- Network Rail Centre Lines
- Network Rail ELRS

### Environmental Designations
- Areas of Outstanding Natural Beauty (AONB)
- Country Parks
- Local Nature Reserves
- National Nature Reserves
- National Parks
- Ramsar Sites
- Special Areas of Conservation (SAC)
- Special Protection Areas (SPA)
- Sites of Special Scientific Interest (SSSI)

### Special Category Land
- Conservation Areas
- CROW Act 2000 Land
- National Trust Land (Always Open)
- National Trust Land (Limited Access)
- Open Greenspace

## Usage

1. **Select base layers** from the sidebar to view different constraints
2. **Upload your own data:**
   - Zip your shapefile components (.shp, .shx, .dbf, .prj) together
   - Or upload a GeoPackage (.gpkg)
3. **Navigate the map:**
   - Click 🔍 next to any layer to zoom to it
   - Use "Zoom to All Visible Layers" to see everything
   - Drag to pan, scroll to zoom
4. **View details:** Hover over features to see attribute information

## Installation (Local)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/land-constraint-checker.git
cd land-constraint-checker

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run land_constraint_checker.py
```

## Tech Stack
- **Streamlit** - Web framework
- **GeoPandas** - Geospatial data handling
- **PyDeck** - Map visualization
- **Fiona** - File I/O

## License
This project is for educational and planning purposes.

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.
