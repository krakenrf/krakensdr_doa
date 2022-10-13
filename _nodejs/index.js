// This is a Websocket server that is a middleware to interface wth the new Krakensdr app and future things

const express = require('express')
const ws = require('ws');
const fs = require('fs');

const app = express()
const port = 8042
const wsport = 8021
const doaInterval = 1000    // Interval the clients should get new doa data in ms

const remoteServer = 'map.krakenrf.com:2096'
const settingsJsonPath = 'settings.json'

let lastDoaUpdate = Date.now()
let settingsJson = {};
let inRemoteMode = false;
let wsClient;
let wsServer;

//load doa settings file
function loadSettingsJson (){
  let rawdata = fs.readFileSync(settingsJsonPath);
  settingsJson = JSON.parse(rawdata);
  console.log("Loaded Settings from json")
  console.log("Freq: "+settingsJson.center_freq);
  console.log("Mode (Data Format): "+settingsJson.doa_data_format);
  console.log("Name: "+settingsJson.station_id);
  console.log("KrakenPro Key: "+settingsJson.krakenpro_key);
  console.log("Lat: "+settingsJson.latitude);
  console.log("Lon: "+settingsJson.longitude);
}
loadSettingsJson();

// if in remote mode connect to server view websocket
if(settingsJson.doa_data_format == 'Kraken Pro Remote' && settingsJson.krakenpro_key != '0') {
  console.log("Remote mode activated");
  inRemoteMode = true;
}

if(inRemoteMode){
  wsClient = new ws("wss://"+remoteServer);

  wsClient.onopen = () => {
    wsClient.send(`{"apikey": "${settingsJson.krakenpro_key}"}`) 
  }
   
  wsClient.onerror = (error) => {
    console.log('WebSocket error:', error)
  }
   
  wsClient.onmessage = (e) => {
    //check what data we got from Server
    var jsn = JSON.parse(e.data);
    if(jsn.function == 'settings'){
      console.log("Got new Settings: "+jsn);
      // read settings fresh from file and set new Settings
      loadSettingsJson();
      settingsJson.center_freq = Number.parseFloat(jsn.freq);      
      fs.writeFileSync(settingsJsonPath, JSON.stringify(settingsJson, null, 2));
    } else {
      console.log(jsn);
    }
  }
} else {
  // when not in Remote mode start websocket server for local connections
  // Websocket that sends incomming Data to App
  wsServer = new ws.Server({ noServer: true });
  wsServer.on('connection', socket => {
    console.log('Got websocket connection!')
    socket.on('message', message => {
        console.log("received: %s",message)
        //socket.send('Connection works to KrakenSDR')
      });
  });

  const server = app.listen(wsport);
  server.on('upgrade', (request, socket, head) => {
    wsServer.handleUpgrade(request, socket, head, socket => {
      wsServer.emit('connection', socket, request);
    });
  });
}

app.use(express.json())

app.get('/', (req, res) => {
    res.send('Hi, this is the KrakenSDR middleware server :)')
})

app.post('/doapost', (req, res) => {
    if(Date.now() - lastDoaUpdate > doaInterval){
      //console.log(req.body);
      lastDoaUpdate = Date.now()
      // in remote mode, send data to sdr server backend like the App does
      if (inRemoteMode) {
        // In remote mode set lat/lon
        //req.body.latitude = settingsJson.latitude; 
        //req.body.longitude = settingsJson.longitude;
        //req.body.gpsBearing = settingsJson.heading;
        console.log(req.body.latitude);
        console.log(req.body.longitude);
        wsClient.send(`{"apikey": "${settingsJson.krakenpro_key}", "data": ${JSON.stringify(req.body)}}`) 
      } else {
        // sends data to all websocket clients
        wsServer.clients.forEach(function each(client) {
          if (client.readyState === ws.OPEN) {
            client.send(JSON.stringify(req.body));
          }
        })
      } 

    } else {
      console.log("...");
    }
    res.sendStatus(200)
  });

app.listen(port, () => {
    console.log(`Middleware HTTP Server is listening at http://localhost:${port}, Websocket on ${wsport}`)
})
