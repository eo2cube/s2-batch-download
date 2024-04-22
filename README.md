# Sentinel-2 Batch Download Tool for HSNB

This tool provides a rudimentary web GUI to query Sentinel-2 satellite imagery for a custom bounding box and time span which can then be downloaded as a single ZIP file. It was developed by the datacube team at [EORC](https://earth-observation.org/) for agricultural scientists at [HSNB](https://www.hs-nb.de/).

## Setup

### Prerequisites
You'll need Node.js and Docker.

### Get the code
Clone this repo. 

### Build the web UI
```
cd /path/to/repo
cd ui
npm install
npm run build
```
This will create a `dist` folder within the `ui` folder, from where the static files are served that form the website that end users actually see.

### Create an output directory
```
cd /path/to/repo
mkdir jobs
```
Or let it point wherever it is convenient for you (lots of gigabytes will be written there).

### Prepare Docker
Add to your `docker-compose.yml`:
```
hsnb:
  build:
    context: ./hsnb
  image: python:3
  container_name: hsnb
  volumes:
  - ./hsnb/jobs:/home/hsnb/jobs
  networks:
    - caddy
```
This assumes that you cloned the repo into a folder called `hsnb` within the same folder as your `docker-compose.yml`. And it also assumes that you have a Docker network called `caddy` where a web server does reverse proxying. The `volumes` section links the `jobs` folder in the actual file system (the path on the left of the colon) to the `jobs` folder in the container's file system (the path on the right of the colon).

### Tell your webserver (if applicable)
Add to your `Caddyfile` (via `sudo nano /etc/caddy/Caddyfile`):
```
hsnb.eo2cube.org {
        reverse_proxy hsnb:8765
}
```
And update the Caddy config with `docker exec -w /etc/caddy caddy caddy reload` (assuming the Caddy webserver is running in a Docker container called `caddy`).

### Start it
Then finally:
```
docker compose build hsnb
docker compose up hsnb
```

## Contact
Christoph Friedrich <christoph.friedrich@uni-wuerzburg.de>
