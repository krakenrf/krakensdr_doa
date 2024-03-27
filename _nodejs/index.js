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
const statusJsonPath = '_share/status.json'
const positionJsonPath = '_share/position.json'

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

app.get('/getSettings', (req, res) => {
    let rawdata = fs.readFileSync(settingsJsonPath, "utf8");
    let settingsJson = JSON.parse(rawdata);
    res.setHeader('content-type', 'application/json');
    res.send(settingsJson);
})

app.post('/updateSettings', (req, res) => {
    const freq = Number(req.query.freq);
    const gain = Number(req.query.gain);
    const array = req.query.array;
    const spacing = Number(req.query.spacing);

    let rawdata = fs.readFileSync(settingsJsonPath, "utf8");
    let settingsObj = JSON.parse(rawdata);
    settingsObj.center_freq = freq;
    settingsObj.uniform_gain = gain;
    settingsObj.ant_arrangement = array;
    settingsObj.ant_spacing_meters = spacing;

    let settingsString = JSON.stringify(settingsObj);
    fs.writeFileSync(
        settingsJsonPath,
        settingsString,
        {encoding: "utf8", flag: "w"}
    );

    let editedSettings = fs.readFileSync(settingsJsonPath, "utf8");
    let editedJson = JSON.parse(editedSettings);
    let success = (editedJson.center_freq===freq
        && editedJson.uniform_gain===gain
        && editedJson.ant_arrangement===array
        && editedJson.ant_spacing_meters===spacing
    );

    res.setHeader('content-type', 'application/json');
    res.send({"success": success});
})

function staticGPSCase(requestQuery){

    const latitude = requestQuery.latitude;
    const longitude = requestQuery.longitude;
    const heading = requestQuery.heading;

    let rawdata = fs.readFileSync(settingsJsonPath, "utf8");
    let settingsObj = JSON.parse(rawdata);
    settingsObj.location_source = "Static";
    settingsObj.latitude = latitude;
    settingsObj.longitude = longitude;
    settingsObj.heading = heading;

    let settingsString = JSON.stringify(settingsObj);
    fs.writeFileSync(
        settingsJsonPath,
        settingsString,
        {encoding: "utf8", flag: "w"}
    );

    let editedSettings = fs.readFileSync(settingsJsonPath, "utf8");
    let editedJson = JSON.parse(editedSettings);
    let success = (editedJson.location_source==="Static"
        && editedJson.latitude===latitude
        && editedJson.longitude===longitude
        && editedJson.heading===heading
    );

    return success;
}

function setGPSCase(locationSource){

    let rawdata = fs.readFileSync(settingsJsonPath, "utf8");
    let settingsObj = JSON.parse(rawdata);
    settingsObj.location_source = locationSource;
    let settingsString = JSON.stringify(settingsObj);
    fs.writeFileSync(
        settingsJsonPath,
        settingsString,
        {encoding: "utf8", flag: "w"}
    );

    let editedSettings = fs.readFileSync(settingsJsonPath, "utf8");
    let editedJson = JSON.parse(editedSettings);
    let success = (editedJson.location_source===locationSource);

    return success;
}

function setGPSFixedHeading(heading){

    let rawdata = fs.readFileSync(settingsJsonPath, "utf8");
    let settingsObj = JSON.parse(rawdata);

    settingsObj.location_source = "gpsd";
    settingsObj.gps_fixed_heading = true;
    settingsObj.heading = heading;

    let settingsString = JSON.stringify(settingsObj);
    fs.writeFileSync(
        settingsJsonPath,
        settingsString,
        {encoding: "utf8", flag: "w"}
    );

    let editedSettings = fs.readFileSync(settingsJsonPath, "utf8");
    let editedJson = JSON.parse(editedSettings);
    let success = (editedJson.location_source==="gpsd"
        && editedJson.gps_fixed_heading === true
        && editedJson.heading === heading);

    return success;
}

app.get("/getStatus", (req, res) => {
    let rawdata = fs.readFileSync(statusJsonPath, "utf8");
    let statusJson = JSON.parse(rawdata);
    res.setHeader('content-type', 'application/json');
    res.send(statusJson);
})

app.get("/getPosition", (req, res) => {
    let rawdata = fs.readFileSync(positionJsonPath, "utf8");
    let positionJson = JSON.parse(rawdata);
    res.setHeader('content-type', 'application/json');
    res.send(positionJson);
})


app.post("/enableGPS", (req, res) => {
    let locationSource = req.query.locationSource;
    let success = false;
    if (locationSource === "Static"){
        success = staticGPSCase(req.query);
    } else if (locationSource === "USB"){
        if (req.query.fixedHeading){
            success = setGPSFixedHeading(req.query.heading);
        }else{
            success = setGPSCase("gpsd")
        }
    } else if (locationSource === "None"){
        success = setGPSCase("None")
    } else {
        setGPSCase("None")
        success = false;
    }

    res.setHeader('content-type', 'application/json');
    res.send({"success": success});
})

/*
const gpsd = require('node-gpsd')
let gpsdDaemon = new gpsd.Daemon();
let listener = new gpsd.Listener();
let lastDataPacket = {};
const dataAgeThreshold = 2; // seconds

function convertCoordinatesMinutesToDegrees(longitude, latitude){
    let latDeg = Number(longitude.slice(0, 2));
    const latMins = Number(longitude.slice(2));
    latDeg += (latMins/60);

    let lonDeg = Number(latitude.slice(0, 3));
    const lonMins = Number(latitude.slice(3));
    latDeg += (lonMins/60);

    return {latitude: latDeg, longitude: lonDeg};
}

app.get("/enableGPSD", (req, res) => {
    gpsdDaemon.start(function() {
        console.log('GPSD started');
    });
    listener.connect(function() {
        console.log('GPSD listener connected');
    });
    listener.on("TPV", function(data){
        let unixSecs = Date.parse(data.time)/1000;
        let latDeg, lonDeg;
        ({latitude: latDeg, longitude: lonDeg} = convertCoordinatesMinutesToDegrees(Number(data.lon), Number(data.lat)));
        lastDataPacket = {
            timestamp: unixSecs,
            latitude: latDeg,
            longitude: lonDeg,
            latitudeError: Number(data.epy),
            longitudeError: Number(data.epx),
            heading: Number(data.track),
            headingError: Number(data.epd)};
    });
    listener.watch();
    res.setHeader('content-type', 'application/json');
    res.send({listenerConnected: listener.isConnected()});
})

app.get("/disableGPSD", (req, res) => {
    listener.unwatch();
    listener.disconnect(function() {
        console.log('GPSD listener disconnected');
    });
    gpsdDaemon.stop(function() {
        console.log('GPSD stopped');
    });
    res.setHeader('content-type', 'application/json');
    res.send({listenerConnected: listener.isConnected()});
})

app.get("/getGPSDPosition", (req, res) => {
    const listenerConnected = listener.isConnected();
    const ageOfData = Math.abs(Date.now()/1000 - lastDataPacket.timestamp);
    if (listenerConnected && ageOfData<dataAgeThreshold){
        res.setHeader('content-type', 'application/json');
        res.send({
            listenerConnected: listenerConnected,
            ageOfData: ageOfData,
            dataAgeThreshold: dataAgeThreshold,
            TPV: lastDataPacket});
    }
})
*/

