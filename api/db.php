<?php
/**
 * TuXo Database API
 * 
 * REST-like PHP endpoint for MySQL operations.
 * Deployed on IONOS hosting, called by tuxo agents.
 * 
 * Usage: POST /api/db.php?action=<action>
 * Auth: Bearer token via Authorization header
 */

header('Content-Type: application/json');
error_reporting(E_ALL);
ini_set('display_errors', 0);
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// === CONFIG ===
// Real credentials live in config.local.php (gitignored) or environment variables.
$local_cfg = @include __DIR__ . '/config.local.php';
if (!is_array($local_cfg)) { $local_cfg = []; }
define('DB_HOST', $local_cfg['DB_HOST'] ?? (getenv('DB_HOST') ?: 'localhost'));
define('DB_USER', $local_cfg['DB_USER'] ?? (getenv('DB_USER') ?: ''));
define('DB_PASS', $local_cfg['DB_PASS'] ?? (getenv('DB_PASS') ?: ''));
define('DB_NAME', $local_cfg['DB_NAME'] ?? (getenv('DB_NAME') ?: ''));
define('API_KEY', $local_cfg['API_KEY'] ?? (getenv('GAPFEED_API_KEY') ?: ''));

// === AUTH ===
function authenticate() {
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if ($auth !== 'Bearer ' . API_KEY) {
        http_response_code(401);
        echo json_encode(['error' => 'Unauthorized']);
        exit;
    }
}

// === DB CONNECTION ===
function getDB() {
    static $conn = null;
    if ($conn === null) {
        $conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME, 3306);
        $conn->set_charset('utf8mb4');
        if ($conn->connect_error) {
            http_response_code(500);
            echo json_encode(['error' => 'DB connection failed: ' . $conn->connect_error]);
            exit;
        }
    }
    return $conn;
}

// === HELPER FUNCTIONS ===
function anonymizeIP($ip) {
    if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        $parts = explode('.', $ip);
        $parts[3] = '0';
        return implode('.', $parts);
    }
    return $ip;
}

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

// === INPUT ===
$action = $_GET['action'] ?? '';
$input = json_decode(file_get_contents('php://input'), true) ?? [];

// Public actions don't require auth (used by frontend)
$public_actions = ['brief', 'log_search', 'get_search_count', 'subscribe', 'get_signal_trend', 'get_popular_searches', 'track', 'sparklines', 'get_gaps', 'stats', 'source_distribution', 'sentiment_breakdown', 'buyer_intent_distribution', 'top_gaps_velocity', 'uptime', 'signal_velocity', 'category_breakdown', 'heat_distribution', 'source_trend'];
if (!in_array($action, $public_actions)) {
    authenticate();
}

// === ROUTES ===
try {
switch ($action) {

    // --- SIGNALS ---
    case 'insert_signal':
        $conn = getDB();
        $stmt = $conn->prepare("
            INSERT INTO signals (source, source_url, platform_id, subreddit, author, title, content,
                created_at, collected_at, vertical, product_category, pain_category, signal_type, location,
                urgency_score, specificity_score, buyer_intent, quality_tier, sentiment,
                competitor_mentions, metadata, is_processed, synthesized)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ");
        $source = $input['source'] ?? 'unknown';
        $source_url = $input['source_url'] ?? '';
        $platform_id = $input['platform_id'] ?? '';
        $subreddit = $input['subreddit'] ?? '';
        $author = $input['author'] ?? '';
        $title = $input['title'] ?? '';
        $content = $input['content'] ?? '';
        $created_at = $input['created_at'] ?? date('Y-m-d H:i:s');
        $collected_at = $input['collected_at'] ?? date('Y-m-d H:i:s');
        $vertical = $input['vertical'] ?? 'general';
        $product_category = $input['product_category'] ?? '';
        $pain_category = $input['pain_category'] ?? '';
        $signal_type = $input['signal_type'] ?? null;
        $location = $input['location'] ?? null;
        $urgency_score = floatval($input['urgency_score'] ?? 0);
        $specificity_score = floatval($input['specificity_score'] ?? 0);
        $buyer_intent = floatval($input['buyer_intent'] ?? 0);
        $quality_tier = $input['quality_tier'] ?? 'noise';
        $sentiment = $input['sentiment'] ?? 'neutral';
        $competitor_mentions = $input['competitor_mentions'] ?? '';
        $metadata = $input['metadata'] ?? '{}';
        $is_processed = intval($input['is_processed'] ?? 0);
        $synthesized = intval($input['synthesized'] ?? 0);
        $stmt->bind_param('sssssssssssssssdddsssii',
            $source, $source_url, $platform_id,
            $subreddit, $author, $title, $content,
            $created_at, $collected_at, $vertical,
            $product_category, $pain_category, $signal_type, $location,
            $urgency_score, $specificity_score, $buyer_intent,
            $quality_tier, $sentiment, $competitor_mentions,
            $metadata, $is_processed, $synthesized
        );
        if ($stmt->execute()) {
            echo json_encode(['ok' => true, 'id' => $conn->insert_id]);
        } else {
            echo json_encode(['error' => $stmt->error]);
        }
        $stmt->close();
        break;

    case 'insert_signals_bulk':
        $conn = getDB();
        $count = 0;
        $conn->begin_transaction();
        try {
            $stmt = $conn->prepare("
                INSERT INTO signals (source, source_url, platform_id, subreddit, author, title, content,
                    created_at, collected_at, vertical, product_category, pain_category, signal_type, location,
                    urgency_score, specificity_score, buyer_intent, quality_tier, sentiment,
                    competitor_mentions, metadata, is_processed, synthesized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ");
            foreach ($input['signals'] as $s) {
                $source = $s['source'] ?? 'unknown';
                $source_url = $s['source_url'] ?? '';
                $platform_id = $s['platform_id'] ?? '';
                $subreddit = $s['subreddit'] ?? '';
                $author = $s['author'] ?? '';
                $title = $s['title'] ?? '';
                $content = $s['content'] ?? '';
                $created_at = $s['created_at'] ?? date('Y-m-d H:i:s');
                $collected_at = $s['collected_at'] ?? date('Y-m-d H:i:s');
                $vertical = $s['vertical'] ?? 'general';
                $product_category = $s['product_category'] ?? '';
                $pain_category = $s['pain_category'] ?? '';
                $signal_type = $s['signal_type'] ?? null;
                $location = $s['location'] ?? null;
                $urgency_score = floatval($s['urgency_score'] ?? 0);
                $specificity_score = floatval($s['specificity_score'] ?? 0);
                $buyer_intent = floatval($s['buyer_intent'] ?? 0);
                $quality_tier = $s['quality_tier'] ?? 'noise';
                $sentiment = $s['sentiment'] ?? 'neutral';
                $competitor_mentions = $s['competitor_mentions'] ?? '';
                $metadata = $s['metadata'] ?? '{}';
                $is_processed = intval($s['is_processed'] ?? 0);
                $synthesized = intval($s['synthesized'] ?? 0);
                $stmt->bind_param('sssssssssssssssdddsssii',
                    $source, $source_url, $platform_id,
                    $subreddit, $author, $title, $content,
                    $created_at, $collected_at, $vertical,
                    $product_category, $pain_category, $signal_type, $location,
                    $urgency_score, $specificity_score, $buyer_intent,
                    $quality_tier, $sentiment, $competitor_mentions,
                    $metadata, $is_processed, $synthesized
                );
                $stmt->execute();
                $count++;
            }
            $conn->commit();
            echo json_encode(['ok' => true, 'inserted' => $count]);
        } catch (Exception $e) {
            $conn->rollback();
            echo json_encode(['error' => $e->getMessage()]);
        }
        $stmt->close();
        break;

    case 'get_signals':
        $conn = getDB();
        $where = ["1=1"];
        $params = [];
        $types = '';

        if (!empty($input['vertical'])) {
            $where[] = "vertical = ?";
            $params[] = $input['vertical'];
            $types .= 's';
        }
        if (!empty($input['quality_tier'])) {
            $where[] = "quality_tier = ?";
            $params[] = $input['quality_tier'];
            $types .= 's';
        }
        if (!empty($input['min_urgency'])) {
            $where[] = "urgency_score >= ?";
            $params[] = floatval($input['min_urgency']);
            $types .= 'd';
        }
        if (isset($input['is_processed']) && $input['is_processed'] !== '') {
            $where[] = "is_processed = ?";
            $params[] = intval($input['is_processed']);
            $types .= 'i';
        }
        if (!empty($input['signal_type'])) {
            $where[] = "signal_type = ?";
            $params[] = $input['signal_type'];
            $types .= 's';
        }
        if (isset($input['gap_id']) && $input['gap_id'] !== '') {
            $where[] = "gap_id = ?";
            $params[] = intval($input['gap_id']);
            $types .= 'i';
        }

        $limit = intval($input['limit'] ?? 50);
        $offset = intval($input['offset'] ?? 0);
        $order = $input['order'] ?? 'urgency_score DESC';

        $sql = "SELECT * FROM signals WHERE " . implode(' AND ', $where) . " ORDER BY $order LIMIT $limit OFFSET $offset";
        $stmt = $conn->prepare($sql);
        if ($types) {
            $stmt->bind_param($types, ...$params);
        }
        $stmt->execute();
        $result = $stmt->get_result();
        $rows = [];
        while ($row = $result->fetch_assoc()) {
            $rows[] = $row;
        }
        echo json_encode(['signals' => $rows, 'count' => count($rows)]);
        $stmt->close();
        break;

    case 'update_signal':
        $conn = getDB();
        $id = intval($input['id']);
        $sets = [];
        $params = [];
        $types = '';

        $allowed = ['pain_category', 'signal_type', 'location', 'urgency_score', 'specificity_score', 'buyer_intent',
                     'quality_tier', 'sentiment', 'competitor_mentions', 'metadata',
                     'is_processed', 'synthesized', 'content', 'title', 'gap_id', 'category'];
        foreach ($allowed as $field) {
            if (array_key_exists($field, $input)) {
                $sets[] = "$field = ?";
                $params[] = $input[$field];
                $types .= (in_array($field, ['urgency_score', 'specificity_score', 'buyer_intent'])) ? 'd' : ((in_array($field, ['is_processed', 'synthesized', 'gap_id'])) ? 'i' : 's');
            }
        }
        if (empty($sets)) {
            echo json_encode(['error' => 'No fields to update']);
            break;
        }
        $params[] = $id;
        $types .= 'i';
        $sql = "UPDATE signals SET " . implode(', ', $sets) . " WHERE id = ?";
        $stmt = $conn->prepare($sql);
        $stmt->bind_param($types, ...$params);
        $stmt->execute();
        echo json_encode(['ok' => true, 'affected' => $stmt->affected_rows]);
        $stmt->close();
        break;

    case 'signal_exists':
        $conn = getDB();
        $stmt = $conn->prepare("SELECT id FROM signals WHERE platform_id = ? AND source = ?");
        $stmt->bind_param('ss', $input['platform_id'], $input['source']);
        $stmt->execute();
        $result = $stmt->get_result();
        $row = $result->fetch_assoc();
        echo json_encode(['exists' => $row ? true : false, 'id' => $row['id'] ?? null]);
        $stmt->close();
        break;

    // --- BRIEFS ---
    case 'upsert_brief':
        $conn = getDB();
        $stmt = $conn->prepare("
            INSERT INTO briefs (vertical, query_hash, query, brief_json, brief_md, signal_count, quality, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE brief_json=VALUES(brief_json), brief_md=VALUES(brief_md),
                signal_count=VALUES(signal_count), quality=VALUES(quality), generated_at=VALUES(generated_at)
        ");
        $stmt->bind_param('sssssiss',
            $input['vertical'], $input['query_hash'], $input['query'],
            $input['brief_json'], $input['brief_md'], $input['signal_count'],
            $input['quality'], $input['generated_at']
        );
        if ($stmt->execute()) {
            echo json_encode(['ok' => true]);
        } else {
            echo json_encode(['error' => $stmt->error]);
        }
        $stmt->close();
        break;

    case 'get_brief':
        $conn = getDB();
        $stmt = $conn->prepare("SELECT * FROM briefs WHERE vertical = ? AND query_hash = ?");
        $stmt->bind_param('ss', $input['vertical'], $input['query_hash']);
        $stmt->execute();
        $result = $stmt->get_result();
        $row = $result->fetch_assoc();
        echo json_encode(['brief' => $row]);
        $stmt->close();
        break;

    case 'get_briefs':
        $conn = getDB();
        $vertical = $input['vertical'] ?? '';
        if ($vertical) {
            $stmt = $conn->prepare("SELECT query, signal_count, quality, generated_at FROM briefs WHERE vertical = ? ORDER BY generated_at DESC LIMIT ?");
            $limit = intval($input['limit'] ?? 20);
            $stmt->bind_param('si', $vertical, $limit);
        } else {
            $stmt = $conn->prepare("SELECT query, signal_count, quality, generated_at FROM briefs ORDER BY generated_at DESC LIMIT ?");
            $limit = intval($input['limit'] ?? 20);
            $stmt->bind_param('i', $limit);
        }
        $stmt->execute();
        $result = $stmt->get_result();
        $rows = [];
        while ($row = $result->fetch_assoc()) {
            $rows[] = $row;
        }
        echo json_encode(['briefs' => $rows]);
        $stmt->close();
        break;

    // --- SCAN LOG ---
    case 'log_scan':
        $conn = getDB();
        $stmt = $conn->prepare("INSERT INTO scan_log (vertical, source, category, signals_found, signals_new, started_at) VALUES (?, ?, ?, 0, 0, NOW())");
        $stmt->bind_param('sss', $input['vertical'], $input['source'], $input['category']);
        $stmt->execute();
        echo json_encode(['ok' => true, 'id' => $conn->insert_id]);
        $stmt->close();
        break;

    case 'complete_scan':
        $conn = getDB();
        $stmt = $conn->prepare("UPDATE scan_log SET signals_found=?, signals_new=?, completed_at=NOW() WHERE id=?");
        $stmt->bind_param('iii', $input['signals_found'], $input['signals_new'], $input['scan_id']);
        $stmt->execute();
        echo json_encode(['ok' => true, 'affected' => $stmt->affected_rows]);
        $stmt->close();
        break;

    // --- STATS ---
    case 'signal_count':
        $conn = getDB();
        $vertical = $input['vertical'] ?? null;
        if ($vertical && $vertical !== '') {
            $stmt = $conn->prepare("SELECT COUNT(*) as cnt FROM signals WHERE vertical = ? AND quality_tier != 'noise'");
            $stmt->bind_param('s', $vertical);
            $stmt->execute();
            $result = $stmt->get_result();
            $row = $result->fetch_assoc();
            echo json_encode(['total' => intval($row['cnt'])]);
            $stmt->close();
        } else {
            $result = $conn->query("SELECT vertical, COUNT(*) as cnt FROM signals WHERE quality_tier != 'noise' GROUP BY vertical");
            $counts = [];
            $total = 0;
            while ($row = $result->fetch_assoc()) {
                $counts[$row['vertical']] = intval($row['cnt']);
                $total += intval($row['cnt']);
            }
            echo json_encode(['total' => $total, 'by_vertical' => $counts]);
        }
        break;

    // --- API STATS (for health checks) ---
    case 'stats':
        $conn = getDB();
        $signals = $conn->query("SELECT COUNT(*) as cnt FROM signals WHERE quality_tier != 'noise'")->fetch_assoc()['cnt'];
        $gaps = $conn->query("SELECT COUNT(*) as cnt FROM gaps WHERE status = 'active'")->fetch_assoc()['cnt'];
        echo json_encode([
            'ok' => true,
            'signals' => intval($signals),
            'gaps' => intval($gaps),
            'timestamp' => date('c'),
        ]);
        break;

    // --- MIGRATION ---
    case 'migrate_schema':
        $conn = getDB();
        $sqls = [
            "CREATE TABLE IF NOT EXISTS signals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                source_url TEXT,
                platform_id VARCHAR(255),
                subreddit VARCHAR(100),
                author VARCHAR(255),
                title TEXT,
                content TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                collected_at DATETIME NOT NULL,
                vertical VARCHAR(50) NOT NULL DEFAULT 'general',
                product_category VARCHAR(100),
                pain_category VARCHAR(100),
                signal_type VARCHAR(20) DEFAULT NULL,
                location VARCHAR(255) DEFAULT NULL,
                urgency_score DECIMAL(5,3) DEFAULT 0,
                specificity_score DECIMAL(5,3) DEFAULT 0,
                buyer_intent DECIMAL(5,3) DEFAULT 0,
                quality_tier VARCHAR(20) DEFAULT 'noise',
                sentiment VARCHAR(20) DEFAULT 'neutral',
                competitor_mentions TEXT,
                metadata TEXT,
                is_processed TINYINT DEFAULT 0,
                synthesized TINYINT DEFAULT 0,
                INDEX idx_vertical (vertical),
                INDEX idx_quality (quality_tier),
                INDEX idx_urgency (urgency_score),
                INDEX idx_type (signal_type),
                INDEX idx_location (location),
                INDEX idx_platform (platform_id, source)
            )",
            "CREATE TABLE IF NOT EXISTS briefs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vertical VARCHAR(50) NOT NULL,
                query_hash VARCHAR(64) NOT NULL,
                query TEXT NOT NULL,
                brief_json LONGTEXT NOT NULL,
                brief_md TEXT,
                signal_count INT DEFAULT 0,
                quality VARCHAR(20),
                generated_at DATETIME NOT NULL,
                UNIQUE KEY uq_query (vertical, query_hash)
            )",
            "CREATE TABLE IF NOT EXISTS scan_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vertical VARCHAR(50) NOT NULL,
                source VARCHAR(50) NOT NULL,
                category VARCHAR(100),
                signals_found INT DEFAULT 0,
                signals_new INT DEFAULT 0,
                started_at DATETIME NOT NULL,
                completed_at DATETIME,
                INDEX idx_vertical (vertical)
            )",
            "CREATE TABLE IF NOT EXISTS gaps (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                slug VARCHAR(500) NOT NULL UNIQUE,
                description TEXT,
                evidence_count INT DEFAULT 0,
                heat_score FLOAT DEFAULT 0,
                category VARCHAR(100) DEFAULT 'uncategorized',
                source_types JSON,
                signal_ids JSON,
                sample_quotes JSON,
                status ENUM('active','stale','merged') DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_heat (heat_score DESC),
                INDEX idx_category (category),
                INDEX idx_status (status),
                INDEX idx_created (created_at DESC)
            )",
            "CREATE TABLE IF NOT EXISTS page_views (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                page_path VARCHAR(500) NOT NULL,
                page_type ENUM('gap','category','source','tag','landing','about','digest','other') DEFAULT 'other',
                referrer VARCHAR(500) DEFAULT NULL,
                search_query VARCHAR(200) DEFAULT NULL,
                session_hash CHAR(8) NOT NULL,
                device_type ENUM('desktop','mobile','tablet','bot','unknown') DEFAULT 'unknown',
                country_code CHAR(2) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_page_type (page_type),
                INDEX idx_created_at (created_at),
                INDEX idx_page_path (page_path),
                INDEX idx_search_query (search_query),
                INDEX idx_session (session_hash)
            )",
            "CREATE TABLE IF NOT EXISTS search_queries (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                query_text VARCHAR(200) NOT NULL,
                results_count INT DEFAULT 0,
                session_hash CHAR(8) NOT NULL,
                clicked_gap_id INT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_query (query_text),
                INDEX idx_no_results (results_count),
                INDEX idx_created (created_at)
            )",
            "CREATE TABLE IF NOT EXISTS sessions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                session_hash CHAR(8) NOT NULL UNIQUE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                page_count INT DEFAULT 1,
                referrer VARCHAR(500) DEFAULT NULL,
                device_type ENUM('desktop','mobile','tablet','bot','unknown') DEFAULT 'unknown',
                country_code CHAR(2) DEFAULT NULL,
                INDEX idx_last_seen (last_seen),
                INDEX idx_page_count (page_count)
            )",
            "CREATE TABLE IF NOT EXISTS gap_engagement (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                gap_id INT NOT NULL,
                views INT DEFAULT 0,
                unique_visitors INT DEFAULT 0,
                avg_time_seconds FLOAT DEFAULT 0,
                search_impressions INT DEFAULT 0,
                search_clicks INT DEFAULT 0,
                date DATE NOT NULL,
                UNIQUE KEY unique_gap_date (gap_id, date),
                INDEX idx_gap_id (gap_id),
                INDEX idx_date (date),
                INDEX idx_views (views)
            )"
        ];
        $results = [];
        foreach ($sqls as $i => $sql) {
            if ($conn->query($sql)) {
                $results[] = "Table $i: OK";
            } else {
                $results[] = "Table $i: ERROR - " . $conn->error;
            }
        }
        // Migrate: add signal_type column to existing tables
        $col_check = $conn->query("SHOW COLUMNS FROM signals LIKE 'signal_type'");
        if ($col_check && $col_check->num_rows === 0) {
            $conn->query("ALTER TABLE signals ADD COLUMN signal_type VARCHAR(20) DEFAULT NULL AFTER pain_category");
            $conn->query("CREATE INDEX idx_signal_type ON signals(signal_type)");
            $results[] = "Migration: signal_type column added";
        } else {
            $results[] = "Migration: signal_type column already exists";
        }
        // Migrate: add location column to existing tables
        $col_check2 = $conn->query("SHOW COLUMNS FROM signals LIKE 'location'");
        if ($col_check2 && $col_check2->num_rows === 0) {
            $conn->query("ALTER TABLE signals ADD COLUMN location VARCHAR(255) DEFAULT NULL AFTER signal_type");
            $conn->query("CREATE INDEX idx_location ON signals(location)");
            $results[] = "Migration: location column added";
        } else {
            $results[] = "Migration: location column already exists";
        }
        
        // Add competitors column to gaps table
        $check = $conn->query("SHOW COLUMNS FROM gaps LIKE 'competitors'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE gaps ADD COLUMN competitors JSON DEFAULT NULL AFTER sample_quotes");
            $results[] = "Migration: competitors column added to gaps";
        } else {
            $results[] = "Migration: competitors column already exists in gaps";
        }
        
        // Add gap_validity column to gaps table
        $check = $conn->query("SHOW COLUMNS FROM gaps LIKE 'gap_validity'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE gaps ADD COLUMN gap_validity VARCHAR(20) DEFAULT 'unvalidated' AFTER competitors");
            $results[] = "Migration: gap_validity column added to gaps";
        } else {
            $results[] = "Migration: gap_validity column already exists in gaps";
        }
        
        // Add last_validated_at column to gaps table
        $check = $conn->query("SHOW COLUMNS FROM gaps LIKE 'last_validated_at'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE gaps ADD COLUMN last_validated_at DATETIME DEFAULT NULL AFTER gap_validity");
            $results[] = "Migration: last_validated_at column added to gaps";
        } else {
            $results[] = "Migration: last_validated_at column already exists in gaps";
        }

        // Add gap_id column to signals table
        $check = $conn->query("SHOW COLUMNS FROM signals LIKE 'gap_id'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE signals ADD COLUMN gap_id INT DEFAULT NULL AFTER quality_tier");
            $conn->query("ALTER TABLE signals ADD INDEX idx_gap_id (gap_id)");
            $results[] = "Migration: gap_id column added to signals";
        } else {
            $results[] = "Migration: gap_id column already exists in signals";
        }

        // Add category column to signals table
        $check = $conn->query("SHOW COLUMNS FROM signals LIKE 'category'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE signals ADD COLUMN category VARCHAR(100) DEFAULT NULL AFTER gap_id");
            $results[] = "Migration: category column added to signals";
        } else {
            $results[] = "Migration: category column already exists in signals";
        }
        
        // Add opportunity_score column to gaps table
        $check = $conn->query("SHOW COLUMNS FROM gaps LIKE 'opportunity_score'");
        if ($check->num_rows === 0) {
            $conn->query("ALTER TABLE gaps ADD COLUMN opportunity_score FLOAT DEFAULT NULL AFTER last_validated_at");
            $results[] = "Migration: opportunity_score column added to gaps";
        } else {
            $results[] = "Migration: opportunity_score column already exists in gaps";
        }

        // competitor_entities table (Phase 2 - persistent entity registry)
        $conn->query("CREATE TABLE IF NOT EXISTS competitor_entities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            canonical_name VARCHAR(200) NOT NULL,
            aliases JSON,
            entity_type ENUM('competitor','substitute','platform','tool') DEFAULT 'competitor',
            verticals JSON,
            total_mentions INT DEFAULT 0,
            total_authors INT DEFAULT 0,
            avg_negative_rate DECIMAL(5,3) DEFAULT 0,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            active TINYINT DEFAULT 1,
            UNIQUE KEY uq_canonical (canonical_name),
            INDEX idx_type (entity_type),
            INDEX idx_mentions (total_mentions DESC)
        )");
        $results[] = "Table competitor_entities: OK";

        // signal_entity_mentions table (Phase 2 - which signal mentions which entity)
        $conn->query("CREATE TABLE IF NOT EXISTS signal_entity_mentions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            signal_id INT NOT NULL,
            entity_id INT NOT NULL,
            raw_mention VARCHAR(200) NOT NULL,
            mention_type ENUM('competitor','substitute','product_category','content_scan') DEFAULT 'content_scan',
            confidence DECIMAL(5,3) DEFAULT 0.5,
            sentiment VARCHAR(20) DEFAULT 'neutral',
            context_span TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_signal_entity (signal_id, entity_id),
            INDEX idx_signal (signal_id),
            INDEX idx_entity (entity_id),
            INDEX idx_confidence (confidence DESC)
        )");
        $results[] = "Table signal_entity_mentions: OK";

        echo json_encode(['ok' => true, 'results' => $results]);
        break;

    // --- COMPETITOR ENTITIES (Phase 2) ---

    case 'upsert_entity':
        $conn = getDB();
        $name = $input['canonical_name'] ?? '';
        if (!$name) {
            http_response_code(400);
            echo json_encode(['error' => 'No canonical_name provided']);
            break;
        }
        $aliases = isset($input['aliases']) ? json_encode($input['aliases']) : null;
        $entity_type = $input['entity_type'] ?? 'competitor';
        $verticals = isset($input['verticals']) ? json_encode($input['verticals']) : null;

        $stmt = $conn->prepare("INSERT INTO competitor_entities (canonical_name, aliases, entity_type, verticals)
            VALUES (?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE aliases=VALUES(aliases), entity_type=VALUES(entity_type),
                verticals=JSON_MERGE_PATCH(verticals, VALUES(verticals)), last_seen=NOW()");
        $stmt->bind_param('ssss', $name, $aliases, $entity_type, $verticals);
        if ($stmt->execute()) {
            $entity_id = $conn->insert_id ?: $conn->query("SELECT id FROM competitor_entities WHERE canonical_name = '" . $conn->real_escape_string($name) . "'")->fetch_assoc()['id'];
            echo json_encode(['ok' => true, 'id' => intval($entity_id)]);
        } else {
            echo json_encode(['error' => $stmt->error]);
        }
        $stmt->close();
        break;

    case 'update_entity_stats':
        $conn = getDB();
        $entity_id = intval($input['entity_id'] ?? 0);
        if (!$entity_id) {
            http_response_code(400);
            echo json_encode(['error' => 'No entity_id']);
            break;
        }
        $total_mentions = intval($input['total_mentions'] ?? 0);
        $total_authors = intval($input['total_authors'] ?? 0);
        $avg_negative = floatval($input['avg_negative_rate'] ?? 0);
        $stmt = $conn->prepare("UPDATE competitor_entities SET total_mentions=?, total_authors=?, avg_negative_rate=?, last_seen=NOW() WHERE id=?");
        $stmt->bind_param('iidi', $total_mentions, $total_authors, $avg_negative, $entity_id);
        $stmt->execute();
        echo json_encode(['ok' => true]);
        $stmt->close();
        break;

    case 'get_entities':
        $conn = getDB();
        $where = ["active = 1"];
        $params = [];
        $types = '';
        if (!empty($_GET['entity_type'])) {
            $where[] = "entity_type = ?";
            $params[] = $_GET['entity_type'];
            $types .= 's';
        }
        $limit = intval($_GET['limit'] ?? 50);
        $order = $_GET['order'] ?? 'total_mentions DESC';
        $sql = "SELECT * FROM competitor_entities WHERE " . implode(' AND ', $where) . " ORDER BY $order LIMIT $limit";
        $stmt = $conn->prepare($sql);
        if ($types) $stmt->bind_param($types, ...$params);
        $stmt->execute();
        $rows = [];
        foreach ($stmt->get_result() as $row) {
            $row['aliases'] = json_decode($row['aliases'], true) ?? [];
            $row['verticals'] = json_decode($row['verticals'], true) ?? [];
            $rows[] = $row;
        }
        echo json_encode(['entities' => $rows, 'count' => count($rows)]);
        $stmt->close();
        break;

    case 'insert_mention':
        $conn = getDB();
        $signal_id = intval($input['signal_id'] ?? 0);
        $entity_id = intval($input['entity_id'] ?? 0);
        if (!$signal_id || !$entity_id) {
            http_response_code(400);
            echo json_encode(['error' => 'signal_id and entity_id required']);
            break;
        }
        $raw = $input['raw_mention'] ?? '';
        $mtype = $input['mention_type'] ?? 'content_scan';
        $confidence = floatval($input['confidence'] ?? 0.5);
        $sentiment = $input['sentiment'] ?? 'neutral';
        $context = $input['context_span'] ?? null;

        $stmt = $conn->prepare("INSERT INTO signal_entity_mentions (signal_id, entity_id, raw_mention, mention_type, confidence, sentiment, context_span)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE confidence=VALUES(confidence), sentiment=VALUES(sentiment), context_span=VALUES(context_span)");
        $stmt->bind_param('iissdss', $signal_id, $entity_id, $raw, $mtype, $confidence, $sentiment, $context);
        if ($stmt->execute()) {
            echo json_encode(['ok' => true, 'id' => intval($conn->insert_id)]);
        } else {
            echo json_encode(['error' => $stmt->error]);
        }
        $stmt->close();
        break;

    case 'insert_mentions_bulk':
        $conn = getDB();
        $mentions = $input['mentions'] ?? [];
        if (empty($mentions)) {
            echo json_encode(['ok' => true, 'inserted' => 0]);
            break;
        }
        $stmt = $conn->prepare("INSERT INTO signal_entity_mentions (signal_id, entity_id, raw_mention, mention_type, confidence, sentiment, context_span)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE confidence=VALUES(confidence), sentiment=VALUES(sentiment)");
        $inserted = 0;
        foreach ($mentions as $m) {
            $sid = intval($m['signal_id'] ?? 0);
            $eid = intval($m['entity_id'] ?? 0);
            $raw = $m['raw_mention'] ?? '';
            $mtype = $m['mention_type'] ?? 'content_scan';
            $conf = floatval($m['confidence'] ?? 0.5);
            $sent = $m['sentiment'] ?? 'neutral';
            $ctx = $m['context_span'] ?? null;
            if ($sid && $eid) {
                $stmt->bind_param('iissdss', $sid, $eid, $raw, $mtype, $conf, $sent, $ctx);
                $stmt->execute();
                $inserted++;
            }
        }
        echo json_encode(['ok' => true, 'inserted' => $inserted]);
        $stmt->close();
        break;

    case 'get_cluster_entities':
        // Get top entities across a list of signal IDs
        $conn = getDB();
        $signal_ids = $input['signal_ids'] ?? [];
        if (empty($signal_ids)) {
            echo json_encode(['entities' => []]);
            break;
        }
        $placeholders = implode(',', array_fill(0, count($signal_ids), '?'));
        $types = str_repeat('i', count($signal_ids));

        $sql = "SELECT e.canonical_name, e.entity_type, COUNT(DISTINCT m.signal_id) as mention_count,
                    COUNT(DISTINCT s.author) as author_count,
                    SUM(CASE WHEN m.sentiment IN ('negative','frustrated','angry') THEN 1 ELSE 0 END) / COUNT(*) as negative_rate
                FROM signal_entity_mentions m
                JOIN competitor_entities e ON e.id = m.entity_id
                JOIN signals s ON s.id = m.signal_id
                WHERE m.signal_id IN ($placeholders)
                GROUP BY e.id, e.canonical_name, e.entity_type
                ORDER BY mention_count DESC
                LIMIT 20";

        $stmt = $conn->prepare($sql);
        $stmt->bind_param($types, ...$signal_ids);
        $stmt->execute();
        $rows = [];
        foreach ($stmt->get_result() as $row) {
            $row['negative_rate'] = round(floatval($row['negative_rate']), 2);
            $rows[] = $row;
        }
        echo json_encode(['entities' => $rows, 'count' => count($rows)]);
        $stmt->close();
        break;

    // --- COMPETITOR ANALYTICS (Phase 3) ---

    case 'top_competitors_by_category':
        // Top failed competitors per pain category
        $conn = getDB();
        $category = $_GET['category'] ?? '';
        $limit = intval($_GET['limit'] ?? 20);

        if ($category) {
            $sql = "SELECT e.canonical_name, e.entity_type,
                        COUNT(DISTINCT m.signal_id) as mentions,
                        COUNT(DISTINCT s.author) as authors,
                        SUM(CASE WHEN m.sentiment IN ('negative','frustrated','angry') THEN 1 ELSE 0 END) / COUNT(*) as negative_rate
                    FROM signal_entity_mentions m
                    JOIN competitor_entities e ON e.id = m.entity_id
                    JOIN signals s ON s.id = m.signal_id
                    WHERE s.pain_category = ? AND e.entity_type = 'competitor'
                    GROUP BY e.id, e.canonical_name, e.entity_type
                    HAVING mentions >= 3
                    ORDER BY negative_rate DESC, mentions DESC
                    LIMIT ?";
            $stmt = $conn->prepare($sql);
            $stmt->bind_param('si', $category, $limit);
        } else {
            // All categories
            $sql = "SELECT s.pain_category, e.canonical_name, e.entity_type,
                        COUNT(DISTINCT m.signal_id) as mentions,
                        SUM(CASE WHEN m.sentiment IN ('negative','frustrated','angry') THEN 1 ELSE 0 END) / COUNT(*) as negative_rate
                    FROM signal_entity_mentions m
                    JOIN competitor_entities e ON e.id = m.entity_id
                    JOIN signals s ON s.id = m.signal_id
                    WHERE e.entity_type = 'competitor'
                    GROUP BY s.pain_category, e.id, e.canonical_name, e.entity_type
                    HAVING mentions >= 3
                    ORDER BY s.pain_category, negative_rate DESC
                    LIMIT ?";
            $stmt = $conn->prepare($sql);
            $stmt->bind_param('i', $limit);
        }
        $stmt->execute();
        $rows = [];
        foreach ($stmt->get_result() as $row) {
            $row['negative_rate'] = round(floatval($row['negative_rate']), 2);
            $rows[] = $row;
        }
        echo json_encode(['results' => $rows, 'count' => count($rows)]);
        $stmt->close();
        break;

    case 'substitute_analytics':
        // Which substitutes dominate before people buy SaaS
        $conn = getDB();
        $sql = "SELECT e.canonical_name,
                    COUNT(DISTINCT m.signal_id) as mentions,
                    COUNT(DISTINCT s.author) as authors,
                    AVG(s.urgency_score) as avg_urgency,
                    GROUP_CONCAT(DISTINCT s.pain_category) as categories
                FROM signal_entity_mentions m
                JOIN competitor_entities e ON e.id = m.entity_id
                JOIN signals s ON s.id = m.signal_id
                WHERE e.entity_type = 'substitute'
                GROUP BY e.id, e.canonical_name
                ORDER BY mentions DESC
                LIMIT 20";
        $stmt = $conn->prepare($sql);
        $stmt->execute();
        $rows = [];
        foreach ($stmt->get_result() as $row) {
            $row['avg_urgency'] = round(floatval($row['avg_urgency'] ?? 0), 2);
            $rows[] = $row;
        }
        echo json_encode(['substitutes' => $rows, 'count' => count($rows)]);
        $stmt->close();
        break;

    case 'entity_heatmap':
        // Entity mentions over time (for trend detection)
        $conn = getDB();
        $entity_id = intval($_GET['entity_id'] ?? 0);
        if (!$entity_id) {
            http_response_code(400);
            echo json_encode(['error' => 'entity_id required']);
            break;
        }
        $sql = "SELECT DATE(s.collected_at) as date, COUNT(*) as mentions
                FROM signal_entity_mentions m
                JOIN signals s ON s.id = m.signal_id
                WHERE m.entity_id = ? AND s.collected_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY DATE(s.collected_at)
                ORDER BY date";
        $stmt = $conn->prepare($sql);
        $stmt->bind_param('i', $entity_id);
        $stmt->execute();
        $rows = [];
        foreach ($stmt->get_result() as $row) {
            $rows[] = $row;
        }
        echo json_encode(['entity_id' => $entity_id, 'daily' => $rows]);
        $stmt->close();
        break;

    // --- SEARCH LOGGING ---
    case 'log_search':
        $conn = getDB();
        $query = trim($input['query'] ?? '');
        if (!$query) {
            echo json_encode(['error' => 'No query provided']);
            break;
        }
        // --- social proof logging (search_log) ---
        // Create table if not exists
        $conn->query("CREATE TABLE IF NOT EXISTS search_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_query (query)
        )");
        // Insert
        $stmt = $conn->prepare("INSERT INTO search_log (query) VALUES (?)");
        $stmt->bind_param('s', $query);
        $stmt->execute();
        $stmt->close();
        // Get count
        $stmt = $conn->prepare("SELECT COUNT(*) as cnt FROM search_log WHERE query = ?");
        $stmt->bind_param('s', $query);
        $stmt->execute();
        $row = $stmt->get_result()->fetch_assoc();
        $stmt->close();
        $count = intval($row['cnt']);
        
        // --- analytics logging (search_queries) ---
        // Create table if not exists
        $conn->query("CREATE TABLE IF NOT EXISTS search_queries (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            query_text VARCHAR(200) NOT NULL,
            results_count INT DEFAULT 0,
            session_hash CHAR(8) NOT NULL,
            clicked_gap_id INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_query (query_text),
            INDEX idx_no_results (results_count),
            INDEX idx_created (created_at)
        )");
        // Generate session hash if not provided
        $session_hash = $input['session_hash'] ?? '';
        if (empty($session_hash)) {
            $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
            $anon_ip = anonymizeIP($ip);
            $ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
            $session_hash = substr(md5($anon_ip . $ua), 0, 8);
        }
        $results_count = intval($input['results_count'] ?? 0);
        $clicked_gap_id = isset($input['clicked_gap_id']) ? intval($input['clicked_gap_id']) : null;
        // Insert into search_queries
        $stmt = $conn->prepare("INSERT INTO search_queries (query_text, results_count, session_hash, clicked_gap_id) VALUES (?, ?, ?, ?)");
        $stmt->bind_param('sisi', $query, $results_count, $session_hash, $clicked_gap_id);
        $stmt->execute();
        $stmt->close();
        
        echo json_encode(['status' => 'ok', 'query' => $query, 'count' => $count]);
        break;

    case 'get_popular_searches':
        $conn = getDB();
        $result = $conn->query("SELECT query, COUNT(*) as count FROM search_log GROUP BY query ORDER BY count DESC LIMIT 10");
        $searches = [];
        if ($result) {
            while ($row = $result->fetch_assoc()) {
                $searches[] = ['query' => $row['query'], 'count' => intval($row['count'])];
            }
        }
        echo json_encode(['status' => 'ok', 'searches' => $searches]);
        break;

    case 'get_search_count':
        $conn = getDB();
        $query = trim($input['query'] ?? '');
        if (!$query) {
            echo json_encode(['error' => 'No query provided']);
            break;
        }
        $stmt = $conn->prepare("SELECT COUNT(*) as cnt FROM search_log WHERE query = ?");
        $stmt->bind_param('s', $query);
        $stmt->execute();
        $row = $stmt->get_result()->fetch_assoc();
        $stmt->close();
        echo json_encode(['status' => 'ok', 'query' => $query, 'count' => intval($row['cnt'])]);
        break;

    // --- BRIEF SNAPSHOTS ---
    case 'log_brief_snapshot':
        $conn = getDB();
        $query = trim($input['query'] ?? '');
        $signal_count = intval($input['signal_count'] ?? 0);
        if (!$query) {
            echo json_encode(['error' => 'No query provided']);
            break;
        }
        // Create table if not exists
        $conn->query("CREATE TABLE IF NOT EXISTS brief_snapshots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query VARCHAR(255) NOT NULL,
            signal_count INT NOT NULL DEFAULT 0,
            created_at DATE NOT NULL,
            INDEX idx_query_date (query, created_at)
        )");
        // Insert (one per query per day)
        $stmt = $conn->prepare("INSERT INTO brief_snapshots (query, signal_count, created_at) VALUES (?, ?, CURDATE())");
        $stmt->bind_param('si', $query, $signal_count);
        $stmt->execute();
        $stmt->close();
        echo json_encode(['status' => 'ok', 'query' => $query, 'signal_count' => $signal_count]);
        break;

    // --- SUBSCRIBERS ---
    case 'subscribe':
        $conn = getDB();
        $email = trim($input['email'] ?? '');
        $query = trim($input['query'] ?? '');
        if (!$email || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
            echo json_encode(['error' => 'Invalid email']);
            break;
        }
        // Create table if not exists
        $conn->query("CREATE TABLE IF NOT EXISTS subscribers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            query VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_email (email)
        )");
        // Insert (ignore duplicates)
        $stmt = $conn->prepare("INSERT IGNORE INTO subscribers (email, query) VALUES (?, ?)");
        $stmt->bind_param('ss', $email, $query);
        $stmt->execute();
        $stmt->close();
        echo json_encode(['status' => 'ok', 'email' => $email]);
        break;

    // --- BRIEF GENERATION (frontend search) ---
    case 'brief':
        $conn = getDB();
        $query = trim($input['query'] ?? ($_GET['query'] ?? ''));
        if (!$query) {
            echo json_encode(['error' => 'No query provided']);
            break;
        }

        // Search matching signals
        $like = '%' . $query . '%';
        $stmt = $conn->prepare("
            SELECT * FROM signals
            WHERE quality_tier != 'noise'
              AND (title LIKE ? OR content LIKE ? OR product_category LIKE ?)
            ORDER BY urgency_score DESC
            LIMIT 200
        ");
        $stmt->bind_param('sss', $like, $like, $like);
        $stmt->execute();
        $result = $stmt->get_result();
        $all_signals = [];
        while ($row = $result->fetch_assoc()) {
            $all_signals[] = $row;
        }
        $stmt->close();

        // Group by pain_category (complaints only)
        $pain_groups = [];
        $top_wants = [];
        foreach ($all_signals as $s) {
            if (($s['signal_type'] ?? '') === 'want') {
                $top_wants[] = [
                    'content' => mb_substr(str_replace("\n", ' ', $s['content'] ?? ''), 0, 200),
                    'source' => $s['subreddit'] ?? '',
                    'url' => $s['source_url'] ?? '',
                ];
                continue;
            }
            $cat = $s['pain_category'] ?? 'general';
            if ($cat === 'uncategorized' || $cat === '') continue;
            if (!isset($pain_groups[$cat])) {
                $pain_groups[$cat] = ['signals' => [], 'urgencies' => [], 'subreddits' => []];
            }
            $pain_groups[$cat]['signals'][] = $s;
            $pain_groups[$cat]['urgencies'][] = floatval($s['urgency_score'] ?? 0);
            if (!empty($s['subreddit'])) {
                $pain_groups[$cat]['subreddits'][$s['subreddit']] = true;
            }
        }

        // Sort by count descending, build top_complaints
        uasort($pain_groups, function($a, $b) { return count($b['signals']) - count($a['signals']); });
        $top_complaints = [];
        foreach ($pain_groups as $cat => $group) {
            $signals = $group['signals'];
            $avg_urgency = count($group['urgencies']) ? array_sum($group['urgencies']) / count($group['urgencies']) : 0;
            // Pick representative signal (highest urgency)
            $best = $signals[0];
            foreach ($signals as $s) {
                if (floatval($s['urgency_score'] ?? 0) > floatval($best['urgency_score'] ?? 0)) {
                    $best = $s;
                }
            }
            $top_complaints[] = [
                'category' => $cat,
                'avg_urgency' => round($avg_urgency, 2),
                'sample' => mb_substr(str_replace("\n", ' ', $best['content'] ?? ''), 0, 200),
                'sources' => array_keys($group['subreddits']),
                'count' => count($signals),
                'url' => $best['source_url'] ?? '',
            ];
        }

        $signal_count = count($all_signals);

        // Log snapshot for trend tracking (fire-and-forget, don't block response)
        @$snap_stmt = $conn->prepare("CREATE TABLE IF NOT EXISTS brief_snapshots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query VARCHAR(255) NOT NULL,
            signal_count INT NOT NULL DEFAULT 0,
            created_at DATE NOT NULL,
            INDEX idx_query_date (query, created_at)
        )");
        @$snap_stmt->execute();
        @$snap_stmt->close();
        @$snap_stmt = $conn->prepare("INSERT INTO brief_snapshots (query, signal_count, created_at) VALUES (?, ?, CURDATE())");
        @$snap_stmt->bind_param('si', $query, $signal_count);
        @$snap_stmt->execute();
        @$snap_stmt->close();

        echo json_encode([
            'query' => $query,
            'signal_count' => $signal_count,
            'top_complaints' => array_slice($top_complaints, 0, 10),
            'top_wants' => array_slice($top_wants, 0, 10),
        ]);
        break;

    // --- TRENDS ---
    case 'get_signal_trend':
        $conn = getDB();
        $query = trim($input['query'] ?? '');
        if (!$query) {
            echo json_encode(['error' => 'No query provided']);
            break;
        }
        // Ensure table exists
        $conn->query("CREATE TABLE IF NOT EXISTS brief_snapshots (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query VARCHAR(255) NOT NULL,
            signal_count INT NOT NULL DEFAULT 0,
            created_at DATE NOT NULL,
            INDEX idx_query_date (query, created_at)
        )");

        // Last 7 days: sum of signal_count snapshots
        $stmt = $conn->prepare("SELECT COALESCE(SUM(signal_count), 0) as total FROM brief_snapshots WHERE query = ? AND created_at > DATE_SUB(CURDATE(), INTERVAL 7 DAY)");
        $stmt->bind_param('s', $query);
        $stmt->execute();
        $current = intval($stmt->get_result()->fetch_assoc()['total']);
        $stmt->close();

        // Previous 7 days
        $stmt = $conn->prepare("SELECT COALESCE(SUM(signal_count), 0) as total FROM brief_snapshots WHERE query = ? AND created_at BETWEEN DATE_SUB(CURDATE(), INTERVAL 14 DAY) AND DATE_SUB(CURDATE(), INTERVAL 7 DAY)");
        $stmt->bind_param('s', $query);
        $stmt->execute();
        $previous = intval($stmt->get_result()->fetch_assoc()['total']);
        $stmt->close();

        // Calculate trend
        if ($previous === 0) {
            $trend = $current > 0 ? 'growing' : 'stable';
            $change = 0;
        } else {
            $change = round((($current - $previous) / $previous) * 100);
            if ($change >= 20) $trend = 'growing';
            elseif ($change <= -20) $trend = 'fading';
            else $trend = 'stable';
        }

        echo json_encode(['status' => 'ok', 'query' => $query, 'current_7d' => $current, 'previous_7d' => $previous, 'change_pct' => $change, 'trend' => $trend]);
        break;

    // --- GAPS ---
    case 'insert_gap':
        $conn = getDB();
        $stmt = $conn->prepare("
            INSERT INTO gaps (title, slug, description, evidence_count, heat_score, category, source_types, signal_ids, sample_quotes, competitors)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE title=VALUES(title), description=VALUES(description),
                evidence_count=VALUES(evidence_count), heat_score=VALUES(heat_score),
                category=VALUES(category), source_types=VALUES(source_types),
                signal_ids=VALUES(signal_ids), sample_quotes=VALUES(sample_quotes),
                competitors=VALUES(competitors),
                updated_at=NOW()
        ");
        $title = $input['title'] ?? '';
        $slug = $input['slug'] ?? '';
        $description = $input['description'] ?? '';
        $evidence_count = intval($input['evidence_count'] ?? 0);
        $heat_score = floatval($input['heat_score'] ?? 0);
        $category = $input['category'] ?? 'uncategorized';
        $source_types = isset($input['source_types']) ? json_encode($input['source_types']) : '[]';
        $signal_ids = isset($input['signal_ids']) ? json_encode($input['signal_ids']) : '[]';
        $sample_quotes = isset($input['sample_quotes']) ? json_encode($input['sample_quotes']) : '[]';
        $competitors = isset($input['competitors']) ? json_encode($input['competitors']) : 'null';
        $stmt->bind_param('sssdisssss',
            $title, $slug, $description, $evidence_count, $heat_score,
            $category, $source_types, $signal_ids, $sample_quotes, $competitors
        );
        if ($stmt->execute()) {
            $id = $conn->insert_id ?: $conn->query("SELECT id FROM gaps WHERE slug = '" . $conn->real_escape_string($slug) . "'")->fetch_assoc()['id'];
            echo json_encode(['success' => true, 'id' => intval($id)]);
        } else {
            http_response_code(500);
            echo json_encode(['error' => $stmt->error]);
        }
        $stmt->close();
        break;

    case 'delete_gaps':
        $conn = getDB();
        $conn->query("DELETE FROM gaps");
        echo json_encode(['ok' => true, 'deleted' => $conn->affected_rows]);
        break;

    case 'reset_validation':
        $conn = getDB();
        $conn->query("UPDATE gaps SET competitors = NULL, gap_validity = 'unvalidated', last_validated_at = NULL, opportunity_score = NULL");
        echo json_encode(['ok' => true, 'reset' => $conn->affected_rows]);
        break;

    case 'update_gap_competitors':
        $conn = getDB();
        $gap_id = intval($input['gap_id'] ?? 0);
        $competitors = $input['competitors'] ?? [];
        $gap_validity = $input['gap_validity'] ?? 'unvalidated';
        $opportunity_score = $input['opportunity_score'] ?? null;
        
        if (!$gap_id) {
            echo json_encode(['error' => 'No gap_id provided']);
            break;
        }
        
        if ($opportunity_score !== null) {
            $stmt = $conn->prepare("UPDATE gaps SET competitors = ?, gap_validity = ?, opportunity_score = ?, last_validated_at = NOW() WHERE id = ?");
            $competitors_json = json_encode($competitors);
            $os = floatval($opportunity_score);
            $stmt->bind_param('ssdi', $competitors_json, $gap_validity, $os, $gap_id);
        } else {
            $stmt = $conn->prepare("UPDATE gaps SET competitors = ?, gap_validity = ?, last_validated_at = NOW() WHERE id = ?");
            $competitors_json = json_encode($competitors);
            $stmt->bind_param('ssi', $competitors_json, $gap_validity, $gap_id);
        }
        $stmt->execute();
        
        if ($stmt->affected_rows > 0) {
            echo json_encode(['ok' => true, 'gap_id' => $gap_id, 'competitors' => $competitors]);
        } else {
            echo json_encode(['error' => 'Gap not found or no changes made']);
        }
        $stmt->close();
        $conn->close();
        break;

    case 'get_gaps':
        $conn = getDB();
        $where = ["1=1"];
        $params = [];
        $types = '';

        if (!empty($_GET['category'])) {
            $where[] = "category = ?";
            $params[] = $_GET['category'];
            $types .= 's';
        }
        if (!empty($_GET['status'])) {
            $where[] = "status = ?";
            $params[] = $_GET['status'];
            $types .= 's';
        } else {
            $where[] = "status = 'active'";
        }

        $limit = intval($_GET['limit'] ?? 50);
        $offset = intval($_GET['offset'] ?? 0);

        // Count total
        $count_sql = "SELECT COUNT(*) as cnt FROM gaps WHERE " . implode(' AND ', $where);
        $count_stmt = $conn->prepare($count_sql);
        if ($types) {
            $count_stmt->bind_param($types, ...$params);
        }
        $count_stmt->execute();
        $total = intval($count_stmt->get_result()->fetch_assoc()['cnt']);
        $count_stmt->close();

        // Fetch rows
        $sql = "SELECT * FROM gaps WHERE " . implode(' AND ', $where) . " ORDER BY heat_score DESC, created_at DESC LIMIT ? OFFSET ?";
        $stmt = $conn->prepare($sql);
        $types .= 'ii';
        $params[] = $limit;
        $params[] = $offset;
        $stmt->bind_param($types, ...$params);
        $stmt->execute();
        $result = $stmt->get_result();
        $rows = [];
        while ($row = $result->fetch_assoc()) {
            $row['source_types'] = json_decode($row['source_types'], true) ?? [];
            $row['signal_ids'] = json_decode($row['signal_ids'], true) ?? [];
            $row['sample_quotes'] = json_decode($row['sample_quotes'], true) ?? [];
            $rows[] = $row;
        }
        echo json_encode(['gaps' => $rows, 'total' => $total]);
        $stmt->close();
        break;

    case 'get_gap_by_slug':
        $conn = getDB();
        $slug = $_GET['slug'] ?? '';
        if (!$slug) {
            http_response_code(400);
            echo json_encode(['error' => 'No slug provided']);
            break;
        }
        $stmt = $conn->prepare("SELECT * FROM gaps WHERE slug = ?");
        $stmt->bind_param('s', $slug);
        $stmt->execute();
        $result = $stmt->get_result();
        $row = $result->fetch_assoc();
        if ($row) {
            $row['source_types'] = json_decode($row['source_types'], true) ?? [];
            $row['signal_ids'] = json_decode($row['signal_ids'], true) ?? [];
            $row['sample_quotes'] = json_decode($row['sample_quotes'], true) ?? [];
        }
        echo json_encode(['gap' => $row]);
        $stmt->close();
        break;

    case 'update_gap':
        $conn = getDB();
        $id = intval($input['id'] ?? 0);
        if (!$id) {
            http_response_code(400);
            echo json_encode(['error' => 'No id provided']);
            break;
        }
        $sets = [];
        $params = [];
        $types = '';

        $allowed = ['title', 'slug', 'description', 'evidence_count', 'heat_score', 'category',
                     'source_types', 'signal_ids', 'sample_quotes', 'status', 'competitors'];
        foreach ($allowed as $field) {
            if (array_key_exists($field, $input)) {
                $sets[] = "$field = ?";
                if ($field === 'evidence_count') {
                    $params[] = intval($input[$field]);
                    $types .= 'i';
                } elseif ($field === 'heat_score') {
                    $params[] = floatval($input[$field]);
                    $types .= 'd';
                } elseif (in_array($field, ['source_types', 'signal_ids', 'sample_quotes', 'competitors'])) {
                    $params[] = json_encode($input[$field]);
                    $types .= 's';
                } else {
                    $params[] = $input[$field];
                    $types .= 's';
                }
            }
        }
        if (empty($sets)) {
            http_response_code(400);
            echo json_encode(['error' => 'No fields to update']);
            break;
        }
        $params[] = $id;
        $types .= 'i';
        $sql = "UPDATE gaps SET " . implode(', ', $sets) . ", updated_at = NOW() WHERE id = ?";
        $stmt = $conn->prepare($sql);
        $stmt->bind_param($types, ...$params);
        $stmt->execute();
        echo json_encode(['success' => true, 'affected' => $stmt->affected_rows]);
        $stmt->close();
        break;

    case 'delete_gap':
        $conn = getDB();
        $id = intval($input['id'] ?? 0);
        if (!$id) {
            http_response_code(400);
            echo json_encode(['error' => 'No id provided']);
            break;
        }
        $stmt = $conn->prepare("UPDATE gaps SET status = 'stale', updated_at = NOW() WHERE id = ?");
        $stmt->bind_param('i', $id);
        $stmt->execute();
        echo json_encode(['success' => true, 'affected' => $stmt->affected_rows]);
        $stmt->close();
        break;

    case 'gap_count':
        $conn = getDB();
        $where = ["1=1"];
        $params = [];
        $types = '';

        if (!empty($_GET['category'])) {
            $where[] = "category = ?";
            $params[] = $_GET['category'];
            $types .= 's';
        }
        if (!empty($_GET['status'])) {
            $where[] = "status = ?";
            $params[] = $_GET['status'];
            $types .= 's';
        } else {
            $where[] = "status = 'active'";
        }

        $sql = "SELECT COUNT(*) as cnt FROM gaps WHERE " . implode(' AND ', $where);
        $stmt = $conn->prepare($sql);
        if ($types) {
            $stmt->bind_param($types, ...$params);
        }
        $stmt->execute();
        $row = $stmt->get_result()->fetch_assoc();
        echo json_encode(['total' => intval($row['cnt'])]);
        $stmt->close();
        break;

    case 'aggregate_analytics':
        $conn = getDB();
        $date = $input['date'] ?? date('Y-m-d', strtotime('-1 day'));

        // Ensure gap_engagement has slug column
        $col_check = $conn->query("SHOW COLUMNS FROM gap_engagement LIKE 'gap_slug'");
        if ($col_check->num_rows === 0) {
            $conn->query("ALTER TABLE gap_engagement ADD COLUMN gap_slug VARCHAR(255) AFTER gap_id");
            $conn->query("ALTER TABLE gap_engagement ADD UNIQUE KEY unique_slug_date (gap_slug, date)");
        }

        // 1. Aggregate gap_engagement from page_views
        $stmt = $conn->prepare("
            INSERT INTO gap_engagement (gap_slug, date, views, unique_visitors)
            SELECT
                page_path,
                DATE(created_at) as view_date,
                COUNT(*) as views,
                COUNT(DISTINCT session_hash) as unique_visitors
            FROM page_views
            WHERE DATE(created_at) = ?
                AND page_type = 'gap'
                AND page_path != ''
            GROUP BY page_path, DATE(created_at)
            ON DUPLICATE KEY UPDATE
                views = VALUES(views),
                unique_visitors = VALUES(unique_visitors)
        ");
        $stmt->bind_param('s', $date);
        $stmt->execute();
        $gap_count = $stmt->affected_rows;
        $stmt->close();

        // 2. Top searches
        $stmt = $conn->prepare("
            SELECT query_text as query, COUNT(*) as cnt
            FROM search_queries
            WHERE DATE(created_at) = ? AND query_text != ''
            GROUP BY query_text
            ORDER BY cnt DESC
            LIMIT 20
        ");
        $stmt->bind_param('s', $date);
        $stmt->execute();
        $result = $stmt->get_result();
        $top_searches = [];
        while ($row = $result->fetch_assoc()) {
            $top_searches[] = $row;
        }
        $stmt->close();

        // 3. Zero-result searches (potential new gaps)
        $stmt = $conn->prepare("
            SELECT query_text as query, COUNT(*) as cnt
            FROM search_queries
            WHERE DATE(created_at) = ? AND query_text != ''
                AND results_count = 0
            GROUP BY query_text
            ORDER BY cnt DESC
            LIMIT 20
        ");
        $stmt->bind_param('s', $date);
        $stmt->execute();
        $result = $stmt->get_result();
        $zero_searches = [];
        while ($row = $result->fetch_assoc()) {
            $zero_searches[] = $row;
        }
        $stmt->close();

        // 4. Session metrics
        $stmt = $conn->prepare("
            SELECT
                COUNT(DISTINCT session_hash) as total_visitors,
                COUNT(*) as total_pageviews
            FROM page_views
            WHERE DATE(created_at) = ?
        ");
        $stmt->bind_param('s', $date);
        $stmt->execute();
        $session = $stmt->get_result()->fetch_assoc();
        $stmt->close();

        // 5. Trending gaps (most viewed today)
        $stmt = $conn->prepare("
            SELECT page_path, COUNT(*) as views
            FROM page_views
            WHERE DATE(created_at) = ? AND page_type = 'gap' AND page_path != ''
            GROUP BY page_path
            ORDER BY views DESC
            LIMIT 10
        ");
        $stmt->bind_param('s', $date);
        $stmt->execute();
        $result = $stmt->get_result();
        $trending = [];
        while ($row = $result->fetch_assoc()) {
            $trending[] = $row;
        }
        $stmt->close();

        echo json_encode([
            'ok' => true,
            'date' => $date,
            'gaps_aggregated' => $gap_count,
            'top_searches' => $top_searches,
            'zero_result_searches' => $zero_searches,
            'session_metrics' => $session,
            'trending_gaps' => $trending
        ]);
        break;

    case 'reset_classifications':
        authenticate();
        $conn = getDB();
        $stmt = $conn->prepare("UPDATE signals SET is_processed = 0, quality_tier = NULL");
        $stmt->execute();
        $affected = $stmt->affected_rows;
        $stmt->close();
        echo json_encode(['ok' => true, 'reset' => $affected]);
        break;

    // --- GRAPH DATA ENDPOINTS (NEW) ---

    case 'source_distribution':
        $conn = getDB();
        
        // Get total count of non-noise signals
        $total_stmt = $conn->prepare("SELECT COUNT(*) as total FROM signals WHERE quality_tier != 'noise'");
        $total_stmt->execute();
        $total_row = $total_stmt->get_result()->fetch_assoc();
        $total_signals = intval($total_row['total']);
        $total_stmt->close();

        if ($total_signals === 0) {
            echo json_encode(['sources' => []]);
            break;
        }

        // Get source distribution
        $stmt = $conn->prepare("
            SELECT source, COUNT(*) AS count
            FROM signals
            WHERE quality_tier != 'noise'
            GROUP BY source
            ORDER BY count DESC
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        $sources = [];
        while ($row = $result->fetch_assoc()) {
            $count = intval($row['count']);
            $percentage = round(($count / $total_signals) * 100, 1);
            $sources[] = [
                'source' => $row['source'],
                'count' => $count,
                'percentage' => $percentage
            ];
        }
        $stmt->close();

        echo json_encode(['sources' => $sources]);
        break;

    case 'sentiment_breakdown':
        $conn = getDB();
        $total_signals = 0;
        $breakdown = ['negative' => 0, 'neutral' => 0, 'positive' => 0];
        $allowed_sentiments = ['positive', 'negative', 'neutral'];

        // Get counts, ensuring we only include relevant sentiments for the sum total
        $stmt = $conn->prepare("
            SELECT sentiment, COUNT(*) as count
            FROM signals
            WHERE quality_tier != 'noise' AND sentiment IN ('positive', 'negative', 'neutral')
            GROUP BY sentiment
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        while ($row = $result->fetch_assoc()) {
            $sentiment = strtolower($row['sentiment']);
            if (in_array($sentiment, $allowed_sentiments)) {
                $count = intval($row['count']);
                $breakdown[$sentiment] = $count;
                $total_signals += $count;
            }
        }
        $stmt->close();
        
        // NOTE: If total signals should include other sentiments, this logic needs adjustment. Sticking to summing buckets as per example implied structure.
        echo json_encode(['breakdown' => $breakdown, 'total' => $total_signals]);
        break;

    case 'buyer_intent_distribution':
        $conn = getDB();
        $distribution = ['high' => 0, 'medium' => 0, 'low' => 0];
        $total_signals = 0;

        // Use CASE statement for bucketizing buyer_intent (0.0 to 1.0)
        $stmt = $conn->prepare("
            SELECT
                CASE
                    WHEN buyer_intent > 0.66 THEN 'high'
                    WHEN buyer_intent > 0.33 THEN 'medium'
                    WHEN buyer_intent > 0 THEN 'low'
                    ELSE 'zero'
                END AS intent_bucket,
                COUNT(*) as count
            FROM signals
            WHERE quality_tier != 'noise' AND buyer_intent >= 0
            GROUP BY intent_bucket
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        while ($row = $result->fetch_assoc()) {
            $bucket = $row['intent_bucket'];
            $count = intval($row['count']);
            if (in_array($bucket, ['high', 'medium', 'low'])) {
                $distribution[$bucket] = $count;
                $total_signals += $count;
            }
        }
        $stmt->close();

        echo json_encode(['distribution' => $distribution, 'total' => $total_signals]);
        break;

    case 'top_gaps_velocity':
        $conn = getDB();
        $stmt = $conn->prepare("
            SELECT 
                id, title, slug, heat_score, evidence_count, category
            FROM gaps
            WHERE status = 'active'
            ORDER BY evidence_count DESC
            LIMIT 10
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        $gaps = [];
        while ($row = $result->fetch_assoc()) {
            $gaps[] = [
                'id' => intval($row['id']),
                'title' => $row['title'],
                'slug' => $row['slug'],
                'heat_score' => floatval($row['heat_score']),
                'evidence_count' => intval($row['evidence_count']),
                'category' => $row['category']
            ];
        }
        echo json_encode(['gaps' => $gaps]);
        $stmt->close();
        break;

    case 'uptime':
        $conn = getDB();

        // 1. Get all distinct sources that have logged a scan in the last 7 days
        $source_stmt = $conn->prepare("
            SELECT DISTINCT source FROM scan_log
            WHERE started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ");
        $source_stmt->execute();
        $source_result = $source_stmt->get_result();
        $logged_sources = [];
        while ($row = $source_result->fetch_assoc()) {
            $logged_sources[] = $row['source'];
        }
        $source_stmt->close();
        
        // 2. Always include all known sources
        $all_sources = ['reddit', 'hackernews', 'stackoverflow', 'devto', 'youtube', 'web_search', 'rss'];
        // Add any logged sources not in our known list
        foreach ($logged_sources as $ls) {
            if (!in_array($ls, $all_sources)) {
                $all_sources[] = $ls;
            }
        }
        
        $uptime_data = [];
        foreach ($all_sources as $source) {
            $uptime_data[$source] = array_fill(0, 14, false);
        }

        if (empty($logged_sources)) {
            echo json_encode(['sources' => $uptime_data]);
            break;
        }

        // 2. Check for scans across 14 half-day slots (i=0 is Day 7 ago 00:00-11:59, i=13 is Today 12:00-23:59)
        for ($i = 0; $i < 14; $i++) {
            // d: days ago (0 to 6)
            $d = floor($i / 2); 
            // h: half-day index (0 for 00:00-11:59:59, 1 for 12:00-23:59:59)
            $h = $i % 2; 
            
            $start_H = $h * 12;
            $end_H = ($h + 1) * 12;
            
            // Define the boundaries for the 12-hour block based on the day $d days ago
            $day_start = "DATE_SUB(CURDATE(), INTERVAL $d DAY)";
            $day_end = "DATE_ADD(DATE_SUB(CURDATE(), INTERVAL $d DAY), INTERVAL 24 HOUR)";

            $window_start = "DATE_ADD(DATE_SUB(CURDATE(), INTERVAL $d DAY), INTERVAL $start_H HOUR)";
            $window_end = "DATE_ADD(DATE_SUB(CURDATE(), INTERVAL $d DAY), INTERVAL $end_H HOUR)";

            foreach ($all_sources as $source) {
                $check_stmt = $conn->prepare("
                    SELECT 1 FROM scan_log
                    WHERE source = ?
                      AND started_at >= $window_start
                      AND started_at < $window_end
                      AND completed_at IS NOT NULL
                    LIMIT 1
                ");
                
                $check_stmt->bind_param('s', $source);
                $check_stmt->execute();
                $is_scanned = $check_stmt->get_result()->num_rows > 0;
                $check_stmt->close();
                
                $uptime_data[$source][$i] = $is_scanned;
            }
        }


        echo json_encode(['sources' => $uptime_data]);
        break;

    // --- END NEW ENDPOINTS ---

    case 'sparklines':
        // Lightweight: returns signal timestamps per gap for sparkline rendering
        $conn = getDB();
        
        // Get all gaps with signal_ids
        $stmt = $conn->prepare("SELECT id, slug, signal_ids FROM gaps WHERE status = 'active'");
        $stmt->execute();
        $result = $stmt->get_result();
        
        $gaps = [];
        $allSignalIds = [];
        while ($row = $result->fetch_assoc()) {
            $signalIds = json_decode($row['signal_ids'], true) ?: [];
            $gaps[$row['id']] = ['slug' => $row['slug'], 'signal_ids' => $signalIds];
            $allSignalIds = array_merge($allSignalIds, $signalIds);
        }
        $stmt->close();
        
        // Deduplicate and fetch timestamps
        $allSignalIds = array_unique($allSignalIds);
        $sparklines = [];
        
        if (!empty($allSignalIds)) {
            $idList = implode(',', array_map('intval', $allSignalIds));
            $result2 = $conn->query("SELECT id, created_at FROM signals WHERE id IN ($idList)");
            
            $signalTimes = [];
            while ($row = $result2->fetch_assoc()) {
                $signalTimes[$row['id']] = $row['created_at'];
            }
            
            // Build sparklines
            foreach ($gaps as $gapId => $gap) {
                $timestamps = [];
                foreach ($gap['signal_ids'] as $sid) {
                    if (isset($signalTimes[(int)$sid])) {
                        $timestamps[] = $signalTimes[(int)$sid];
                    }
                }
                sort($timestamps);
                $sparklines[$gapId] = [
                    'slug' => $gap['slug'],
                    'timestamps' => array_slice($timestamps, -20) // Last 20 timestamps max
                ];
            }
        }
        
        echo json_encode($sparklines);
        $conn->close();
        break;


    case 'signal_velocity':
        $conn = getDB();
        $days = isset($_GET['days']) ? intval($_GET['days']) : 30;
        $stmt = $conn->prepare("
            SELECT DATE(collected_at) as day, COUNT(*) as count
            FROM signals
            WHERE collected_at >= DATE_SUB(NOW(), INTERVAL ? DAY)
              AND quality_tier != 'noise'
            GROUP BY DATE(collected_at)
            ORDER BY day ASC
        ");
        $stmt->bind_param('i', $days);
        $stmt->execute();
        $result = $stmt->get_result();
        $data = [];
        while ($row = $result->fetch_assoc()) {
            $data[] = ['date' => $row['day'], 'count' => intval($row['count'])];
        }
        $stmt->close();
        echo json_encode(['velocity' => $data, 'days' => $days]);
        break;

    case 'category_breakdown':
        $conn = getDB();
        $stmt = $conn->prepare("
            SELECT pain_category, COUNT(*) as count,
                   AVG(urgency_score) as avg_urgency,
                   AVG(buyer_intent) as avg_intent
            FROM signals
            WHERE quality_tier != 'noise' AND pain_category != '' AND pain_category != 'uncategorized'
            GROUP BY pain_category
            ORDER BY count DESC
            LIMIT 15
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        $data = [];
        while ($row = $result->fetch_assoc()) {
            $data[] = [
                'category' => $row['pain_category'],
                'count' => intval($row['count']),
                'avg_urgency' => round(floatval($row['avg_urgency']), 2),
                'avg_intent' => round(floatval($row['avg_intent']), 2)
            ];
        }
        $stmt->close();
        echo json_encode(['categories' => $data]);
        break;

    case 'heat_distribution':
        $conn = getDB();
        $stmt = $conn->prepare("
            SELECT
                CASE
                    WHEN heat_score >= 0.8 THEN 'critical'
                    WHEN heat_score >= 0.6 THEN 'hot'
                    WHEN heat_score >= 0.4 THEN 'warm'
                    WHEN heat_score >= 0.2 THEN 'cool'
                    ELSE 'cold'
                END as bucket,
                COUNT(*) as count
            FROM gaps WHERE status = 'active'
            GROUP BY bucket
            ORDER BY FIELD(bucket, 'critical', 'hot', 'warm', 'cool', 'cold')
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        $data = [];
        while ($row = $result->fetch_assoc()) {
            $data[] = ['bucket' => $row['bucket'], 'count' => intval($row['count'])];
        }
        $stmt->close();

        // Also get avg heat and top 5 by heat
        $avg_stmt = $conn->prepare("SELECT AVG(heat_score) as avg_heat, MAX(heat_score) as max_heat FROM gaps WHERE status = 'active'");
        $avg_stmt->execute();
        $avg_row = $avg_stmt->get_result()->fetch_assoc();
        $avg_stmt->close();

        echo json_encode([
            'distribution' => $data,
            'avg_heat' => round(floatval($avg_row['avg_heat']), 2),
            'max_heat' => round(floatval($avg_row['max_heat']), 2)
        ]);
        break;

    case 'source_trend':
        $conn = getDB();
        $stmt = $conn->prepare("
            SELECT DATE(collected_at) as day, source, COUNT(*) as count
            FROM signals
            WHERE collected_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
              AND quality_tier != 'noise'
            GROUP BY DATE(collected_at), source
            ORDER BY day ASC, count DESC
        ");
        $stmt->execute();
        $result = $stmt->get_result();
        $data = [];
        while ($row = $result->fetch_assoc()) {
            $data[] = [
                'date' => $row['day'],
                'source' => $row['source'],
                'count' => intval($row['count'])
            ];
        }
        $stmt->close();
        echo json_encode(['trends' => $data]);
        break;

    default:
        http_response_code(400);
        echo json_encode(['error' => 'Unknown action: ' . $action]);
        break;
}
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage(), 'trace' => $e->getTraceAsString()]);
}
