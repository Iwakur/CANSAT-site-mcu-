<?php
declare(strict_types=1);

function telemetry_blank_record(string $line): array
{
    return [
        'raw_line' => $line,
        'device_time' => null,
        'bmp_temp' => null,
        'bmp_pressure' => null,
        'bmp_altitude' => null,
        'bme_temp' => null,
        'bme_pressure' => null,
        'bme_humidity' => null,
        'bme_gas' => null,
        'bme_altitude' => null,
        'tmp36_temp' => null,
        'tmp36_voltage' => null,
        'tmp36_raw' => null,
        'ax' => null,
        'ay' => null,
        'az' => null,
        'gx' => null,
        'gy' => null,
        'gz' => null,
        'pitch' => null,
        'roll' => null,
        'mag_x' => null,
        'mag_y' => null,
        'mag_z' => null,
        'heading' => null,
        'gps_fix' => null,
        'gps_satellites' => null,
        'gps_lat' => null,
        'gps_lon' => null,
        'gps_altitude' => null,
        'parse_ok' => false,
        'parse_message' => 'No telemetry fields found.',
    ];
}

function telemetry_section(string $line, string $name): string
{
    if (preg_match('/' . preg_quote($name, '/') . '\[([^\]]*)\]/', $line, $match)) {
        return $match[1];
    }

    return '';
}

function telemetry_value(string $section, string $key): ?string
{
    if (preg_match('/(?:^|\s)' . preg_quote($key, '/') . '=([^\s\]]+)/', $section, $match)) {
        return $match[1];
    }

    return null;
}

function telemetry_number(?string $value): ?float
{
    if ($value === null || $value === '' || $value === 'None' || $value === 'RTCERR') {
        return null;
    }

    if (!preg_match('/-?\d+(?:\.\d+)?/', $value, $match)) {
        return null;
    }

    return (float) $match[0];
}

function telemetry_int(?string $value): ?int
{
    $number = telemetry_number($value);
    return $number === null ? null : (int) round($number);
}

function parse_telemetry_line(string $line): array
{
    $line = trim(str_replace(["\r", "\n"], ' ', $line));
    $record = telemetry_blank_record($line);

    if ($line === '') {
        $record['parse_message'] = 'Empty line.';
        return $record;
    }

    if (preg_match('/(?:^|\s)T=([^\s]+)/', $line, $match)) {
        $record['device_time'] = $match[1];
    }

    $bmp = telemetry_section($line, 'BMP');
    $bme = telemetry_section($line, 'BME');
    $tmp36 = telemetry_section($line, 'TMP36');
    $mpu = telemetry_section($line, 'MPU');
    $mag = telemetry_section($line, 'MAG');
    $gps = telemetry_section($line, 'GPS');

    $record['bmp_temp'] = telemetry_number(telemetry_value($bmp, 'T'));
    $record['bmp_pressure'] = telemetry_number(telemetry_value($bmp, 'P'));
    $record['bmp_altitude'] = telemetry_number(telemetry_value($bmp, 'A'));

    $record['bme_temp'] = telemetry_number(telemetry_value($bme, 'T'));
    $record['bme_pressure'] = telemetry_number(telemetry_value($bme, 'P'));
    $record['bme_humidity'] = telemetry_number(telemetry_value($bme, 'H'));
    $record['bme_gas'] = telemetry_number(telemetry_value($bme, 'G'));
    $record['bme_altitude'] = telemetry_number(telemetry_value($bme, 'A'));

    $record['tmp36_temp'] = telemetry_number(telemetry_value($tmp36, 'T'));
    $record['tmp36_voltage'] = telemetry_number(telemetry_value($tmp36, 'V'));
    $record['tmp36_raw'] = telemetry_int(telemetry_value($tmp36, 'Raw'));

    $record['ax'] = telemetry_number(telemetry_value($mpu, 'Ax'));
    $record['ay'] = telemetry_number(telemetry_value($mpu, 'Ay'));
    $record['az'] = telemetry_number(telemetry_value($mpu, 'Az'));
    $record['gx'] = telemetry_number(telemetry_value($mpu, 'Gx'));
    $record['gy'] = telemetry_number(telemetry_value($mpu, 'Gy'));
    $record['gz'] = telemetry_number(telemetry_value($mpu, 'Gz'));
    $record['pitch'] = telemetry_number(telemetry_value($mpu, 'Pit'));
    $record['roll'] = telemetry_number(telemetry_value($mpu, 'Rol'));

    $record['mag_x'] = telemetry_number(telemetry_value($mag, 'X'));
    $record['mag_y'] = telemetry_number(telemetry_value($mag, 'Y'));
    $record['mag_z'] = telemetry_number(telemetry_value($mag, 'Z'));
    $record['heading'] = telemetry_number(telemetry_value($mag, 'H'));

    $record['gps_fix'] = telemetry_int(telemetry_value($gps, 'FIX'));
    $record['gps_satellites'] = telemetry_int(telemetry_value($gps, 'SAT'));
    $record['gps_lat'] = telemetry_number(telemetry_value($gps, 'LAT'));
    $record['gps_lon'] = telemetry_number(telemetry_value($gps, 'LON'));
    $record['gps_altitude'] = telemetry_number(telemetry_value($gps, 'ALT'));

    $hasSection = $bmp !== '' || $bme !== '' || $tmp36 !== '' || $mpu !== '' || $mag !== '' || $gps !== '';
    $hasValue = false;

    foreach ($record as $key => $value) {
        if (!in_array($key, ['raw_line', 'device_time', 'parse_ok', 'parse_message'], true) && $value !== null) {
            $hasValue = true;
            break;
        }
    }

    $record['parse_ok'] = $hasSection && $hasValue;
    $record['parse_message'] = $record['parse_ok']
        ? null
        : ($hasSection ? 'Telemetry sections found, but no numeric values parsed.' : 'No telemetry sections found.');

    return $record;
}
