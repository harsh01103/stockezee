lines = open('runner.py','r',encoding='utf-8').readlines()
for i,l in enumerate(lines):
    ll = l.lower()
    if 'telegram' in ll or 'execute' in ll or '.post(' in ll or 'webhook' in ll:
        print(f'{i+1}: {l.rstrip()[:120].encode("ascii","replace").decode()}')
