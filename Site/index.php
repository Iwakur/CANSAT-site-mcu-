<?php
declare(strict_types=1);

require_once __DIR__ . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'layout.php';

$dbOk = true;
$dbMessage = 'Database ready.';

try {
    $pdo = db();
    $liveId = ensure_live_dataset($pdo);
} catch (Throwable $e) {
    $dbOk = false;
    $dbMessage = $e->getMessage();
}

page_header('Home', 'home');
?>
<section class="hero hero-command">
    <p class="eyebrow">Mission control</p>
    <h1>Starships[CanSat]</h1>
    <p class="muted">This PC receives ground-station telemetry, stores it in local MySQL, and displays logs, live graphs, and imported SD files.</p>
    <p class="message <?= $dbOk ? 'ok' : 'error' ?>"><?= htmlspecialchars($dbMessage) ?></p>
</section>

<section class="grid">
    <a class="stat starship-card" href="live.php">
        <span class="ship-tag">Telemetry</span>
        <strong>Live</strong>
        Ground-station data graphed from the protected Live dataset.
    </a>
    <a class="stat starship-card" href="logs.php">
        <span class="ship-tag">Ground station</span>
        <strong>Logs</strong>
        Raw readable telemetry lines, newest first.
    </a>
    <a class="stat starship-card" href="import.php">
        <span class="ship-tag">Saved data</span>
        <strong>Import / Saved Data</strong>
        Upload SD files, create datasets, compare saved flights.
    </a>
</section>

<?php if ($dbOk): ?>
<section class="panel maintenance-panel">
    <div>
        <p class="eyebrow">Renew station</p>
        <h2>Maintenance controls</h2>
        <p class="muted">Clear temporary mission data when you want a clean launch board.</p>
    </div>
    <div class="toolbar">
        <button type="button" data-maintenance-action="clear_logs">Clear logs</button>
        <button type="button" data-maintenance-action="clear_live">Clear live data</button>
        <button type="button" data-maintenance-action="clear_imports" class="danger">Clear saved datasets</button>
        <button type="button" data-maintenance-action="renew_database" class="danger">Renew database</button>
    </div>
    <p id="maintenanceMessage" class="message">Ready.</p>
</section>
<?php endif; ?>

<section class="panel">
    <h2>Receiver URL</h2>
    <p class="muted">Use one of these in the ground station, depending on how you run PHP.</p>
    <pre class="log-output">Laragon Apache:
http://PC_IP/GitHub/CANSAT/Site/api/receive.php

PHP dev server from Site:
http://PC_IP:8000/api/receive.php</pre>
</section>
<?php if ($dbOk): ?>
<script src="assets/js/maintenance.js"></script>
<?php endif; ?>
<?php
page_footer();
