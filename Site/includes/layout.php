<?php
declare(strict_types=1);

function page_header(string $title, string $active): void
{
    ?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($title) ?> - CanSat Dashboard</title>
    <link rel="stylesheet" href="assets/css/app.css">
</head>
<body>
    <header class="topbar">
        <a class="brand" href="index.php">
            <span class="brand-mark">CS</span>
            <span>
                <span class="brand-title">Starships[CanSat]</span>
                <span class="brand-subtitle">Telemetry command deck</span>
            </span>
        </a>
        <nav>
            <a class="<?= $active === 'live' ? 'active' : '' ?>" href="live.php">Live</a>
            <a class="<?= $active === 'replay' ? 'active' : '' ?>" href="replay.php">Replay</a>
            <a class="<?= $active === 'logs' ? 'active' : '' ?>" href="logs.php">Logs</a>
            <a class="<?= $active === 'import' ? 'active' : '' ?>" href="import.php">Saved</a>
        </nav>
    </header>
    <main class="page">
    <?php
}

function page_footer(): void
{
    ?>
    </main>
</body>
</html>
    <?php
}
