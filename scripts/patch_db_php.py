with open(r'C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to insert - right before the default case
marker = "default:"
idx = content.find(marker)
if idx > 0:
    # Find the actual 'default:' that's a switch case
    # Go back to find the start of the line
    line_start = content.rfind('\n', 0, idx)
    
    new_action = """    case 'reset_classifications':
        authenticate();
        $conn = getDB();
        $stmt = $conn->prepare("UPDATE signals SET is_processed = 0, quality_tier = NULL");
        $stmt->execute();
        $affected = $stmt->affected_rows;
        $stmt->close();
        echo json_encode(['ok' => true, 'reset' => $affected]);
        break;

"""
    content = content[:line_start+1] + new_action + content[line_start+1:]
    
    with open(r'C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Added reset_classifications action at line position {line_start}')
else:
    print('Could not find default case')
