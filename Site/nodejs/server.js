const express = require('express');
const WebSocket = require('ws');

const app = express();
const port = 3000;

const server = app.listen(port, () => {
    console.log("Serveur lancé sur http://localhost:" + port);
});

const wss = new WebSocket.Server({ server });

let clients = [];

wss.on('connection', (ws) => {
    console.log("Client connecté");
    clients.push(ws);

    ws.on('close', () => {
        clients = clients.filter(c => c !== ws);
    });
});

app.get('/data', (req, res) => {
    const { x, y, z, altitude, model, scale } = req.query;

    console.log("Reçu :", x, y, z, altitude, model, scale);

    const data = JSON.stringify({
        x: parseFloat(x),
        y: parseFloat(y),
        z: parseFloat(z),
		scale: parseFloat(scale),
        altitude: parseFloat(altitude),
		model : model,
        time: Date.now()
    });

    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(data);
        }
    });

    res.send("OK");
});