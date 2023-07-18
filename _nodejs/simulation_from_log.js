const axios = require('axios');

const fs = require('fs');
const { syncBuiltinESMExports } = require('module');

var logArray = [];
var logIndex = 0;
try {
  const data = fs.readFileSync('redoubt360.csv', 'UTF-8');
  const lines = data.split(/\r?\n/);

  lines.forEach(line => {
    var logData = line.split(',');
    
    var logEntry = {
      tStamp: parseInt(logData[0]),
      latitude: parseFloat(logData[1]),
      longitude: parseFloat(logData[2]),
      gpsBearing: parseFloat(logData[3]),
      radioBearing: parseFloat(logData[5]),
      conf: parseInt(logData[6]),
      power: parseFloat(logData[7]),
      freq: parseInt(logData[8]),
      antType: logData[9],
      latency: parseInt(logData[10]),
      doaArray: logData.slice(12, logData.length-1).map(x => parseFloat(x))+",", 
    };
/*
    // new Format
    var logEntry = {
      tStamp: parseInt(logData[0]),
      latitude: parseFloat(logData[8]),
      longitude: parseFloat(logData[9]),
      gpsBearing: parseFloat(logData[10]),
      radioBearing: parseFloat(logData[1]),
      conf: parseFloat(logData[2]),
      power: parseFloat(logData[3]),
      freq: parseInt(logData[4]),
      antType: logData[5],
      latency: parseInt(logData[6]),
      doaArray: logData.slice(17, logData.length).map(x => parseFloat(x))+",",  
    };*/
    //console.log(logEntry.doaArray);
    logArray.push(logEntry);
  });

} catch (err) {
  console.error(err);
}

setInterval(() => {
if (logIndex <= logArray.length) {
    var logEntry = logArray[logIndex];
    logEntry.tStamp = Date.now();

    console.log("Sending Data as kraken: "+logEntry)
    axios.post('http://localhost:8042/doapost', logEntry)
        .then(function (response) {
            //console.log(response);
        })
        .catch(function (error) {
            console.log(error);
        });
    logIndex++;
}
}, 1000);