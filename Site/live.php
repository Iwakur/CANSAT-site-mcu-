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

page_header('Live', 'live');
?>
<section class="hero">
    <h1>Live telemetry</h1>
    <p class="muted">Graphs refresh every second from the Live dataset.</p>
    <?php if ($dbError): ?>
        <p class="message error"><?= htmlspecialchars($dbError) ?></p>
    <?php else: ?>
        <p id="message" class="message">Loading live data...</p>
    <?php endif; ?>
    <div class="toolbar">
        <button id="clearLive" class="danger" type="button">Clear live data</button>
        <label class="toggle-option">
            <input id="rawToggle" type="checkbox">
            <span>Raw values</span>
        </label>
        <span id="liveStats" class="muted"></span>
    </div>
</section>

<div id="charts"></div>

<?php if (!$dbError): ?>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>window.Chart || document.write('<script src="assets/vendor/chart.umd.min.js"><\/script>');</script>
<script src="assets/js/charts.js"></script>
<script src="assets/js/live.js"></script>
<?php endif; ?>
<?php
page_footer();
