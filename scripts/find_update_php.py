with open(r'C:\Users\cosit\.openclaw\workspace\gapfeed\api\db.php', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find("case 'update_signal':")
if idx >= 0:
    lines = content[idx:].split('\n')[:60]
    for i, line in enumerate(lines):
        print(f'{i}: {line}')
else:
    print('update_signal case not found')
    # search for update
    for i, line in enumerate(content.split('\n')):
        if 'update_signal' in line:
            print(f'{i}: {line}')
