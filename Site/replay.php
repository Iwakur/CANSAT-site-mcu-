<?php
declare(strict_types=1);

require_once __DIR__ . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'layout.php';

try {
    db();
    $dbError = null;
} catch (Throwable $e) {
    $dbError = $e->getMessage();
}

page_header('Replay', 'replay');
?>
<section class="hero">
    <h1>Replay</h1>
    <p class="muted">Dataset playback with one current telemetry sample and 3D attitude state.</p>
    <?php if ($dbError): ?>
        <p class="message error"><?= htmlspecialchars($dbError) ?></p>
    <?php else: ?>
        <p id="replayMessage" class="message">Loading replay data...</p>
    <?php endif; ?>
</section>

<?php if (!$dbError): ?>
<section class="panel replay-controls">
    <div class="toolbar">
        <label class="control-field" for="replayDataset">
            <span>Dataset</span>
            <select id="replayDataset"></select>
        </label>
        <button id="replayRefresh" type="button">Refresh</button>
        <label class="toggle-option">
            <input id="followLive" type="checkbox">
            <span>Follow Live</span>
        </label>
        <span id="replayStatus" class="muted"></span>
    </div>
    <div class="replay-timeline">
        <input id="replaySlider" type="range" min="0" max="0" value="0" disabled>
        <div class="replay-timeline-meta">
            <span id="replayPosition">0 / 0</span>
            <span id="replayTime">--</span>
        </div>
    </div>
</section>

<section class="replay-stage">
    <div id="replayViewport" class="replay-viewport" aria-label="3D CanSat attitude view"></div>
    <aside class="replay-hud" aria-live="polite">
        <div class="replay-hud-header">
            <span>Current sample</span>
            <strong id="hudSample">--</strong>
        </div>
        <div class="replay-hud-grid">
            <span>Dataset</span><strong id="hudDataset">--</strong>
            <span>Device time</span><strong id="hudTime">--</strong>
            <span>Received</span><strong id="hudReceived">--</strong>
            <span>Row</span><strong id="hudRow">--</strong>
            <span>Parse</span><strong id="hudParse">--</strong>
            <span>GPS fix</span><strong id="hudGpsFix">--</strong>
            <span>Satellites</span><strong id="hudGpsSatellites">--</strong>
            <span>GPS lat/lon</span><strong id="hudGpsPosition">--</strong>
            <span>GPS altitude</span><strong id="hudGpsAltitude">--</strong>
            <span>BME altitude</span><strong id="hudBmeAltitude">--</strong>
            <span>TMP36</span><strong id="hudTmp36">--</strong>
            <span>BME temp</span><strong id="hudBmeTemp">--</strong>
            <span>Pressure</span><strong id="hudPressure">--</strong>
            <span>Humidity</span><strong id="hudHumidity">--</strong>
            <span>Gas</span><strong id="hudGas">--</strong>
            <span>Attitude</span><strong id="hudAttitude">--</strong>
            <span>Acceleration</span><strong id="hudAccel">--</strong>
            <span>Gyroscope</span><strong id="hudGyro">--</strong>
            <span>GPS motion</span><strong id="hudGpsMotion">--</strong>
        </div>
        <pre id="hudRawLine" class="replay-raw-line">--</pre>
    </aside>
</section>

<script src="https://cdn.jsdelivr.net/npm/three@0.128/build/three.min.js"></script>
<script>window.THREE || document.write('<script src="assets/vendor/three.min.js"><\/script>');</script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128/examples/js/loaders/GLTFLoader.js"></script>
<script>THREE.GLTFLoader || document.write('<script src="assets/vendor/GLTFLoader.js"><\/script>');</script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128/examples/js/controls/OrbitControls.js"></script>
<script>THREE.OrbitControls || document.write('<script src="assets/vendor/OrbitControls.js"><\/script>');</script>
<script src="assets/js/replay.js"></script>
<?php endif; ?>
<?php
page_footer();
