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
    {'path':'custom_repository/data/AONB.gpkg','layers':['environmental_designations__aonb'], 'colors':['blue'], 'display_name':'AONB'},
    {'path':'custom_repository/data/Conservation_areas.gpkg','layers':['special_category_land__conservation_areas'], 'colors':['gray'], 'display_name':'Conservation Areas'},
    {'path':'custom_repository/data/Country_parks.gpkg','layers':['environmental_designations__country_parks'], 'colors':['red'], 'display_name':'Country Parks'},
    {'path':'custom_repository/data/Crow_act_2000.gpkg','layers':['special_category_land__crow_act_2000'], 'colors':['black'], 'display_name':'CROW Act 2000'},
    {'path':'custom_repository/data/Local_nature_reserves.gpkg','layers':['environmental_designations__local_nature_reserves'], 'colors':['green'], 'display_name':'Local Nature Reserves'},
    {'path':'custom_repository/data/National_nature_reserves.gpkg','layers':['environmental_designations__national_nature_reserves'], 'colors':['purple'], 'display_name':'National Nature Reserves'},
    {'path':'custom_repository/data/National_parks.gpkg','layers':['environmental_designations__national_parks'], 'colors':['orange'], 'display_name':'National Parks'},
    {'path':'custom_repository/data/National_trust_land_always_open.gpkg','layers':['special_category_land__national_trust_land_always_open'], 'colors':['brown'], 'display_name':'National Trust (Always Open)'},
    {'path':'custom_repository/data/National_trust_land_limited_access.gpkg','layers':['special_category_land__national_trust_limited_access'], 'colors':['cyan'], 'display_name':'National Trust (Limited Access)'},
    {'path':'custom_repository/data/Open_greenspace.gpkg','layers':['special_category_land__open_greenspace'], 'colors':['magenta'], 'display_name':'Open Greenspace'},
    {'path':'custom_repository/data/RAMSAR.gpkg','layers':['environmental_designations__ramsar'], 'colors':['darkblue'], 'display_name':'RAMSAR'},
    {'path':'custom_repository/data/SAC.gpkg','layers':['environmental_designations__sac'], 'colors':['darkred'], 'display_name':'SAC'},
    {'path':'custom_repository/data/Sensitive_Parties.gpkg','layers':['canals_on_the_trust_network', 'dry_docks', 'network_rail_centre_lines', 'nwr_elrs'], 'colors':['pink', 'lightblue', 'lightgreen', 'beige'], 'display_name':'Sensitive Parties'},
    {'path':'custom_repository/data/SPA.gpkg','layers':['environmental_designations__spa'], 'colors':['darkgreen'], 'display_name':'SPA'},
    {'path':'custom_repository/data/SSSI.gpkg','layers':['environmental_designations__sssi'], 'colors':['cadetblue'], 'display_name':'SSSI'},
]

COLOR_MAP = {
    'blue':[0,0,255,140], 'red':[255,0,0,140], 'green':[0,255,0,140], 'purple':[128,0,128,140],
    'orange':[255,165,0,140], 'darkblue':[0,0,139,140], 'darkred':[139,0,0,140], 'darkgreen':[0,100,0,140],
    'cadetblue':[95,158,160,140], 'pink':[255,192,203,140], 'gray':[128,128,128,140],
    'black':[0,0,0,140], 'brown':[165,42,42,140], 'cyan':[0,255,255,140], 'magenta':[255,0,255,140],
    'lightblue':[173,216,230,140], 'lightgreen':[144,238,144,140], 'beige':[245,245,220,140]
}

# ---- SESSION STATE ----
if 'loaded_layers_cache' not in st.session_state:
    st.session_state.loaded_layers_cache = {}
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
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2
    lon_diff = abs(bounds[2] - bounds[0])
    lat_diff = abs(bounds[3] - bounds[1])
    max_diff = max(lon_diff, lat_diff)
    if max_diff > 10: zoom = 5
    elif max_diff > 5: zoom = 6
    elif max_diff > 2: zoom = 7
    elif max_diff > 1: zoom = 8
    elif max_diff > 0.5: zoom = 9
    elif max_diff > 0.1: zoom = 11
    elif max_diff > 0.05: zoom = 12
    else: zoom = 13
    return center_lat, center_lon, zoom

# ---- FUNCTION TO LOAD A LAYER ON-DEMAND ----
@st.cache_data
def load_layer(path, layer_name):
    """Load and cache a single layer"""
    try:
        gdf = gpd.read_file(path, layer=layer_name).to_crs(epsg=4326)
        gdf = smart_simplify(gdf)
        return gdf
    except Exception as e:
        st.error(f"Error loading {layer_name}: {e}")
        return None

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
            st.warning("⚠️ Standalone .shp file detected. This may not work without .shx, .dbf, and .prj files.")
            st.info("💡 Tip: Zip all shapefile components (.shp, .shx, .dbf, .prj) together and upload the zip file for best results.")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".shp") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            try:
                gdf = gpd.read_file(tmp_path).to_crs(epsg=4326)
                gdf = smart_simplify(gdf)
                
                layer_name = uploaded_file.name
                if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                    st.session_state.user_layers.append({
                        'name': layer_name,
                        'data': gdf,
                        'color': [255,0,255,180]
                    })
                    st.success(f"✓ {uploaded_file.name} loaded successfully!")
                    
                    lat, lon, zoom = get_bounds(gdf)
                    st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
            except Exception as e:
                st.error(f"Error reading standalone .shp file: {e}")
        
        elif tmp_ext == 'zip':
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                extract_dir = tempfile.mkdtemp()
                zip_ref.extractall(extract_dir)
                
                shp_files = list(Path(extract_dir).glob("**/*.shp"))
                if not shp_files:
                    st.error("No .shp file found in the zip.")
                else:
                    gdf = gpd.read_file(shp_files[0]).to_crs(epsg=4326)
                    gdf = smart_simplify(gdf)
                    
                    layer_name = uploaded_file.name
                    if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                        st.session_state.user_layers.append({
                            'name': layer_name,
                            'data': gdf,
                            'color': [255,0,255,180]
                        })
                        st.success(f"✓ {uploaded_file.name} loaded successfully with {len(gdf)} features!")
                        
                        lat, lon, zoom = get_bounds(gdf)
                        st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
                
                shutil.rmtree(extract_dir, ignore_errors=True)
        
        elif tmp_ext == 'gpkg':
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            layers_in_gpkg = fiona.listlayers(tmp_path)
            layer_sel = st.sidebar.selectbox("Select layer", layers_in_gpkg, key='gpkg_layer_select')
            
            if st.sidebar.button("Load Selected Layer"):
                gdf = gpd.read_file(tmp_path, layer=layer_sel).to_crs(epsg=4326)
                gdf = smart_simplify(gdf)
                
                layer_name = f"{uploaded_file.name}-{layer_sel}"
                if not any(l['name'] == layer_name for l in st.session_state.user_layers):
                    st.session_state.user_layers.append({
                        'name': layer_name,
                        'data': gdf,
                        'color': [255,0,255,180]
                    })
                    st.success(f"✓ {layer_name} loaded successfully with {len(gdf)} features!")
                    
                    lat, lon, zoom = get_bounds(gdf)
                    st.session_state.view_state = {'latitude': lat, 'longitude': lon, 'zoom': zoom}
    
    except Exception as e:
        st.error(f"Error reading file: {e}")

# ---- LAYER VISIBILITY (with on-demand loading) ----
st.sidebar.header("Base Constraint Layers")

# Group layers by category
env_layers = [l for l in BASE_GEOPACKAGES if 'environmental' in l['path'] or l['display_name'] in ['AONB', 'Country Parks', 'Local Nature Reserves', 'National Nature Reserves', 'National Parks', 'RAMSAR', 'SAC', 'SPA', 'SSSI']]
scl_layers = [l for l in BASE_GEOPACKAGES if 'special_category' in l['path'] or l['display_name'] in ['Conservation Areas', 'CROW Act 2000', 'National Trust (Always Open)', 'National Trust (Limited Access)', 'Open Greenspace']]
sensitive_layers = [l for l in BASE_GEOPACKAGES if 'Sensitive' in l['display_name']]

visible_base_layers = {}

with st.sidebar.expander("Environmental Designations", expanded=False):
    for base in env_layers:
        if Path(base['path']).exists():
            visible_base_layers[base['display_name']] = st.checkbox(
                base['display_name'], 
                value=False, 
                key=f"base_{base['display_name']}"
            )

with st.sidebar.expander("Special Category Land", expanded=False):
    for base in scl_layers:
        if Path(base['path']).exists():
            visible_base_layers[base['display_name']] = st.checkbox(
                base['display_name'], 
                value=False, 
                key=f"base_{base['display_name']}"
            )

with st.sidebar.expander("Sensitive Parties", expanded=False):
    for base in sensitive_layers:
        if Path(base['path']).exists():
            # Sensitive_Parties has multiple layers
            for idx, layer_name in enumerate(base['layers']):
                visible_base_layers[layer_name] = st.checkbox(
                    layer_name.replace('_', ' ').title(), 
                    value=False, 
                    key=f"base_{layer_name}"
                )

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

# ---- CREATE PYDECK LAYERS (only for visible/selected layers) ----
deck_layers = []

# Load and display base layers ONLY if selected
for base in BASE_GEOPACKAGES:
    if not Path(base['path']).exists():
        continue
    
    for idx, layer_name in enumerate(base['layers']):
        # Check if this layer is selected
        is_visible = visible_base_layers.get(base['display_name'], False) or visible_base_layers.get(layer_name, False)
        
        if is_visible:
            # Load layer on-demand (cached)
            gdf = load_layer(base['path'], layer_name)
            
            if gdf is not None:
                color = COLOR_MAP[base['colors'][idx]]
                deck_layers.append(pdk.Layer(
                    "GeoJsonLayer",
                    gdf.__geo_interface__,
                    stroked=True,
                    filled=True,
                    get_fill_color=color,
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

# ---- RENDER MAP ----
r = pdk.Deck(
    layers=deck_layers,
    initial_view_state=view_state,
    map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    tooltip=True
)
st.pydeck_chart(r, use_container_width=True)

# ---- INFO ----
st.sidebar.markdown("---")
st.sidebar.info(f"""
**Layers loaded:** {len(deck_layers)}

💡 **Tip:** Select only the layers you need to improve performance.
""")