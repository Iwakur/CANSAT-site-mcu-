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

    if ($action === 'copy_live') {
        $liveId = ensure_live_dataset($pdo);

        $countStmt = $pdo->prepare('SELECT COUNT(*) AS row_count FROM telemetry WHERE dataset_id = ?');
        $countStmt->execute([$liveId]);
        $rowCount = (int) (($countStmt->fetch()['row_count'] ?? 0));

        if ($rowCount === 0) {
            json_response(['ok' => false, 'error' => 'Live dataset has no rows to copy.'], 400);
        }

        $nameStmt = $pdo->query("SELECT name FROM datasets WHERE name REGEXP '^live_[0-9]+$'");
        $usedNumbers = [];
        foreach ($nameStmt->fetchAll() as $row) {
            if (preg_match('/^live_([0-9]+)$/', (string) $row['name'], $match)) {
                $usedNumbers[(int) $match[1]] = true;
            }
        }

        $copyNumber = 1;
        while (isset($usedNumbers[$copyNumber])) {
            $copyNumber += 1;
        }
        $copyName = 'live_' . $copyNumber;

        $pdo->beginTransaction();
        try {
            $stmt = $pdo->prepare(
                "INSERT INTO datasets (name, type, source_filename, notes, is_protected)
                 VALUES (?, 'import', NULL, ?, 0)"
            );
            $stmt->execute([$copyName, 'Copied from Live dataset.']);
            $copyId = (int) $pdo->lastInsertId();

            $pdo->prepare(
                "INSERT INTO telemetry (
                    dataset_id, received_at, line_number, raw_line, mcu_sample_id, device_time,
                    tmp36_temp, tmp36_voltage, tmp36_raw,
                    bme_temp, bme_pressure, bme_humidity, bme_gas, bme_gas_valid, bme_altitude,
                    ax, ay, az, gx, gy, gz, pitch, roll,
                    mag_x, mag_y, mag_z, heading,
                    gps_fix, gps_satellites, gps_lat, gps_lon, gps_altitude,
                    gps_hdop, gps_speed_kmh, gps_course_deg, gps_vertical_speed_ms,
                    parse_ok, parse_message
                )
                SELECT
                    ?, received_at, line_number, raw_line, mcu_sample_id, device_time,
                    tmp36_temp, tmp36_voltage, tmp36_raw,
                    bme_temp, bme_pressure, bme_humidity, bme_gas, bme_gas_valid, bme_altitude,
                    ax, ay, az, gx, gy, gz, pitch, roll,
                    mag_x, mag_y, mag_z, heading,
                    gps_fix, gps_satellites, gps_lat, gps_lon, gps_altitude,
                    gps_hdop, gps_speed_kmh, gps_course_deg, gps_vertical_speed_ms,
                    parse_ok, parse_message
                FROM telemetry
                WHERE dataset_id = ?
                ORDER BY id ASC"
            )->execute([$copyId, $liveId]);

            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }

        json_response([
            'ok' => true,
            'dataset_id' => $copyId,
            'dataset_name' => $copyName,
            'rows_copied' => $rowCount,
        ]);
    }

    json_response(['ok' => false, 'error' => 'Unknown action.'], 400);
} catch (Throwable $e) {
    json_response(['ok' => false, 'error' => $e->getMessage()], 500);
}
