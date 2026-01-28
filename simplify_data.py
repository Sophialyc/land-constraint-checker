import geopandas as gpd
from pathlib import Path
import fiona

input_folder = Path("custom_repository/data")  # use already split files
output_folder = Path("custom_repository/data_simplified")  # new folder for simplified results
output_folder.mkdir(exist_ok=True)

# Only the two large files
geopackages = {
    'Crow_act_2000.gpkg': 0.065,  # increase tolerance if needed
}

for gpkg_name, tolerance in geopackages.items():
    gpkg_path = input_folder / gpkg_name
    if not gpkg_path.exists():
        print(f"❌ {gpkg_name} not found")
        continue

    layers = fiona.listlayers(str(gpkg_path))
    print(f"\n📦 Processing {gpkg_name} ({len(layers)} layers)...")

    output_path = output_folder / gpkg_name

    for i, layer in enumerate(layers):
        try:
            print(f"  🔧 {layer}...", end=" ")
            gdf = gpd.read_file(gpkg_path, layer=layer)
            gdf['geometry'] = gdf['geometry'].simplify(tolerance=tolerance, preserve_topology=True)
            
            # Save first layer with 'w', append others with 'a'
            gdf.to_file(output_path, layer=layer, driver='GPKG', mode='w' if i == 0 else 'a')
            print("✓")
        except Exception as e:
            print(f"❌ {e}")

    output_size = output_path.stat().st_size / (1024 * 1024)
    print(f"  📊 Output size: {output_size:.2f} MB")

print("\n✅ Done!")