// This is a Websocket server that is a middleware to interface wth the new Krakensdr app and future things
require('log-timestamp');
const express = require('express')
const ws = require('ws');
const fs = require('fs');
const crypto = require('crypto');

const app = express()
const port = 8042
const wsport = 8021
const doaInterval = 250    // Interval the clients should get new doa data in ms

//const remoteServerDefault = 'wss://testmap.krakenrf.com:2096'
const remoteServerDefault = 'wss://map.krakenrf.com:2096'
const settingsJsonPath = '_share/settings.json'

let remoteServer = ''
let lastDoaUpdate = Date.now()
let settingsJson = {};
let settingsChanged = false;
let inRemoteMode = false;
let wsClient;
let wsServer;
let wsPingInterval;

let debugMode = false;

// Check for cmd Parameters, -d = DEBUG mode
if (process.argv[2] && process.argv[2] === '-d') {
  console.log('Debug mode enabled');
  debugMode = true;
}

//load doa settings file
function loadSettingsJson (){
  // check if Settings changed via Hash
  if (settingsJson.center_freq) {
    const oldHash = crypto.createHash('md5').update(JSON.stringify(settingsJson)).digest("hex")
    // load ne Data and ten check if there are changes
    try {
        let rawdata = fs.readFileSync(settingsJsonPath);
        let newSettings = JSON.parse(rawdata);
        const newHash = crypto.createHash('md5').update(JSON.stringify(newSettings)).digest("hex")
        if (newHash != oldHash) {
          console.log("hashes not the same, settings changend locally")
          settingsChanged = true;
        }
        settingsJson = newSettings;
    } catch (error) {}
  } else {
    try {
        console.log("Settings are empty, so initial load")
        settingsChanged = true;
        let rawdata = fs.readFileSync(settingsJsonPath);
        settingsJson = JSON.parse(rawdata)
        remoteServer = settingsJson.mapping_server_url || remoteServerDefault
    } catch (error) {}
  }

  if(debugMode){
    console.log("Loaded Settings from json")
    console.log("Freq: "+settingsJson.center_freq);
    console.log("Mode (Data Format): "+settingsJson.doa_data_format);
    console.log("Name: "+settingsJson.station_id);
    console.log("KrakenPro Key: "+settingsJson.krakenpro_key);
    console.log("Lat: "+settingsJson.latitude);
    console.log("Lon: "+settingsJson.longitude);
  }
}
loadSettingsJson();

function wsTrySend(data){
  try {
    wsClient.send(data)
    return true;
  } catch (error) {
    console.error("Sending data over WS failed, catched error")
    return false;
  }
}

// send Keep allive ping and if needed send Settings
function websocketPing (){
  loadSettingsJson()
  //check if Settings Changed
  if (settingsChanged) {
    if(debugMode) console.log("sending Settings")
    wsTrySend(`{"apikey": "${settingsJson.krakenpro_key}", "type": "settings", "data": ${JSON.stringify(settingsJson)}}`)
    settingsChanged = false
  } else {
    if(debugMode) console.log("send Ping")
    wsTrySend(`{"apikey": "${settingsJson.krakenpro_key}", "type": "ping"}`)
  }
}

function websocketConnect (){
  wsClient = new ws(remoteServer);

  wsClient.onopen = () => {
    // start ping interval
    wsPingInterval = setInterval(websocketPing, 10000);
  }

  wsClient.onclose = (e) => {
    console.error('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
    setTimeout(websocketConnect, 1000);
  };
   
  wsClient.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
   
  wsClient.onmessage = (e) => {
    //check what data we got from Server
    var jsn = JSON.parse(e.data);
    if(jsn.function == 'settings'){
      if(debugMode) console.log("Got new Settings from Server");
      // read settings fresh from file and set new Settings
      loadSettingsJson();
      var newSettings = JSON.parse(jsn.settings);
      newSettings.ext_upd_flag = true;
      fs.writeFileSync(settingsJsonPath, JSON.stringify(newSettings, null, 2));
    } else {
      if(debugMode) console.log(jsn);
    }
  }
}

function checkForRemoteMode (){
  if(debugMode) console.log("Checking for Remote Mode");
  loadSettingsJson()
  // if in remote mode connect to server with websocket
  if(settingsJson.doa_data_format == 'Kraken Pro Remote' && settingsJson.krakenpro_key != '0') {
    if(inRemoteMode == false){
      console.log("Remote mode activated");
      inRemoteMode = true;
      websocketConnect()
    }
    setTimeout(checkForRemoteMode, 10000);
  } else {
    inRemoteMode = false;
    if (wsClient) {
      wsClient.onclose = function () {};
      wsClient.close()  //stop connection to remote Server
      clearInterval(wsPingInterval)
      wsClient = null
    }
    console.log("Remote mode deactivated, checking again in 10s");
    // set 10s timer to poll Settings again and see if they changed to remote mode
    setTimeout(checkForRemoteMode, 10000);
  }
}

checkForRemoteMode()

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
      //console.log(req.body.latitude);
      //console.log(req.body.longitude);
      wsTrySend(`{"apikey": "${settingsJson.krakenpro_key}", "data": ${JSON.stringify(req.body)}}`) 
    } else {
      // sends data to all websocket clients
      /*
      wsServer.clients.forEach(function each(client) {
        if (client.readyState === ws.OPEN) {
          client.send(JSON.stringify(req.body));
        }
      })*/
    } 

  } else {
    if(debugMode) console.log("...");
  }
  res.sendStatus(200)
});

app.post('/prpost', (req, res) => {
    // in remote mode, send data to sdr server backend like the App does
    if (inRemoteMode) {
      // In remote mode set lat/lon
      //req.body.latitude = settingsJson.latitude; 
      //req.body.longitude = settingsJson.longitude;
      //req.body.gpsBearing = settingsJson.heading;
      if(debugMode) console.log(req.body);
      wsTrySend(`{"apikey": "${settingsJson.krakenpro_key}", "type": "pr", "data": ${JSON.stringify(req.body)}}`) 
    } else {
      // sends data to all websocket clients
      /*
      wsServer.clients.forEach(function each(client) {
        if (client.readyState === ws.OPEN) {
          client.send(JSON.stringify(req.body));
        }
      })*/
    } 
  res.sendStatus(200)
});

app.listen(port, () => {
    console.log(`Middleware HTTP Server is listening at http://localhost:${port}, Websocket on ${wsport}`)
})
