# CONFIG
bbox = [13.18260, 53.81978, 13.286973, 53.840044]  # format: xmin, ymin, xmax, ymax (order: lon, lat) (CRS: WGS 84, EPSG:4326)
start = '2024-03-05'  # format: YYYY-MM-DD
end   = '2024-03-23'  # format: YYYY-MM-DD
# band number to name mappings: 1=coastal, 2=blue, 3=green, 4=red, 5=rededge1, 6=rededge2, 7=rededge3, 8=nir, 8a=nir08, 9=nir09, 11=swir16, 12=swir22
bands = ['coastal', 'blue', 'green', 'red', 'rededge1', 'rededge2', 'rededge3', 'nir', 'nir08', 'nir09', 'swir16', 'swir22']
indices = ['ndvi']  # not implemented yet
pattern = 'out/yymmdd-name.tiff'  # any folder structure must exist

# STOP
# Edit until here and run code once

download = False   # Please leave it on False for the first run to see how many files your search will match, then change it to True and run the script again to actually download

# STOP STOP

import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from pystac_client import Client as stac

def save_cog_subset(url, bbox_4326, filename):
    with rasterio.open(url) as src:
        bounds = transform_bounds(4326, src.crs.to_epsg(), *bbox_4326)
        window = rasterio.windows.from_bounds(*bounds, src.transform)
        chunk = src.read(1, window=window)

        with rasterio.open(
            filename,
            'w',
            driver='GTiff',
            width=chunk.shape[1],
            height=chunk.shape[0],
            count=1,
            dtype=chunk.dtype,
            crs=src.crs,
            transform=src.window_transform(window)
        ) as dst:
            dst.write(chunk, indexes=1)

# example:
#url = 'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/33/U/UV/2023/7/S2A_33UUV_20230715_0_L2A/B02.tif'
#bounds = [380362.3703989794, 5965002.356713361, 387286.92594044295, 5967085.6707827095]
#save_cog_subset(url, bounds, 'test.tiff')  # old when bounds were still expected in the tiff's crs
#save_cog_subset(url, bbox, 'test.tiff')    # new where it's always expected in EPSG:4326

ALL_ASSETS_ALPHABETICAL = ['aot', 'blue', 'coastal', 'granule_metadata', 'green', 'nir', 'nir08', 'nir09', 'red', 'rededge1', 'rededge2', 'rededge3', 'scl', 'swir16', 'swir22', 'thumbnail', 'tileinfo_metadata', 'visual', 'wvp']
# BAND NUMBER:         1          2       3        4      5           6           7           8      8a       9        11        12
ALL_BANDS_IN_ORDER = ['coastal', 'blue', 'green', 'red', 'rededge1', 'rededge2', 'rededge3', 'nir', 'nir08', 'nir09', 'swir16', 'swir22']
# assets that are not included in ALL_BANDS_IN_ORDER: 'aot', 'granule_metadata', 'scl', 'thumbnail', 'tileinfo_metadata', 'visual', 'wvp'

catalog = stac.open("https://earth-search.aws.element84.com/v1")
search = catalog.search(
    max_items = None,
    collections = ['sentinel-2-l2a'],
    bbox = bbox,
    datetime = [start+'T00:00:00Z', end+'T00:00:00Z'],
)

item_count = search.matched()
files_per_item = len(bands) + len(indices)
print(f"Your search matched {item_count} items")
print(f"You requested {len(bands)} bands and {len(indices)} indices, i.e. {files_per_item} files per item")
print(f"That means you will download {item_count*files_per_item} files in total")

if not download:
    print("If you're sure you want to continue, set the 'download' variable to 'True' and run this script again")

else:

    for item in search.items():
        yymmdd = str(item.datetime)[2:10].replace('-', '')
        for band in bands:
            filename = pattern.replace('name', band).replace('yymmdd', yymmdd)
            print(filename)
            save_cog_subset(item.assets[band].href, bbox, filename)