<?php
declare(strict_types=1);

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'includes' . DIRECTORY_SEPARATOR . 'bootstrap.php';

try {
    $line = trim((string) ($_GET['line'] ?? $_POST['line'] ?? $_GET['message'] ?? $_POST['message'] ?? ''));
    $type = strtolower(trim((string) ($_GET['type'] ?? $_POST['type'] ?? 'telemetry')));
    $source = trim((string) ($_GET['source'] ?? $_POST['source'] ?? 'ground_station'));

    if ($line === '') {
        http_response_code(400);
        header('Content-Type: text/plain; charset=utf-8');
        echo 'ERROR missing line/message';
        exit;
    }

    if ($source === '') {
        $source = 'ground_station';
    }
    $source = substr(preg_replace('/[^A-Za-z0-9_.-]+/', '_', $source), 0, 40);

    $pdo = db();

    if ($type === 'log') {
        insert_log($pdo, $line, $source);
    } else {
        $liveId = ensure_live_dataset($pdo);
        $record = parse_telemetry_line($line);
        insert_telemetry($pdo, $liveId, $record);
    }

    header('Content-Type: text/plain; charset=utf-8');
    echo 'OK';
} catch (Throwable $e) {
    http_response_code(500);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'ERROR ' . $e->getMessage();
}
