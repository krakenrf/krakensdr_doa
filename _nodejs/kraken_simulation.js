// This file simulates one or multiple Krakens sending simulated Data to the Middleware for testing

const axios = require('axios');

const ARRAY_LENGTH = 360
const MAIN_DIRECTION = 360 - 90
var doaArr = Array.from(Array(ARRAY_LENGTH)).map(x=>Math.random() * 10)

var dirMin = MAIN_DIRECTION - 10

for (let i = 0; i < 30; i++) {
    doaArr[dirMin+i] = 15+(i/10)
}

//console.log(doaArr)
var logEntry = {
    tStamp: Date.now(),
    latitude: 50.8220873,
    longitude: 6.9190049,
    gpsBearing: 0,
    radioBearing: MAIN_DIRECTION,
    conf: 3,
    power: -29.4,
    freq: 394314000,
    antType: 'UCA',
    latency: 2,
    doaArray: doaArr.map(x => parseFloat(x))+",", 
};

axios.post('http://localhost:8042/doapost', logEntry)
.then(function (response) {
    //console.log(response);
})
.catch(function (error) {
    console.log(error);
});