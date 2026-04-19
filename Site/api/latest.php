<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $pdo = db();
    $datasetId = isset($_GET['dataset_id']) ? (int) $_GET['dataset_id'] : ensure_live_dataset($pdo);
    $limit = max(1, min(2000, (int) ($_GET['limit'] ?? 500)));

    $datasetStmt = $pdo->prepare('SELECT * FROM datasets WHERE id = ?');
    $datasetStmt->execute([$datasetId]);
    $dataset = $datasetStmt->fetch();

    if (!$dataset) {
        json_response(['ok' => false, 'error' => 'Dataset not found.'], 404);
    }

    $stmt = $pdo->prepare(
        "SELECT *
         FROM (
            SELECT * FROM telemetry
            WHERE dataset_id = ?
            ORDER BY id DESC
            LIMIT {$limit}
         ) recent
         ORDER BY id ASC"
    );
    $stmt->execute([$datasetId]);
    $rows = $stmt->fetchAll();

    $metaStmt = $pdo->prepare(
        "SELECT COUNT(*) AS row_count, MAX(id) AS max_id, MAX(received_at) AS last_received_at
         FROM telemetry
         WHERE dataset_id = ?"
    );
    $metaStmt->execute([$datasetId]);
    $meta = $metaStmt->fetch() ?: ['row_count' => 0, 'max_id' => null, 'last_received_at' => null];

    json_response([
        'ok' => true,
        'dataset' => $dataset,
        'meta' => [
            'row_count' => (int) $meta['row_count'],
            'max_id' => $meta['max_id'] === null ? null : (int) $meta['max_id'],
            'last_received_at' => $meta['last_received_at'],
        ],
        'rows' => $rows,
    ]);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
