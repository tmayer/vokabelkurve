<?php
// Lernstand lesen und schreiben. Jede Anfrage braucht den Geräteschlüssel im Header X-VK-Token.
//   GET   -> {settings, decks: {deckId: {wid_dir: card}}}
//   POST  {deck, cards: {wid_dir: card|null}}   Karten zusammenführen (null löscht)
//         {deck, reset: true}                   Lernstand eines Decks löschen
//         {settings: {...}}                     Einstellungen speichern
declare(strict_types=1);
require __DIR__ . '/config.php';

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

function fail(int $code, string $msg): void
{
    http_response_code($code);
    echo json_encode(['error' => $msg], JSON_UNESCAPED_UNICODE);
    exit;
}

// --- Zugang prüfen (Vergleich in konstanter Zeit, gespeichert ist nur der SHA-256-Hash) ---
$token = $_SERVER['HTTP_X_VK_TOKEN'] ?? '';
if (!is_string($token) || strlen($token) < 20 || strlen($token) > 200
    || !hash_equals(VK_TOKEN_HASH, hash('sha256', $token))) {
    usleep(400000); // bremst Rateversuche
    fail(401, 'Geräteschlüssel fehlt oder ist falsch');
}

$method = $_SERVER['REQUEST_METHOD'];
if ($method !== 'GET' && $method !== 'POST') {
    fail(405, 'Nur GET und POST erlaubt');
}

if (!is_dir(VK_DATA_DIR) && !mkdir(VK_DATA_DIR, 0750, true)) {
    fail(500, 'Datenordner fehlt und kann nicht angelegt werden');
}
$lock = fopen(VK_DATA_DIR . '/.lock', 'c');
if ($lock === false) {
    fail(500, 'Datenordner ist nicht beschreibbar');
}

function deckFile(string $deck): string
{
    return VK_DATA_DIR . '/progress-' . $deck . '.json';
}
function readJson(string $p): array
{
    if (!is_file($p)) {
        return [];
    }
    $j = json_decode((string) file_get_contents($p), true);
    return is_array($j) ? $j : [];
}
function writeJson(string $p, $data): void
{
    $tmp = $p . '.tmp';
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION);
    if ($json === false || file_put_contents($tmp, $json) === false || !rename($tmp, $p)) {
        fail(500, 'Speichern fehlgeschlagen');
    }
}
function isNum($v, float $min, float $max): bool
{
    return (is_int($v) || is_float($v)) && is_finite((float) $v) && $v >= $min && $v <= $max;
}
// Karte prüfen und nur bekannte Felder übernehmen
function cleanCard($c): ?array
{
    if (!is_array($c)) {
        return null;
    }
    $limits = ['S' => [0, 100000], 'D' => [0, 10], 'last' => [0, 1e14], 'due' => [0, 1e14],
               'reps' => [0, 1e6], 'lapses' => [0, 1e6], 'lastG' => [0, 4]];
    $out = [];
    foreach ($limits as $k => [$a, $b]) {
        if (!array_key_exists($k, $c) || !isNum($c[$k], $a, $b)) {
            return null;
        }
        $out[$k] = $c[$k];
    }
    if (!isset($c['h']) || !is_array($c['h']) || count($c['h']) > 60 || !array_is_list($c['h'])) {
        return null;
    }
    foreach ($c['h'] as $e) {
        if (!is_array($e) || count($e) > 8 || !array_is_list($e)) {
            return null;
        }
        foreach ($e as $x) {
            if (!isNum($x, -1, 1e14)) {
                return null;
            }
        }
    }
    $out['h'] = $c['h'];
    // Vertipper: [Zeitpunkt, Antwortzeit ms, Position]
    if (isset($c['slips'])) {
        if (!is_array($c['slips']) || count($c['slips']) > 60 || !array_is_list($c['slips'])) {
            return null;
        }
        foreach ($c['slips'] as $e) {
            if (!is_array($e) || count($e) !== 3 || !array_is_list($e)) {
                return null;
            }
            foreach ($e as $x) {
                if (!isNum($x, 0, 1e14)) {
                    return null;
                }
            }
        }
        $out['slips'] = $c['slips'];
    }
    return $out;
}

// ------------------------------------------------------------------ GET
if ($method === 'GET') {
    flock($lock, LOCK_SH);
    $decks = [];
    foreach (glob(VK_DATA_DIR . '/progress-*.json') ?: [] as $p) {
        if (preg_match('/progress-([a-z0-9-]{1,80})\.json$/', $p, $m)) {
            $decks[$m[1]] = (object) readJson($p);
        }
    }
    $settings = readJson(VK_DATA_DIR . '/settings.json');
    flock($lock, LOCK_UN);
    echo json_encode(['settings' => (object) $settings, 'decks' => (object) $decks],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION);
    exit;
}

// ------------------------------------------------------------------ POST
$len = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($len <= 0 || $len > VK_MAX_BODY) {
    fail(413, 'Anfrage zu groß oder leer');
}
$body = json_decode((string) file_get_contents('php://input', false, null, 0, VK_MAX_BODY), true, 32);
if (!is_array($body)) {
    fail(400, 'Ungültiges JSON');
}

flock($lock, LOCK_EX);

if (isset($body['settings'])) {
    $s = $body['settings'];
    if (!is_array($s)) {
        fail(400, 'Ungültige Einstellungen');
    }
    $clean = [];
    if (isset($s['retention']) && isNum($s['retention'], 0.7, 0.99)) $clean['retention'] = $s['retention'];
    if (isset($s['newPer']) && isNum($s['newPer'], 0, 50)) $clean['newPer'] = (int) $s['newPer'];
    if (isset($s['size']) && isNum($s['size'], 5, 100)) $clean['size'] = (int) $s['size'];
    if (isset($s['offset']) && isNum($s['offset'], 0, 1e11)) $clean['offset'] = $s['offset'];
    if (isset($s['autoNext']) && is_bool($s['autoNext'])) $clean['autoNext'] = $s['autoNext'];
    if (isset($s['nextMode']) && in_array($s['nextMode'], ['instant', 'delay', 'tap'], true)) $clean['nextMode'] = $s['nextMode'];
    if (isset($s['afterGoal']) && in_array($s['afterGoal'], ['new', 'review'], true)) $clean['afterGoal'] = $s['afterGoal'];
    if (isset($s['regraded']) && isNum($s['regraded'], 0, 100)) $clean['regraded'] = (int) $s['regraded'];
    if (isset($s['dirMode']) && in_array($s['dirMode'], ['both', '0', '1'], true)) $clean['dirMode'] = $s['dirMode'];
    if (isset($s['ovMode']) && in_array($s['ovMode'], ['word', '0', '1'], true)) $clean['ovMode'] = $s['ovMode'];
    if (isset($s['active']) && is_string($s['active']) && preg_match('/^[a-z0-9-]{1,80}$/', $s['active'])) $clean['active'] = $s['active'];
    writeJson(VK_DATA_DIR . '/settings.json', (object) $clean);
}

if (isset($body['deck'])) {
    $deck = $body['deck'];
    if (!is_string($deck) || !preg_match('/^[a-z0-9-]{1,80}$/', $deck)) {
        fail(400, 'Ungültige Deck-ID');
    }
    $file = deckFile($deck);
    if (!empty($body['reset'])) {
        if (is_file($file) && !unlink($file)) {
            fail(500, 'Zurücksetzen fehlgeschlagen');
        }
    } elseif (isset($body['cards']) && is_array($body['cards'])) {
        $cards = readJson($file);
        foreach ($body['cards'] as $k => $c) {
            if (!is_string($k) || !preg_match('/^[a-z0-9]{1,16}_[01]$/', $k)) {
                fail(400, 'Ungültiger Kartenschlüssel');
            }
            if ($c === null) {
                unset($cards[$k]);
                continue;
            }
            $clean = cleanCard($c);
            if ($clean === null) {
                fail(400, 'Ungültige Karte ' . $k);
            }
            $cards[$k] = $clean;
        }
        if (count($cards) > VK_MAX_CARDS) {
            fail(413, 'Zu viele Karten in diesem Deck');
        }
        writeJson($file, (object) $cards);
    }
}

flock($lock, LOCK_UN);
echo json_encode(['ok' => true]);
