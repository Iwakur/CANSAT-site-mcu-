<?php
declare(strict_types=1);

function app_config(): array
{
    static $config = null;

    if ($config === null) {
        $config = require dirname(__DIR__) . DIRECTORY_SEPARATOR . 'config.php';
    }

    return $config;
}

function db_name(): string
{
    $name = (string) app_config()['db_name'];

    if (!preg_match('/^[A-Za-z0-9_]+$/', $name)) {
        throw new RuntimeException('Database name may only contain letters, numbers, and underscores.');
    }

    return $name;
}

function db(): PDO
{
    static $pdo = null;

    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $config = app_config();
    $charset = $config['db_charset'];
    $serverDsn = "mysql:host={$config['db_host']};charset={$charset}";
    $database = db_name();

    $server = new PDO($serverDsn, $config['db_user'], $config['db_pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $server->exec("CREATE DATABASE IF NOT EXISTS `{$database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

    $dsn = "mysql:host={$config['db_host']};dbname={$database};charset={$charset}";
    $pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);

    ensure_schema($pdo);

    return $pdo;
}

function ensure_schema(PDO $pdo): void
{
    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS datasets (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            type VARCHAR(20) NOT NULL DEFAULT 'import',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source_filename VARCHAR(255) NULL,
            notes TEXT NULL,
            is_protected TINYINT(1) NOT NULL DEFAULT 0,
            INDEX idx_type (type),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    );

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS telemetry (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            dataset_id INT UNSIGNED NOT NULL,
            received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            line_number INT UNSIGNED NULL,
            raw_line TEXT NOT NULL,
            mcu_sample_id INT UNSIGNED NULL,
            device_time VARCHAR(64) NULL,
            tmp36_temp DOUBLE NULL,
            tmp36_voltage DOUBLE NULL,
            tmp36_raw INT NULL,
            bme_temp DOUBLE NULL,
            bme_pressure DOUBLE NULL,
            bme_humidity DOUBLE NULL,
            bme_gas DOUBLE NULL,
            bme_gas_valid TINYINT NULL,
            bme_altitude DOUBLE NULL,
            ax DOUBLE NULL,
            ay DOUBLE NULL,
            az DOUBLE NULL,
            gx DOUBLE NULL,
            gy DOUBLE NULL,
            gz DOUBLE NULL,
            pitch DOUBLE NULL,
            roll DOUBLE NULL,
            mag_x DOUBLE NULL,
            mag_y DOUBLE NULL,
            mag_z DOUBLE NULL,
            heading DOUBLE NULL,
            gps_fix TINYINT NULL,
            gps_satellites INT NULL,
            gps_lat DOUBLE NULL,
            gps_lon DOUBLE NULL,
            gps_altitude DOUBLE NULL,
            gps_hdop DOUBLE NULL,
            gps_speed_kmh DOUBLE NULL,
            gps_course_deg DOUBLE NULL,
            gps_vertical_speed_ms DOUBLE NULL,
            parse_ok TINYINT(1) NOT NULL DEFAULT 0,
            parse_message VARCHAR(255) NULL,
            CONSTRAINT fk_telemetry_dataset
                FOREIGN KEY (dataset_id) REFERENCES datasets(id)
                ON DELETE CASCADE,
            INDEX idx_dataset_id (dataset_id),
            INDEX idx_received_at (received_at),
            INDEX idx_line_number (line_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    );

    ensure_telemetry_column($pdo, 'tmp36_temp', 'DOUBLE NULL');
    ensure_telemetry_column($pdo, 'mcu_sample_id', 'INT UNSIGNED NULL');
    ensure_telemetry_column($pdo, 'tmp36_voltage', 'DOUBLE NULL');
    ensure_telemetry_column($pdo, 'tmp36_raw', 'INT NULL');
    ensure_telemetry_column($pdo, 'bme_gas_valid', 'TINYINT NULL');
    ensure_telemetry_column($pdo, 'gps_hdop', 'DOUBLE NULL');
    ensure_telemetry_column($pdo, 'gps_speed_kmh', 'DOUBLE NULL');
    ensure_telemetry_column($pdo, 'gps_course_deg', 'DOUBLE NULL');
    ensure_telemetry_column($pdo, 'gps_vertical_speed_ms', 'DOUBLE NULL');

    $pdo->exec(
        "CREATE TABLE IF NOT EXISTS logs (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            raw_line TEXT NOT NULL,
            source VARCHAR(40) NOT NULL DEFAULT 'ground',
            INDEX idx_received_at (received_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    );

    ensure_live_dataset($pdo);
}

function ensure_telemetry_column(PDO $pdo, string $column, string $definition): void
{
    $stmt = $pdo->prepare('SHOW COLUMNS FROM telemetry LIKE ?');
    $stmt->execute([$column]);

    if (!$stmt->fetch()) {
        $pdo->exec("ALTER TABLE telemetry ADD COLUMN `{$column}` {$definition}");
    }
}

function ensure_live_dataset(PDO $pdo): int
{
    $stmt = $pdo->prepare("SELECT id FROM datasets WHERE type = 'live' ORDER BY id ASC LIMIT 1");
    $stmt->execute();
    $row = $stmt->fetch();

    if ($row) {
        $pdo->prepare("UPDATE datasets SET name = 'Live', is_protected = 1 WHERE id = ?")->execute([$row['id']]);
        return (int) $row['id'];
    }

    $stmt = $pdo->prepare(
        "INSERT INTO datasets (name, type, source_filename, notes, is_protected)
         VALUES ('Live', 'live', NULL, 'Data received from the ground station.', 1)"
    );
    $stmt->execute();

    return (int) $pdo->lastInsertId();
}

function insert_log(PDO $pdo, string $rawLine, string $source = 'ground'): void
{
    $stmt = $pdo->prepare("INSERT INTO logs (raw_line, source) VALUES (?, ?)");
    $stmt->execute([$rawLine, $source]);
}

function insert_telemetry(PDO $pdo, int $datasetId, array $record, ?int $lineNumber = null): void
{
    $columns = [
        'dataset_id', 'line_number', 'raw_line', 'mcu_sample_id', 'device_time',
        'tmp36_temp', 'tmp36_voltage', 'tmp36_raw',
        'bme_temp', 'bme_pressure', 'bme_humidity', 'bme_gas', 'bme_gas_valid', 'bme_altitude',
        'ax', 'ay', 'az', 'gx', 'gy', 'gz', 'pitch', 'roll',
        'mag_x', 'mag_y', 'mag_z', 'heading',
        'gps_fix', 'gps_satellites', 'gps_lat', 'gps_lon', 'gps_altitude',
        'gps_hdop', 'gps_speed_kmh', 'gps_course_deg', 'gps_vertical_speed_ms',
        'parse_ok', 'parse_message',
    ];

    $values = [
        $datasetId,
        $lineNumber,
        $record['raw_line'],
        $record['mcu_sample_id'],
        $record['device_time'],
        $record['tmp36_temp'],
        $record['tmp36_voltage'],
        $record['tmp36_raw'],
        $record['bme_temp'],
        $record['bme_pressure'],
        $record['bme_humidity'],
        $record['bme_gas'],
        $record['bme_gas_valid'],
        $record['bme_altitude'],
        $record['ax'],
        $record['ay'],
        $record['az'],
        $record['gx'],
        $record['gy'],
        $record['gz'],
        $record['pitch'],
        $record['roll'],
        $record['mag_x'],
        $record['mag_y'],
        $record['mag_z'],
        $record['heading'],
        $record['gps_fix'],
        $record['gps_satellites'],
        $record['gps_lat'],
        $record['gps_lon'],
        $record['gps_altitude'],
        $record['gps_hdop'],
        $record['gps_speed_kmh'],
        $record['gps_course_deg'],
        $record['gps_vertical_speed_ms'],
        $record['parse_ok'] ? 1 : 0,
        $record['parse_message'],
    ];

    $placeholders = implode(', ', array_fill(0, count($columns), '?'));
    $stmt = $pdo->prepare('INSERT INTO telemetry (' . implode(', ', $columns) . ") VALUES ({$placeholders})");
    $stmt->execute($values);
}
