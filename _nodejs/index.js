// This is a Websocket server that is a middleware to interface wth the new Krakensdr app and future things

const express = require('express')
const ws = require('ws');

const app = express()
const port = 8042
const wsport = 8021
const doaInterval = 1000    // Interval the clients should get new doa data in ms

var lastDoaUpdate = Date.now()

// Websocket that sends incomming Data to App

const wsServer = new ws.Server({ noServer: true });
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

app.use(express.json())

app.get('/', (req, res) => {
    res.send('Hi, this is the KrakenSDR middleware server :)')
})

app.post('/doapost', (req, res) => {
    if(Date.now() - lastDoaUpdate > doaInterval){
      console.log(req.body);
      lastDoaUpdate = Date.now()
      // TODO: send data to all websocket clients
      wsServer.clients.forEach(function each(client) {
        if (client.readyState === ws.OPEN) {
          client.send(JSON.stringify(req.body));
        }
      })
    } else {
      console.log("...");
    }
    res.sendStatus(200)
  });

app.listen(port, () => {
    console.log(`Middleware HTTP Server is listening at http://localhost:${port}, Websocket on ${wsport}`)
})
