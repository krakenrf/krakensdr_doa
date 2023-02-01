const axios = require('axios');

setInterval(() => {

  var rb = Math.floor(Math.random() * 49) + 1;
  var prData = {"rb": rb};

  console.log("Sending PR Data as kraken: "+prData.rb)
  axios.post('http://localhost:8042/prpost', prData)
      .then(function (response) {
          //console.log(response);
      })
      .catch(function (error) {
          console.log(error);
      });
}, 5000);