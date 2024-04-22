FROM python:3

WORKDIR /home/hsnb

#COPY requirements.txt ./

RUN pip install rasterio numpy pystac_client

COPY . .

CMD [ "python", "./server-worker.py" ]
