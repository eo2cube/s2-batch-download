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
                filename = './' + jobname + '/'+jobname+'.zip'
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
            ready = os.path.isfile('./'+data['jobname']+'/'+data['jobname']+'.zip')
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

def make_filename(pattern, name, yymmdd, jobname):
    filename = pattern.replace('name', name).replace('yymmdd', yymmdd)
    return './' + jobname + '/' + filename

def calculate_index(indexname, pattern, yymmdd, jobname):
    if indexname == 'ndvi':
        with rasterio.open(make_filename(pattern, 'red', yymmdd, jobname)) as red_src:
            with rasterio.open(make_filename(pattern, 'nir', yymmdd, jobname)) as nir_src:
                red = red_src.read(1).astype('float64')
                nir = nir_src.read(1).astype('float64')
                denominator = nir+red
                ndvi = np.where(denominator==0., 0, (nir-red)/(nir+red))
                with rasterio.open(
                    make_filename(pattern, 'ndvi', yymmdd, jobname),
                    'w',
                    driver='Gtiff',
                    width = red_src.width,
                    height = red_src.height,
                    count=1, crs=red_src.crs,
                    transform=red_src.transform,
                    dtype='float64'
                ) as tiff:
                    tiff.write(ndvi, 1)
    return


def run_worker():
    while True:
        data = q.get()
        logging.info(data)
        logging.info("That was the worker")

        bbox, start, end, bands, indices, pattern, jobname = data.values()
        logging.info(jobname)
        search = get_search_result(bbox, start, end)

        os.mkdir('./' + jobname)

        f = open('./' + jobname + "/" + jobname + ".txt", "a") 
        f.write(json.dumps(data))
        f.close()

        tempbands = []
        for index in indices:
            if index=='ndvi' and 'red' not in bands:
                tempbands.append('red')
            if index=='ndvi' and 'nir' not in bands:
                tempbands.append('nir')


        for item in search.items():
            yymmdd = str(item.datetime)[2:10].replace('-', '')
            for band in bands + tempbands:
                filename = make_filename(pattern, band, yymmdd, jobname)
                logging.info(filename)
                save_cog_subset(item.assets[band].href, bbox, filename)
            for index in indices:
                logging.info("Calculating " + index.upper())
                calculate_index(index, pattern, yymmdd, jobname)
            for band in tempbands:
                filename = make_filename(pattern, band, yymmdd, jobname)
                os.remove(filename)

        logging.info('Zipping...')
        shutil.make_archive('./'+jobname, 'zip', './'+jobname)
        shutil.move('./'+jobname+'.zip', './'+jobname+'/'+jobname+'.zip')
        logging.info('Finished!')


###############################################################################


if __name__ == '__main__':
    t1 = Thread(target = run_server)
    t1.start()

    t2 = Thread(target = run_worker)
    t2.start()
