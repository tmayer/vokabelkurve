<?php
// Listet die Deck-Dateien im Ordner decks/. Liefert nur Dateinamen, Größe und Änderungszeit.
declare(strict_types=1);
require __DIR__ . '/config.php';

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo json_encode(['error' => 'Nur GET erlaubt']);
    exit;
}

$out = [];
foreach (scandir(VK_DECK_DIR) ?: [] as $f) {
    // nur harmlose Dateinamen mit passender Endung, keine versteckten Dateien, keine Pfade
    if (!preg_match('/^[\p{L}\p{N}][\p{L}\p{M}\p{N} _().,+-]{0,119}\.(csv|tsv|txt)$/u', $f)) {
        continue;
    }
    $p = VK_DECK_DIR . '/' . $f;
    if (!is_file($p) || is_link($p)) {
        continue;
    }
    $out[] = ['file' => $f, 'size' => filesize($p), 'mtime' => filemtime($p)];
}
echo json_encode(['decks' => $out], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
