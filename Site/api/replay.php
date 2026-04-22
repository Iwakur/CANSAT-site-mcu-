<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $pdo = db();
    $datasetId = isset($_GET['dataset_id']) ? (int) $_GET['dataset_id'] : ensure_live_dataset($pdo);
    $latest = isset($_GET['latest']) && (string) $_GET['latest'] !== '0';
    $requestedIndex = max(0, (int) ($_GET['index'] ?? 0));

    $datasetStmt = $pdo->prepare('SELECT * FROM datasets WHERE id = ?');
    $datasetStmt->execute([$datasetId]);
    $dataset = $datasetStmt->fetch();

    if (!$dataset) {
        json_response(['ok' => false, 'error' => 'Dataset not found.'], 404);
    }

    $metaStmt = $pdo->prepare(
        "SELECT COUNT(*) AS row_count, MAX(id) AS max_id, MAX(received_at) AS last_received_at
         FROM telemetry
         WHERE dataset_id = ?"
    );
    $metaStmt->execute([$datasetId]);
    $meta = $metaStmt->fetch() ?: ['row_count' => 0, 'max_id' => null, 'last_received_at' => null];
    $rowCount = (int) $meta['row_count'];

    $index = 0;
    $row = null;

    if ($rowCount > 0) {
        $index = $latest ? $rowCount - 1 : min($requestedIndex, $rowCount - 1);
        $columns = implode(', ', [
            'id', 'dataset_id', 'received_at', 'line_number', 'raw_line', 'mcu_sample_id', 'device_time',
            'tmp36_temp', 'tmp36_voltage', 'tmp36_raw',
            'bme_temp', 'bme_pressure', 'bme_humidity', 'bme_gas', 'bme_gas_valid', 'bme_altitude',
            'ax', 'ay', 'az', 'gx', 'gy', 'gz', 'pitch', 'roll',
            'mag_x', 'mag_y', 'mag_z', 'heading',
            'gps_fix', 'gps_satellites', 'gps_lat', 'gps_lon', 'gps_altitude',
            'gps_hdop', 'gps_speed_kmh', 'gps_course_deg', 'gps_vertical_speed_ms',
            'parse_ok', 'parse_message',
        ]);

        $rowStmt = $pdo->prepare(
            "SELECT {$columns}
             FROM telemetry
             WHERE dataset_id = ?
             ORDER BY id ASC
             LIMIT 1 OFFSET {$index}"
        );
        $rowStmt->execute([$datasetId]);
        $row = $rowStmt->fetch() ?: null;
    }

    json_response([
        'ok' => true,
        'dataset' => $dataset,
        'meta' => [
            'row_count' => $rowCount,
            'max_id' => $meta['max_id'] === null ? null : (int) $meta['max_id'],
            'last_received_at' => $meta['last_received_at'],
        ],
        'index' => $index,
        'row' => $row,
    ]);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
