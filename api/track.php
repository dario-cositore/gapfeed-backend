<?php
/**
 * TuXo Tracking Pixel Endpoint
 * 
 * Minimal, fast PHP tracking pixel endpoint.
 * Accepts query string params, logs to MySQL, returns 1x1 transparent GIF.
 * Responds in under 50ms.
 * 
 * Usage: GET /api/track.php?p=/path&t=gap&q=search&...
 */

header('Content-Type: image/gif');
header('Cache-Control: no-cache, no-store, must-revalidate');
header('Pragma: no-cache');
header('Expires: 0');
header('Access-Control-Allow-Origin: *');

// === CONFIG (same as db.php) ===
// Real credentials live in config.local.php (gitignored) or environment variables.
$local_cfg = @include __DIR__ . '/config.local.php';
if (!is_array($local_cfg)) { $local_cfg = []; }
define('DB_HOST', $local_cfg['DB_HOST'] ?? (getenv('DB_HOST') ?: 'localhost'));
define('DB_USER', $local_cfg['DB_USER'] ?? (getenv('DB_USER') ?: ''));
define('DB_PASS', $local_cfg['DB_PASS'] ?? (getenv('DB_PASS') ?: ''));
define('DB_NAME', $local_cfg['DB_NAME'] ?? (getenv('DB_NAME') ?: ''));

// === 1x1 transparent GIF (base64 decoded) ===
$gif = base64_decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');

// === Database connection with error suppression ===
function getDB() {
    static $conn = null;
    if ($conn === null) {
        $conn = @new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME, 3306);
        if ($conn->connect_error) {
            // Log error but don't break response
            error_log('DB connection failed: ' . $conn->connect_error);
            $conn = null;
        } else {
            $conn->set_charset('utf8mb4');
        }
    }
    return $conn;
}

// === Rate limiting (file-based, 100 requests per IP per minute) ===
function isRateLimited($ip) {
    $dir = sys_get_temp_dir() . '/tuxo_tracking';
    if (!is_dir($dir)) {
        mkdir($dir, 0777, true);
    }
    $file = $dir . '/' . md5($ip) . '.cnt';
    $now = time();
    $window = 60; // 1 minute
    
    // Read existing counts
    $counts = [];
    if (file_exists($file)) {
        $data = file_get_contents($file);
        $counts = json_decode($data, true) ?? [];
    }
    
    // Clean old entries
    $counts = array_filter($counts, function($t) use ($now) {
        return $now - $t < $window;
    });
    
    // Check limit
    if (count($counts) >= 100) {
        return true;
    }
    
    // Add current request
    $counts[] = $now;
    file_put_contents($file, json_encode($counts));
    return false;
}

// === Anonymize IP (zero last octet) ===
function anonymizeIP($ip) {
    // IPv4: zero last octet, IPv6: zero last 64 bits? For simplicity, just IPv4.
    if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        $parts = explode('.', $ip);
        $parts[3] = '0';
        return implode('.', $parts);
    }
    return $ip;
}

// === Detect device type from User-Agent ===
function detectDeviceType($ua) {
    $ua = strtolower($ua);
    if (strpos($ua, 'bot') !== false || strpos($ua, 'crawler') !== false || strpos($ua, 'spider') !== false) {
        return 'bot';
    }
    if (preg_match('/(googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot|facebot|ia_archiver)/i', $ua)) {
        return 'bot';
    }
    if (strpos($ua, 'curl') !== false || strpos($ua, 'wget') !== false || strpos($ua, 'headless') !== false || strpos($ua, 'phantom') !== false) {
        return 'bot';
    }
    if (preg_match('/(tablet|ipad|playbook|silk)/i', $ua)) {
        return 'tablet';
    }
    if (preg_match('/(mobile|android|iphone|ipod|blackberry|opera mini|windows phone)/i', $ua)) {
        return 'mobile';
    }
    return 'desktop';
}

// === Main logic ===
try {
    // Get params
    $page_path = $_GET['p'] ?? '';
    $page_type = $_GET['t'] ?? 'other';
    $referrer = $_GET['ref'] ?? ($_SERVER['HTTP_REFERER'] ?? '');
    $search_query = $_GET['q'] ?? '';
    $session_hash = $_GET['s'] ?? '';
    $results_count = isset($_GET['results']) ? intval($_GET['results']) : 0;
    
    // Sanitize inputs
    $page_path = substr(htmlspecialchars($page_path, ENT_QUOTES, 'UTF-8'), 0, 500);
    $page_type = substr(htmlspecialchars($page_type, ENT_QUOTES, 'UTF-8'), 0, 20);
    $referrer = substr(htmlspecialchars($referrer, ENT_QUOTES, 'UTF-8'), 0, 500);
    $search_query = substr(htmlspecialchars($search_query, ENT_QUOTES, 'UTF-8'), 0, 200);
    $session_hash = substr(htmlspecialchars($session_hash, ENT_QUOTES, 'UTF-8'), 0, 8);
    
    // Rate limiting
    $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    if (isRateLimited($ip)) {
        // Still return GIF but skip DB insertion
        echo $gif;
        exit;
    }
    
    // Generate session hash if not provided
    if (empty($session_hash)) {
        $anon_ip = anonymizeIP($ip);
        $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
        $session_hash = substr(md5($anon_ip . $ua), 0, 8);
    }
    
    // Detect device type
    $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
    $device_type = detectDeviceType($ua);
    
    // Bot detection: if bot, still log but set device_type='bot'
    // Already handled by detectDeviceType
    
    // Country code (optional, skip for speed)
    $country_code = null;
    
    // Connect to DB
    $conn = getDB();
    if ($conn) {
        // Insert into page_views
        $stmt = $conn->prepare("
            INSERT INTO page_views (page_path, page_type, referrer, search_query, session_hash, device_type, country_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ");
        $stmt->bind_param('sssssss', $page_path, $page_type, $referrer, $search_query, $session_hash, $device_type, $country_code);
        $stmt->execute();
        $stmt->close();
        
        // Insert or update sessions
        $stmt = $conn->prepare("
            INSERT INTO sessions (session_hash, page_count, referrer, device_type, country_code)
            VALUES (?, 1, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                last_seen = CURRENT_TIMESTAMP,
                page_count = page_count + 1,
                referrer = COALESCE(?, referrer),
                device_type = COALESCE(?, device_type),
                country_code = COALESCE(?, country_code)
        ");
        $stmt->bind_param('sssssss', $session_hash, $referrer, $device_type, $country_code, $referrer, $device_type, $country_code);
        $stmt->execute();
        $stmt->close();
        
        // If search query present, also insert into search_queries
        if (!empty($search_query)) {
            $stmt = $conn->prepare("
                INSERT INTO search_queries (query_text, results_count, session_hash, clicked_gap_id)
                VALUES (?, ?, ?, NULL)
            ");
            $stmt->bind_param('sis', $search_query, $results_count, $session_hash);
            $stmt->execute();
            $stmt->close();
        }
    }
} catch (Exception $e) {
    // Log error but don't break response
    error_log('Tracking error: ' . $e->getMessage());
}

// Always return GIF
echo $gif;
exit;