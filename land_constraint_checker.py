import streamlit as st
import geopandas as gpd
import pydeck as pdk
import tempfile
from pathlib import Path
import fiona
import zipfile
import shutil
import pandas as pd

# ---- PAGE SETUP ----
st.set_page_config(page_title="Land Constraint Checker", layout="wide")
st.title("Land Constraint Checker")

# ---- CONFIG ----
BASE_GEOPACKAGES = [
    {
        'path': 'custom_repository/data/Sensitive_Parties.gpkg',
        'layers': ['canals_on_the_trust_network', 'dry_docks', 'network_rail_centre_lines', 'nwr_elrs'],
        'colors': ['pink', 'lightblue', 'lightgreen', 'beige']
    },
    {
        'path': 'custom_repository/data/Environmental_Designations.gpkg',
        'layers': ['aonb', 'country_parks', 'local_nature_reserves', 'national_nature_reserves',
                   'national_parks', 'ramsar', 'sac', 'spa', 'sssi'],
        'colors': ['blue', 'red', 'green', 'purple', 'orange', 'darkblue', 'darkred', 'darkgreen', 'cadetblue']
    },
    {
        'path': 'custom_repository/data/Special_Category_Land.gpkg',
        'layers': ['conservation_areas', 'crow_act_2000', 'national_trust_land_always_open',
                   'national_trust_limited_access', 'open_greenspace'],
        'colors': ['gray', 'black', 'brown', 'cyan', 'magenta']
    }
]

COLOR_MAP = {
    'blue':[0,0,255,140], 'red':[255,0,0,140], 'green':[0,255,0,140], 'purple':[128,0,128,140],
    'orange':[255,165,0,140], 'darkblue':[0,0,139,140], 'darkred':[139,0,0,140], 'darkgreen':[0,100,0,140],
    'cadetblue':[95,158,160,140], 'pink':[255,192,203,140], 'lightblue':[173,216,230,140],
    'lightgreen':[144,238,144,140], 'beige':[245,245,220,140], 'gray':[128,128,128,140],
    'black':[0,0,0,140], 'brown':[165,42,42,140], 'cyan':[0,255,255,140], 'magenta':[255,0,255,140]
}

# ---- SESSION STATE ----
if 'base_layers_loaded' not in st.session_state:
    st.session_state.base_layers_loaded = []
if 'user_layers' not in st.session_state:
    st.session_state.user_layers = []
if 'view_state' not in st.session_state:
    st.session_state.view_state = {'latitude': 52, 'longitude': -1, 'zoom': 6}

# ---- FUNCTION TO SIMPLIFY LARGE GEOMETRIES ----
def smart_simplify(gdf, tol_small=0.0001, tol_large=0.002):
    try:
        geom_count = len(gdf)
        tol = tol_large if geom_count > 5000 else tol_small
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=tol, preserve_topology=True)
    except Exception as e:
        st.warning(f"Geometry simplification failed: {e}")
    return gdf

# ---- FUNCTION TO CALCULATE BOUNDS ----
def get_bounds(gdf):
    """Get the bounding box of a GeoDataFrame"""
    bounds = gdf.total_bounds  # returns [minx, miny, maxx, maxy]
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2
    
    # Calculate zoom level based on bounds
    lon_diff = abs(bounds[2] - bounds[0])
    lat_diff = abs(bounds[3] - bounds[1])
    max_diff = max(lon_diff, lat_diff)
    
    # Simple zoom calculation
    if max_diff > 10:
        zoom = 5
    elif max_diff > 5:
        zoom = 6
    elif max_diff > 2:
        zoom = 7
    elif max_diff > 1:
        zoom = 8
    elif max_diff > 0.5:
        zoom = 9
    elif max_diff > 0.1:
        zoom = 11
    elif max_diff > 0.05:
        zoom = 12
    else:
        zoom = 13
    
    return center_lat, center_lon, zoom

# ---- LOAD BASE LAYERS ----
for base in BASE_GEOPACKAGES:
    if not Path(base['path']).exists():
        st.warning(f"GeoPackage not found: {base['path']}")
        continue
    for idx, layer_name in enumerate(base['layers']):
        if any(l['name']==layer_name for l in st.session_state.base_layers_loaded):
            continue
        try:
            gdf = gpd.read_file(base['path'], layer=layer_name).to_crs(epsg=4326)
            gdf = smart_simplify(gdf)
            color = COLOR_MAP[base['colors'][idx]]
            st.session_state.base_layers_loaded.append({'name':layer_name,'data':gdf,'color':color})
        except Exception as e:
            st.error(f"Error loading {layer_name}: {e}")

# ---- FILE UPLOAD ----
uploaded_file = st.sidebar.file_uploader(
    "Upload Shapefile (zipped) or GeoPackage", 
    type=['zip', 'gpkg', 'shp'],
    key='file_uploader'
)

if uploaded_file:
    tmp_ext = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if tmp_ext == 'shp':
            # --- Handle standalone .shp file ---
            st.warning("⚠️ Standalone .shp file detected. This may not work without .shx, .dbf, and .prj files.")
            st.info("💡 Tip: Zip all shapefile components (.shp, .shx, .dbf, .prj) together and upload the zip file for best results.")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".shp") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            try:
                gdf = gpd.read_file(tmp_path).to_crs(epsg=4326)
                gdf = smart_simplify(gdf)
                
                # Check if layer already exists
                layer_name = uploaded_file.name
                if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                    st.session_state.user_layers.append({
                        'name': layer_name,
                        'data': gdf,
                        'color': [255,0,255,180]
                    })
                    st.success(f"✓ {uploaded_file.name} loaded successfully!")
                    
                    # Auto-zoom to uploaded layer
                    lat, lon, zoom = get_bounds(gdf)
                    st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
            except Exception as e:
                st.error(f"Error reading standalone .shp file: {e}")
                st.info("Please upload a zipped shapefile containing all components (.shp, .shx, .dbf, .prj)")
        
        elif tmp_ext == 'zip':
            # --- Handle zipped shapefile ---
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                extract_dir = tempfile.mkdtemp()
                zip_ref.extractall(extract_dir)
                
                # Look for .shp
                shp_files = list(Path(extract_dir).glob("**/*.shp"))
                if not shp_files:
                    st.error("No .shp file found in the zip.")
                else:
                    gdf = gpd.read_file(shp_files[0]).to_crs(epsg=4326)
                    gdf = smart_simplify(gdf)
                    
                    # Check if layer already exists
                    layer_name = uploaded_file.name
                    if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                        st.session_state.user_layers.append({
                            'name': layer_name,
                            'data': gdf,
                            'color': [255,0,255,180]
                        })
                        st.success(f"✓ {uploaded_file.name} loaded successfully with {len(gdf)} features!")
                        
                        # Auto-zoom to uploaded layer
                        lat, lon, zoom = get_bounds(gdf)
                        st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
                
                # Cleanup
                shutil.rmtree(extract_dir, ignore_errors=True)
        
        elif tmp_ext == 'gpkg':
            # --- Handle GeoPackage ---
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            layers_in_gpkg = fiona.listlayers(tmp_path)
            layer_sel = st.sidebar.selectbox("Select layer", layers_in_gpkg, key='gpkg_layer_select')
            
            if st.sidebar.button("Load Selected Layer"):
                gdf = gpd.read_file(tmp_path, layer=layer_sel).to_crs(epsg=4326)
                gdf = smart_simplify(gdf)
                
                # Check if layer already exists
                layer_name = f"{uploaded_file.name}-{layer_sel}"
                if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                    st.session_state.user_layers.append({
                        'name': layer_name,
                        'data': gdf,
                        'color': [255,0,255,180]
                    })
                    st.success(f"✓ {layer_name} loaded successfully with {len(gdf)} features!")
                    
                    # Auto-zoom to uploaded layer
                    lat, lon, zoom = get_bounds(gdf)
                    st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
    
    except Exception as e:
        st.error(f"Error reading file: {e}")

# ---- LAYER VISIBILITY ----
st.sidebar.header("SCL Layers")
visible_base = {layer['name']:st.sidebar.checkbox(layer['name'], value=False, key=f"base_{layer['name']}") 
                for layer in st.session_state.base_layers_loaded}

st.sidebar.header("Your Upload Layers")
visible_user = {}
for idx, layer in enumerate(st.session_state.user_layers):
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        visible_user[layer['name']] = st.checkbox(layer['name'], value=True, key=f"user_{idx}_{layer['name']}")
    with col2:
        if st.button("🔍", key=f"zoom_{idx}", help="Zoom to layer"):
            lat, lon, zoom = get_bounds(layer['data'])
            st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
            st.rerun()

# ---- ZOOM TO ALL VISIBLE LAYERS ----
if st.sidebar.button("🌍 Zoom to All Visible Layers"):
    all_visible_gdfs = []
    
    for layer in st.session_state.base_layers_loaded:
        if visible_base.get(layer['name'], False):
            all_visible_gdfs.append(layer['data'])
    
    for layer in st.session_state.user_layers:
        if visible_user.get(layer['name'], True):
            all_visible_gdfs.append(layer['data'])
    
    if all_visible_gdfs:
        # Combine all visible layers
        combined_gdf = gpd.GeoDataFrame(pd.concat(all_visible_gdfs, ignore_index=True))
        lat, lon, zoom = get_bounds(combined_gdf)
        st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
        st.rerun()

# ---- CREATE PYDECK LAYERS ----
deck_layers = []

# Add base layers
for layer in st.session_state.base_layers_loaded:
    if visible_base.get(layer['name'], False):
        deck_layers.append(pdk.Layer(
            "GeoJsonLayer",
            layer['data'].__geo_interface__,
            stroked=True,
            filled=True,
            get_fill_color=layer['color'],
            get_line_color=[0,0,0,255],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
            opacity=0.7
        ))

# Add user layers
for layer in st.session_state.user_layers:
    if visible_user.get(layer['name'], True):
        deck_layers.append(pdk.Layer(
            "GeoJsonLayer",
            layer['data'].__geo_interface__,
            stroked=True,
            filled=True,
            get_fill_color=layer['color'],
            get_line_color=[255,0,0,255],
            line_width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
            opacity=0.8
        ))

# ---- INITIAL VIEW ----
view_state = pdk.ViewState(
    latitude=st.session_state.view_state['latitude'],
    longitude=st.session_state.view_state['longitude'],
    zoom=st.session_state.view_state['zoom'],
    pitch=0
)

# ---- RENDER MAP WITH LIGHT BASEMAP ----
if deck_layers or True:  # Always show map
    r = pdk.Deck(
        layers=deck_layers,
        initial_view_state=view_state,
        map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',  # Light CartoDB basemap
        tooltip={"text": "{name}"}
    )
    st.pydeck_chart(r, use_container_width=True)
else:
    st.info("Select at least one layer to display.")

# ---- INFO SECTION ----
st.sidebar.markdown("---")
st.sidebar.info("""
**Map Controls:**
- 🔍 Click zoom button next to your upload layer to center on it
- 🌍 Use 'Zoom to All Visible' to see all layers visible
- Drag to pan, scroll to zoom

**Basemap Options:**
Current: CartoDB Positron (light)

**Tip:** For shapefiles, zip all components together (.shp, .shx, .dbf, .prj)
""")