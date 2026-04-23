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

// ===== ROUTE DATA =====
app.get('/data', (req, res) => {

    const {
        // Quaternion (prioritaire)
        q1, q2, q3, q4,

        // Ancien fallback (Euler)
        x, y, z,

        altitude,
        model,
        scale
    } = req.query;

    // ===== GESTION QUATERNION =====
    let Q1 = safeFloat(q1);
    let Q2 = safeFloat(q2);
    let Q3 = safeFloat(q3);
    let Q4 = safeFloat(q4);

    // 🔁 Fallback si jamais tu envoies encore des angles
    if (Q1 === undefined && x !== undefined) {
        console.log("⚠️ Mode fallback Euler utilisé");

        const degToRad = (deg) => deg * Math.PI / 180;

        const roll = degToRad(safeFloat(x) || 0);
        const pitch = degToRad(safeFloat(y) || 0);
        const yaw = degToRad(safeFloat(z) || 0);

        // Conversion Euler → Quaternion
        const cy = Math.cos(yaw * 0.5);
        const sy = Math.sin(yaw * 0.5);
        const cp = Math.cos(pitch * 0.5);
        const sp = Math.sin(pitch * 0.5);
        const cr = Math.cos(roll * 0.5);
        const sr = Math.sin(roll * 0.5);

        Q1 = cr * cp * cy + sr * sp * sy; // w
        Q2 = sr * cp * cy - cr * sp * sy; // x
        Q3 = cr * sp * cy + sr * cp * sy; // y
        Q4 = cr * cp * sy - sr * sp * cy; // z
    }

    // ===== NORMALISATION (important IMU) =====
    if (Q1 !== undefined) {
        const norm = Math.sqrt(Q1*Q1 + Q2*Q2 + Q3*Q3 + Q4*Q4);
        if (norm > 0) {
            Q1 /= norm;
            Q2 /= norm;
            Q3 /= norm;
            Q4 /= norm;
        }
    }

    // ===== DATA FINAL =====
    const data = JSON.stringify({
        q1: Q1,
        q2: Q2,
        q3: Q3,
        q4: Q4,

        altitude: safeFloat(altitude),
        scale: safeFloat(scale) ?? 1,
        model: model || null,

        time: Date.now()
    });

    console.log("📡 Envoi :", data);

    // ===== BROADCAST =====
    clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(data);
        }
    });

    res.send("OK");
});

// ===== ROUTE TEST =====
app.get('/', (req, res) => {
    res.send("🚀 Serveur WebSocket actif");
});