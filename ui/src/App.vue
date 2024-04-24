<template>
  <header>
    <h1>HSNB Sentinel-2 Data Downloader</h1>
  </header>

  <h2>AOI</h2>
  BBOX:
  <input v-model="bbox"> (CRS: WGS84 - format: xmin,ymin,xmax,ymax - e.g.: 13.18260,53.81978,13.286973,53.840044)

  <h2>Time</h2>
  Start: <input v-model="start">
  End: <input v-model="end">
  (format: YYYY-MM-DD)
  
  <h2>Bands</h2>
  <div class="checkboxcontainer" v-for="band in BANDS">
    <input type="checkbox" :id="band.name" :value="band.name" v-model="bands"><label :for="band.name">Band {{ band.number }} ({{ band.name }})</label>
  </div>

  <h2>Indices</h2>
  <div class="checkboxcontainer" v-for="index in ['ndvi', 'ndre', 'ngrdi', 'savi', 'mois', 'evi']">
    <input type="checkbox" :id="index" :value="index" v-model="indices"><label :for="index">{{ index.toUpperCase() }}</label>
  </div>

  <h2>Filename Pattern</h2>
  <input v-model="pattern"> ("yymmdd" and "name" will be replaced by e.g. "240410" and "ndvi")

  <h2>Submit</h2>

  <button @click="check">1. Check search</button>
  <button @click="order">2. Start processing</button>

  <h2>Job</h2>
  Name: {{ jobname }}<br>
  <button @click="status">3. Get status</button>
  <a :href="'/download/'+jobname+'.zip'">4. Download</a>

  <footer>Contact: Christoph Friedrich &lt;christoph.friedrich (ät) uni-wuerzburg.de&gt;</footer>
</template>

<script setup>
import { ref } from "vue";

const bbox = ref('13.18260, 53.81978, 13.286973, 53.840044');
const start = ref('2024-03-05');
const end = ref('2024-03-09');  // try until -23
const bands = ref(['red','green','blue']);
const indices = ref(['ndvi']);
const pattern = ref('yymmdd-name.tiff')

const jobname = ref(null);

const BANDS = [
  {number: '1',  name: 'coastal'},
  {number: '2',  name: 'blue'},
  {number: '3',  name: 'green'},
  {number: '4',  name: 'red'},
  {number: '5',  name: 'rededge1'},
  {number: '6',  name: 'rededge2'},
  {number: '7',  name: 'rededge3'},
  {number: '8',  name: 'nir'},
  {number: '8a', name: 'nir08'},
  {number: '9',  name: 'nir09'},
  {number: '11', name: 'swir16'},
  {number: '12', name: 'swir22'}
]

function post(url) {
  return fetch(url, {
    method: "POST",
    headers: {'Content-Type': 'application/json'}, 
    body: JSON.stringify({
      bbox: bbox.value.split(',').map(parseFloat),
      start: start.value,
      end: end.value,
      bands: bands.value,
      indices: indices.value,
      pattern: pattern.value
    })
  })
}

function check() {
  post('/api/check').then(async res => {
    let data = await res.json();
    alert(`Matched ${data.matched} items. If you think that's okay, click 'Start' now. Otherwise limit your search more and click 'Check' again.`);
  });
}

function order() {
  post('/api/order').then(async res => {
    let data = await res.json();
    jobname.value = data.jobname;
    alert(`Job submitted with ID: ${data.jobname}`);
  });
}

function status() {
  return fetch('/api/status', {
    method: "POST",
    headers: {'Content-Type': 'application/json'}, 
    body: JSON.stringify({
      jobname: jobname.value
    })
  }).then(async res => {
    let data = await res.json();
    if (data.ready) alert('Ready!'); else alert("Not ready yet");
  });
}
</script>

<style scoped>
header {
  line-height: 1.5;
}

footer {
  margin-top: 50px;
}

@media (min-width: 1024px) {
  header {
    display: flex;
    place-items: center;
    padding-right: calc(var(--section-gap) / 2);
  }
}

h2 {
  margin-top: 20px;
  margin-bottom: 10px;
}

div.checkboxcontainer {
  margin-bottom: 10px;
  padding-left: 20px;
}

div.checkboxcontainer input {
  margin-right: 10px;
}

button {
  margin-top: 20px;
  padding: 5px 20px;
  font-size: 14pt;
}
</style>
