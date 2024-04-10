import './assets/main.css';

import { createApp } from 'vue'
import App from './App.vue'

const app = createApp(App);
app.config.devtools = true;
app.mount('#app');
