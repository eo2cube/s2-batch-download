#!/usr/bin/env python3
"""
Author: Christoph Friedrich <christoph.friedrich@uni-wuerzburg.de>
Usage: python3 server-worker.py
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

from threading import Thread

import queue
q = queue.Queue()

import json

import os
from datetime import datetime

import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from pystac_client import Client as stac

import shutil


###############################################################################


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

def get_search_result(bbox, start, end):
    catalog = stac.open("https://earth-search.aws.element84.com/v1")
    return catalog.search(
        max_items = None,
        collections = ['sentinel-2-l2a'],
        bbox = bbox,
        datetime = [start+'T00:00:00Z', end+'T00:00:00Z'],
    )


###############################################################################


class S(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200, "ok")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        
        logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))

        if self.path == '/':
            f = open('./ui/dist/index.html', 'rb')
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f.read())
            f.close()
            return
        
        if self.path.startswith('/assets/'):
            filename = self.path.replace('/assets/','')
            f = open('./ui/dist/assets/'+filename, 'rb')
            if self.path.endswith('.css'):
                self.send_header('Content-type', 'text/css')
            else:
                self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            self.wfile.write(f.read())
            f.close()
            return

        if self.path.startswith("/download/"):
            try:
                jobname = self.path.replace('/download/','').replace('.zip','')
                filename = './jobs/' + jobname + '/'+jobname+'.zip'
                logging.info(filename)
                f = open(filename, 'rb')
                self.send_header('Content-type', 'application/zip')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return
            except IOError:
                self.send_error(404,'File Not Found: %s' % self.path)

        if self.path == '/put':
            q.put({
                'bbox': [13.18260, 53.81978, 13.286973, 53.840044],  # format: xmin, ymin, xmax, ymax (order: lon, lat) (CRS: WGS 84, EPSG:4326)
                'start': '2024-03-05',  # format: YYYY-MM-DD
                'end': '2024-03-23',  # format: YYYY-MM-DD
                # band number to name mappings: 1=coastal, 2=blue, 3=green, 4=red, 5=rededge1, 6=rededge2, 7=rededge3, 8=nir, 8a=nir08, 9=nir09, 11=swir16, 12=swir22
                'bands': ['coastal', 'blue', 'green', 'red', 'rededge1', 'rededge2', 'rededge3', 'nir', 'nir08', 'nir09', 'swir16', 'swir22'],
                'indices': ['ndvi'],  # not implemented yet
                'pattern': 'out/yymmdd-name.tiff'  # any folder structure must exist
                })
        
        if self.path == '/api/status':
            self.end_headers()
            self.wfile.write(q.qsize)
            return

        self.end_headers()
        self.wfile.write(" GET request for {}".format(str(q.qsize())).encode('utf-8'))


    def do_POST(self):
        self.send_response(200, "ok")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
       
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        data = json.loads(post_data)
        logging.info("POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
                str(self.path), str(self.headers), post_data.decode('utf-8'))

        if(self.path == '/api/status'):
            ready = os.path.isfile('./jobs/'+data['jobname']+'/'+data['jobname']+'.zip')
            logging.info(ready)
            self.wfile.write(('{"ready":' + ('true' if ready else 'false') + '}').encode('utf-8'))
            return

        bbox, start, end, *rest = data.values()
        search = get_search_result(bbox, start, end)
        
        if(self.path == '/api/check'):
            item_count = search.matched()
            #files_per_item = len(bands) + len(indices)
            #out = f"Your search matched {item_count} items"
            #out += f"You requested {len(bands)} bands and {len(indices)} indices, i.e. {files_per_item} files per item"
            #out += f"That means you will download {item_count*files_per_item} files in total"
            #self.wfile.write(out.encode('utf-8'))
            self.wfile.write(('{"matched":' + str(item_count) + '}').encode('utf-8'))

        if(self.path == '/api/order'):
            logging.info('Putting to queue')
            jobname = datetime.now().strftime("job-%Y-%m-%d-%H-%M-%S")
            data['jobname'] = jobname
            q.put(data)
            self.wfile.write(('{"jobname":"' + jobname + '"}').encode('utf-8'))


    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()


###############################################################################


def run_server(server_class=HTTPServer, handler_class=S, port=8765):
    logging.basicConfig(level=logging.INFO)
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logging.info('Starting httpd...\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')


###############################################################################


def make_filename(pattern, name, yymmdd, jobname):
    filename = pattern.replace('name', name).replace('yymmdd', yymmdd)
    return './jobs/' + jobname + '/' + filename

class Metadata:
    def __init__(self, width, height, crs, transform):
        self.width = width
        self.height = height
        self.crs = crs
        self.transform = transform

# The `metadata` parameter can be a DatasetReader or of class Metadata (it's only important that it has `width`, `height`, `crs` and `transform` available via the dot operator)
def save_as_tiff(data, metadata, filename):
    data_shape = np.shape(data)
    bands_to_write_to = [1] if len(data_shape)==2 else list(range(1, data_shape[0]+1))  # e.g. [4,100,200] -> [1,2,3,4]
    with rasterio.open(
        filename,
        'w',
        driver ='Gtiff',
        width = metadata.width,
        height = metadata.height,
        count = len(bands_to_write_to),
        crs = metadata.crs,
        transform = metadata.transform,
        dtype = 'float64'
    ) as tiff:
        tiff.write(data, bands_to_write_to)

# Takes a coarser array of shape (x,y) and a finer array of shape (2x+a,2y+b) where a,b can be 0 or 1 independently
# Returns the coarser array doubled in both dimensions, the finer array with possibly the last row and/or column removed to fit the shape of the other array, and the new shape
def resample_to_same_shape(finer_array, coarser_array):
    doubled_v = np.repeat(coarser_array, 2, axis=0)
    doubled_vh = np.repeat(doubled_v, 2, axis=1)
    result2 = doubled_vh
    shape_to_match = np.shape(result2)
    shape_of_finer = np.shape(finer_array)
    result1 = finer_array
    if shape_of_finer[0] > shape_to_match[0]:
        result1 = np.delete(result1, shape_of_finer[0]-1, 0)
    if shape_of_finer[1] > shape_to_match[1]:
        result1 = np.delete(result1, shape_of_finer[1]-1, 1)
    return result1, result2, shape_to_match

# important: the first entry is the band that is used in the *numerator* of the corresponding formula, the second entry the one in the *denominator*
# this is also the reason why they are arrays and not sets
BANDS_FOR_INDICES = {
    'ndvi':  ['nir', 'red'],
    'evi':   ['red', 'nir', 'blue'],
    'ndyi':  ['green', 'blue'],
    'ngrdi': ['green', 'red'],
    'ndre':  ['nir', 'rededge1'],
    'msavi': ['red', 'nir'],
    'vari':  ['green', 'red', 'blue'],  # special case
    'ndsi':  ['red', 'rededge1'],
    'msi':   ['swir16', 'nir'],
    'reip':  ['red', 'rededge1', 'rededge2', 'rededge3'],  # special case
    'mois':  ['nir08', 'swir16'],
}

def calculate_index(indexname, pattern, yymmdd, jobname):
    # formulas based on a rather simple fraction ("normalized difference" and very similar)
    if indexname in ['ndvi', 'ndyi', 'ndre', 'ndsi', 'ngrdi', 'mois', 'vari', 'msi']:
        bandname1 = BANDS_FOR_INDICES[indexname][0]
        bandname2 = BANDS_FOR_INDICES[indexname][1]
        with rasterio.open(make_filename(pattern, bandname1, yymmdd, jobname)) as src_band1:
            with rasterio.open(make_filename(pattern, bandname2, yymmdd, jobname)) as src_band2:
                # load bands
                band1 = src_band1.read(1).astype('float64')
                band2 = src_band2.read(1).astype('float64')

                # resample if necessary
                band1_shape = np.shape(band1)
                band2_shape = np.shape(band2)
                final_shape = None
                final_transform = None
                final_crs = src_band1.crs  # they are all the same anyway
                if band1_shape[0] > band2_shape[0]:  # detect which one is the coarser and which one the finer array
                    band1, band2, final_shape = resample_to_same_shape(band1, band2)  # resample (and store possibly altered shape)
                    final_transform = src_band1.transform  # use the transform of the finer array because it has the 10m resolution, not the 20m
                elif band1_shape[0] < band2_shape[0]:  # the same vice versa
                    band2, band1, final_shape = resample_to_same_shape(band2, band1)
                    final_transform = src_band2.transform
                else:
                    final_shape = band1_shape  # both are the same -> doesn't matter if it's 1 or 2
                    final_transform = src_band1.transform

                # calculate
                numerator = (band1-band2)  # default case (normalized difference)
                denominator = (band1+band2)
                if indexname == 'msi':  # more simple case where formula is just the ratio of the bands without any normalization
                    numerator = band1
                    denominator = band2
                if indexname == 'vari':  # special case where additionally to the normal formula blue is subtracted from the denominator
                    with rasterio.open(make_filename(pattern, 'blue', yymmdd, jobname)) as src_band3:
                        band3 = src_band3.read(1).astype('float64')
                        denominator -= band3
                result = np.where(denominator==0., 0, numerator/denominator)  # set 0 where division would be undefined

                # save
                metadata = Metadata(final_shape[1], final_shape[0], final_crs, final_transform)
                save_as_tiff(result, metadata, make_filename(pattern, indexname, yymmdd, jobname))

    # more special formulas

    if indexname == 'evi':
        with rasterio.open(make_filename(pattern, 'red', yymmdd, jobname)) as red_src:
            with rasterio.open(make_filename(pattern, 'nir', yymmdd, jobname)) as nir_src:
                with rasterio.open(make_filename(pattern, 'blue', yymmdd, jobname)) as blue_src:
                    red = red_src.read(1).astype('float64') / 10000
                    nir = nir_src.read(1).astype('float64') / 10000
                    blue = blue_src.read(1).astype('float64') / 10000
                    G = 2.5
                    C1 = 6
                    C2 = 7.5
                    L = 1
                    denominator = (nir + C1*red - C2*blue + L)
                    evi = np.clip(np.where(denominator==0., 0, G*((nir-red)/denominator)), -1, 1)
                    save_as_tiff(evi, red_src, make_filename(pattern, 'evi', yymmdd, jobname))
                    
    if indexname == 'reip':
        with rasterio.open(make_filename(pattern, 'red', yymmdd, jobname)) as red_src:
            with rasterio.open(make_filename(pattern, 'rededge1', yymmdd, jobname)) as re1_src:
                with rasterio.open(make_filename(pattern, 'rededge2', yymmdd, jobname)) as re2_src:
                    with rasterio.open(make_filename(pattern, 'rededge3', yymmdd, jobname)) as re3_src:
                        red = red_src.read(1).astype('float64')
                        re1 = re1_src.read(1).astype('float64')
                        re2 = re2_src.read(1).astype('float64')
                        re3 = re3_src.read(1).astype('float64')
                        _, re1, _ = resample_to_same_shape(red, re1)
                        _, re2, _ = resample_to_same_shape(red, re2)
                        red, re3, final_shape = resample_to_same_shape(red, re3)
                        denominator = (re2-re1)
                        reip = np.where(denominator==0., 0, 700+40*(((red+re3)/2)-re1/denominator))
                        metadata = Metadata(final_shape[1], final_shape[0], red_src.crs, red_src.transform)
                        save_as_tiff(reip, metadata, make_filename(pattern, indexname, yymmdd, jobname))

    if indexname == 'msavi':
        with rasterio.open(make_filename(pattern, 'red', yymmdd, jobname)) as red_src:
            with rasterio.open(make_filename(pattern, 'nir', yymmdd, jobname)) as nir_src:
                red = red_src.read(1).astype('float64')
                nir = nir_src.read(1).astype('float64')
                radicand = np.square(2*nir+1) - 8*(nir-red)
                msavi = np.where(radicand<0, 0, 2*nir+1-np.sqrt(radicand)/2)
                save_as_tiff(msavi, red_src, make_filename(pattern, indexname, yymmdd, jobname))

    return

def create_composite(name, pattern, yymmdd, jobname):
    if name == 'tci':
        with rasterio.open(make_filename(pattern, 'red', yymmdd, jobname)) as red_src:
            with rasterio.open(make_filename(pattern, 'green', yymmdd, jobname)) as green_src:
                with rasterio.open(make_filename(pattern, 'blue', yymmdd, jobname)) as blue_src:
                    red = red_src.read(1).astype('float64')
                    green = green_src.read(1).astype('float64')
                    blue = blue_src.read(1).astype('float64')
                    save_as_tiff(np.array([red, green, blue]), red_src, make_filename(pattern, 'tci', yymmdd, jobname))

def run_worker():
    while True:
        data = q.get()
        logging.info(data)
        logging.info("That was the worker")

        bbox, start, end, bands, indices, other, pattern, jobname = data.values()
        logging.info(jobname)
        search = get_search_result(bbox, start, end)

        os.mkdir('./jobs/' + jobname)

        f = open('./jobs/' + jobname + "/" + jobname + ".txt", "a") 
        f.write(json.dumps(data))
        f.close()

        bands_explicitly_requested = set(bands)
        bands_implicitly_needed = set()
        for index in indices:
            bands_implicitly_needed |= set(BANDS_FOR_INDICES[index])
        if 'tci' in other:
            bands_implicitly_needed |= set(['red', 'green', 'blue'])
        bands_to_download = bands_explicitly_requested | bands_implicitly_needed  # union of all
        bands_to_delete_later = bands_to_download - bands_explicitly_requested  # only keep those that were explicitly requested

        for item in search.items():
            yymmdd = str(item.datetime)[2:10].replace('-', '')
            for band in bands_to_download:
                filename = make_filename(pattern, band, yymmdd, jobname)
                logging.info(filename)
                save_cog_subset(item.assets[band].href, bbox, filename)
            for index in indices:
                logging.info("Calculating " + index.upper())
                calculate_index(index, pattern, yymmdd, jobname)
            for item in other:
                logging.info("Compositing " + item.upper())
                create_composite(item, pattern, yymmdd, jobname)
            for band in bands_to_delete_later:
                filename = make_filename(pattern, band, yymmdd, jobname)
                os.remove(filename)

        logging.info('Zipping...')
        shutil.make_archive('./jobs/'+jobname, 'zip', './jobs/'+jobname)
        shutil.move('./jobs/'+jobname+'.zip', './jobs/'+jobname+'/'+jobname+'.zip')
        logging.info('Finished!')


###############################################################################


if __name__ == '__main__':
    t1 = Thread(target = run_server)
    t1.start()

    t2 = Thread(target = run_worker)
    t2.start()
