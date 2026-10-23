import re

with open(r"C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php", 'r', encoding='utf-8') as f:
    content = f.read()

new_endpoints = '''
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

'''

# Insert before the default case
marker = "    default:"
if marker in content:
    content = content.replace(marker, new_endpoints + marker)
    print("Added 4 new endpoints")
else:
    print("Could not find default case marker")

with open(r"C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php", 'w', encoding='utf-8') as f:
    f.write(content)

# Also add the new actions to the public_actions list
old_public = "$public_actions = ['brief', 'log_search', 'get_search_count', 'subscribe', 'get_signal_trend', 'get_popular_searches', 'get_gaps', 'get_gap_by_slug', 'get_gap_quotes', 'get_related_gaps', 'search_gaps', 'search_signals', 'signal_count', 'source_distribution', 'sentiment_breakdown', 'buyer_intent_distribution', 'top_gaps_velocity', 'uptime', 'sparklines', 'get_categories', 'get_category_gaps', 'get_sources', 'get_source_gaps'];"
new_public = "$public_actions = ['brief', 'log_search', 'get_search_count', 'subscribe', 'get_signal_trend', 'get_popular_searches', 'get_gaps', 'get_gap_by_slug', 'get_gap_quotes', 'get_related_gaps', 'search_gaps', 'search_signals', 'signal_count', 'source_distribution', 'sentiment_breakdown', 'buyer_intent_distribution', 'top_gaps_velocity', 'uptime', 'sparklines', 'get_categories', 'get_category_gaps', 'get_sources', 'get_source_gaps', 'signal_velocity', 'category_breakdown', 'heat_distribution', 'source_trend'];"

with open(r"C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php", 'r', encoding='utf-8') as f:
    content = f.read()

if old_public in content:
    content = content.replace(old_public, new_public)
    print("Updated public_actions list")

with open(r"C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php", 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
