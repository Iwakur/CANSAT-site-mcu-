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

page_header('Logs', 'logs');
?>
<section class="hero">
    <h1>Ground station logs</h1>
    <p class="muted">Ground station status, radio, WiFi, SD, and HTTP events, newest first.</p>
    <?php if ($dbError): ?>
        <p class="message error"><?= htmlspecialchars($dbError) ?></p>
    <?php else: ?>
        <div class="toolbar">
            <input id="search" type="search" placeholder="Filter logs">
            <button id="refreshLogs" type="button">Refresh</button>
            <button id="clearLogs" class="danger" type="button">Clear logs</button>
        </div>
        <p id="message" class="message">Loading logs...</p>
    <?php endif; ?>
</section>

<pre id="logOutput" class="log-output"></pre>

<?php if (!$dbError): ?>
<script src="assets/js/logs.js"></script>
<?php endif; ?>
<?php
page_footer();
