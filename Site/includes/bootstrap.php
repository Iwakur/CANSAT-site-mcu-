<?php
declare(strict_types=1);

require_once __DIR__ . DIRECTORY_SEPARATOR . 'db.php';
require_once __DIR__ . DIRECTORY_SEPARATOR . 'telemetry_parser.php';

function json_response(array $payload, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($payload);
    exit;
}

function app_url(string $path = ''): string
{
    $base = rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/\\');
    $base = preg_replace('#/(api)$#', '', $base);

    return $base . '/' . ltrim($path, '/');
}
