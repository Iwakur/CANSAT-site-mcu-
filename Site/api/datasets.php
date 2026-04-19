<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $pdo = db();
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

    if ($method === 'GET') {
        $stmt = $pdo->query(
            "SELECT d.*,
                    COUNT(t.id) AS row_count,
                    MAX(t.received_at) AS last_received_at
             FROM datasets d
             LEFT JOIN telemetry t ON t.dataset_id = d.id
             GROUP BY d.id
             ORDER BY d.is_protected DESC, d.created_at DESC"
        );
        json_response(['ok' => true, 'datasets' => $stmt->fetchAll()]);
    }

    $action = (string) ($_POST['action'] ?? '');
    $datasetId = (int) ($_POST['dataset_id'] ?? 0);

    if ($action === 'delete') {
        $stmt = $pdo->prepare('SELECT * FROM datasets WHERE id = ?');
        $stmt->execute([$datasetId]);
        $dataset = $stmt->fetch();

        if (!$dataset) {
            json_response(['ok' => false, 'error' => 'Dataset not found.'], 404);
        }

        if ((int) $dataset['is_protected'] === 1 || $dataset['type'] === 'live') {
            json_response(['ok' => false, 'error' => 'The Live dataset cannot be deleted.'], 400);
        }

        $pdo->prepare('DELETE FROM datasets WHERE id = ?')->execute([$datasetId]);
        json_response(['ok' => true]);
    }

    if ($action === 'clear_live') {
        $liveId = ensure_live_dataset($pdo);
        $pdo->prepare('DELETE FROM telemetry WHERE dataset_id = ?')->execute([$liveId]);
        json_response(['ok' => true]);
    }

    json_response(['ok' => false, 'error' => 'Unknown action.'], 400);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
