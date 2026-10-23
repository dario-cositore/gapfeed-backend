with open(r'C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find("case 'get_signals':")
if idx >= 0:
    lines = content[idx:].split('\n')[:60]
    for i, line in enumerate(lines):
        print(f'{i}: {line}')
else:
    print('get_signals not found')
