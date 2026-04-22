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

page_header('Import / Saved Data', 'import');
?>
<section class="hero">
    <h1>Import / Saved Data</h1>
    <p class="muted">Upload an SD log file into a new dataset, then select any dataset to graph it.</p>
    <?php if ($dbError): ?>
        <p class="message error"><?= htmlspecialchars($dbError) ?></p>
    <?php else: ?>
        <p id="message" class="message">Loading datasets...</p>
    <?php endif; ?>
</section>

<?php if (!$dbError): ?>
<section class="panel">
    <h2>Import SD file</h2>
    <form id="importForm">
        <div class="toolbar">
            <input type="file" name="telemetry_file" accept=".txt,.log,.csv" required>
            <input type="text" name="dataset_name" placeholder="Dataset name (optional)">
            <button type="submit">Import</button>
        </div>
    </form>
</section>

<section class="panel">
    <h2>Datasets</h2>
    <div class="toolbar">
        <select id="datasetSelect"></select>
        <button id="copyLive" type="button">Copy live dataset</button>
        <button id="deleteDataset" class="danger" type="button">Delete selected</button>
        <button id="clearImports" class="danger" type="button">Clear saved datasets</button>
        <label class="toggle-option">
            <input id="rawToggle" type="checkbox">
            <span>Raw values</span>
        </label>
        <span id="savedStats" class="muted"></span>
    </div>
</section>

<div id="charts"></div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>window.Chart || document.write('<script src="assets/vendor/chart.umd.min.js"><\/script>');</script>
<script src="assets/js/charts.js"></script>
<script src="assets/js/import.js"></script>
<?php endif; ?>
<?php
page_footer();
