import geopandas as gpd
from pathlib import Path
import fiona

input_folder = Path("custom_repository/data")
output_folder = Path("custom_repository/data_simplified")
output_folder.mkdir(exist_ok=True)

geopackages = {
    'Sensitive_Parties.gpkg': 0.0005,
    'Environmental_Designations.gpkg': 0.003,
    'Special_Category_Land.gpkg': 0.003
}

for gpkg_name, tolerance in geopackages.items():
    gpkg_path = input_folder / gpkg_name
    
    if not gpkg_path.exists():
        print(f"❌ {gpkg_name} not found")
        continue
    
    layers = fiona.listlayers(str(gpkg_path))
    print(f"\n📦 Processing {gpkg_name} ({len(layers)} layers)...")
    
    for layer in layers:
        try:
            print(f"  🔧 {layer}...", end=" ")
            gdf = gpd.read_file(gpkg_path, layer=layer)
            gdf['geometry'] = gdf['geometry'].simplify(tolerance=tolerance, preserve_topology=True)
            
            output_path = output_folder / gpkg_name
            gdf.to_file(output_path, layer=layer, driver='GPKG')
            print(f"✓")
        except Exception as e:
            print(f"❌ {e}")
    
    output_size = (output_folder / gpkg_name).stat().st_size / (1024 * 1024)
    print(f"  📊 Size: {output_size:.2f} MB")

print("\n✅ Done!")