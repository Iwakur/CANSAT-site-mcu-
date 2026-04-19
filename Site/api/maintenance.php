<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $pdo = db();
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

    if ($method !== 'POST') {
        json_response(['ok' => false, 'error' => 'POST required.'], 405);
    }

    $action = (string) ($_POST['action'] ?? '');

    if ($action === 'clear_logs') {
        $pdo->exec('DELETE FROM logs');
        json_response(['ok' => true, 'message' => 'Logs cleared.']);
    }

    if ($action === 'clear_imports') {
        $pdo->exec("DELETE FROM datasets WHERE type <> 'live' AND is_protected = 0");
        json_response(['ok' => true, 'message' => 'Imported datasets cleared.']);
    }

    if ($action === 'clear_live') {
        $liveId = ensure_live_dataset($pdo);
        $stmt = $pdo->prepare('DELETE FROM telemetry WHERE dataset_id = ?');
        $stmt->execute([$liveId]);
        json_response(['ok' => true, 'message' => 'Live telemetry cleared.']);
    }

    if ($action === 'renew_database') {
        $pdo->beginTransaction();
        try {
            $pdo->exec('DELETE FROM logs');
            $pdo->exec('DELETE FROM telemetry');
            $pdo->exec("DELETE FROM datasets WHERE type <> 'live' OR is_protected = 0");
            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }

        ensure_live_dataset($pdo);
        json_response(['ok' => true, 'message' => 'Database renewed with a clean Live dataset.']);
    }

    json_response(['ok' => false, 'error' => 'Unknown action.'], 400);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
