<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $pdo = db();
    $search = trim((string) ($_GET['q'] ?? ''));
    $limit = max(1, min(5000, (int) ($_GET['limit'] ?? 1000)));

    if ($search !== '') {
        $stmt = $pdo->prepare(
            "SELECT * FROM logs
             WHERE raw_line LIKE ?
             ORDER BY id DESC
             LIMIT {$limit}"
        );
        $stmt->execute(['%' . $search . '%']);
    } else {
        $stmt = $pdo->query("SELECT * FROM logs ORDER BY id DESC LIMIT {$limit}");
    }

    json_response(['ok' => true, 'logs' => $stmt->fetchAll()]);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
