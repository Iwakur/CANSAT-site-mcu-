const express = require('express');
const WebSocket = require('ws');

const app = express();
const port = 3000;

// ===== SERVER HTTP =====
const server = app.listen(port, () => {
    console.log("Serveur lancé sur http://localhost:" + port);
});

// ===== WEBSOCKET =====
const wss = new WebSocket.Server({ server });

let clients = [];

wss.on('connection', (ws) => {
    console.log("Client connecté");
    clients.push(ws);

    ws.on('close', () => {
        console.log("Client déconnecté");
        clients = clients.filter(c => c !== ws);
    });
});

// ===== UTILS =====
function safeFloat(v) {
    const n = parseFloat(v);
    return isNaN(n) ? undefined : n;
}

const dgram = require('dgram');
const udpServer = dgram.createSocket('udp4');

udpServer.on('message', (msg, rinfo) => {
    try {
        const text = msg.toString().trim();
        console.log("📥 UDP reçu :", text);

        // Format attendu : "q1,q2,q3,q4"
        const parts = text.split(',');

        let Q1 = safeFloat(parts[0]);
        let Q2 = safeFloat(parts[1]);
        let Q3 = safeFloat(parts[2]);
        let Q4 = safeFloat(parts[3]);

        // Normalisation
        if (Q1 !== undefined) {
            const norm = Math.sqrt(Q1*Q1 + Q2*Q2 + Q3*Q3 + Q4*Q4);
            if (norm > 0) {
                Q1 /= norm;
                Q2 /= norm;
                Q3 /= norm;
                Q4 /= norm;
            }
        }

        const data = JSON.stringify({
            q1: Q1,
            q2: Q2,
            q3: Q3,
            q4: Q4,
            time: Date.now()
        });

        console.log("📡 Broadcast UDP :", data);

        // Envoi WebSocket
        clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(data);
            }
        });

    } catch (err) {
        console.log("Erreur UDP :", err);
    }
});

// Port UDP (le même que ton Pico)
udpServer.bind(3000, () => {
    console.log("📡 Serveur UDP actif sur port 3000");
});