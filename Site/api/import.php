<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
        json_response(['ok' => false, 'error' => 'Use POST with a telemetry_file upload.'], 405);
    }

    if (!isset($_FILES['telemetry_file']) || !is_uploaded_file($_FILES['telemetry_file']['tmp_name'])) {
        json_response(['ok' => false, 'error' => 'No file uploaded.'], 400);
    }

    $file = $_FILES['telemetry_file'];
    $originalName = basename((string) $file['name']);
    $contents = file_get_contents($file['tmp_name']);

    if ($contents === false) {
        json_response(['ok' => false, 'error' => 'Could not read uploaded file.'], 400);
    }

    $lines = preg_split('/\r\n|\r|\n/', $contents) ?: [];
    $pdo = db();
    $datasetName = trim((string) ($_POST['dataset_name'] ?? ''));

    if ($datasetName === '') {
        $baseName = pathinfo($originalName, PATHINFO_FILENAME) ?: 'SD import';
        $datasetName = $baseName . ' ' . date('Y-m-d H:i:s');
    }

    $pdo->beginTransaction();

    $stmt = $pdo->prepare(
        "INSERT INTO datasets (name, type, source_filename, notes, is_protected)
         VALUES (?, 'import', ?, 'Imported from SD/ground-station log file.', 0)"
    );
    $stmt->execute([$datasetName, $originalName]);
    $datasetId = (int) $pdo->lastInsertId();

    $read = 0;
    $inserted = 0;
    $bad = 0;

    foreach ($lines as $index => $line) {
        $line = trim((string) $line);

        if ($line === '') {
            continue;
        }

        $read++;
        $record = parse_telemetry_line($line);

        if (!$record['parse_ok']) {
            $bad++;
        }

        insert_telemetry($pdo, $datasetId, $record, $index + 1);
        $inserted++;
    }

    $pdo->commit();

    json_response([
        'ok' => true,
        'dataset_id' => $datasetId,
        'dataset_name' => $datasetName,
        'lines_read' => $read,
        'rows_inserted' => $inserted,
        'bad_rows' => $bad,
    ]);
} catch (Throwable $e) {
    if (isset($pdo) && $pdo instanceof PDO && $pdo->inTransaction()) {
        $pdo->rollBack();
    }

    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
