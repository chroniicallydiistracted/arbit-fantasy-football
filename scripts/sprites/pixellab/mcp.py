"""Minimal PixelLab MCP client: reads the key from Claude Code's local config, never prints it.
Usage: python3 mcp.py TOOL '{"json": "args"}' [outdir]. Text results print; images save to outdir."""
import base64, json, sys, urllib.request, pathlib
cfg = json.load(open('/home/andre/.claude.json'))
server = cfg['projects']['/home/andre/arbit-fantasy-football']['mcpServers']['pixellab']
URL, AUTH = server['url'], server['headers']['Authorization']
sid = None
def rpc(body, notify=False, timeout=120):
    global sid
    h = {'Authorization': AUTH, 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if sid: h['Mcp-Session-Id'] = sid
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get('Mcp-Session-Id') or sid
        text = r.read().decode()
    if notify or not text.strip(): return None
    if text.lstrip().startswith('{'): return json.loads(text)
    result = None
    for line in text.splitlines():
        if line.startswith('data:'): result = json.loads(line[5:])
    return result
def call(name, args, out=None, timeout=300):
    rpc({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'arbit','version':'0'}}})
    rpc({'jsonrpc':'2.0','method':'notifications/initialized'}, notify=True)
    res = rpc({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':args}}, timeout=timeout)
    if 'error' in res: print('ERROR', json.dumps(res['error'])[:2000]); return res
    n = 0
    for item in res['result'].get('content', []):
        if item.get('type') == 'text': print(item['text'])
        elif item.get('type') == 'image' and out:
            n += 1; p = pathlib.Path(out) / f'{name}-{n}.png'; p.write_bytes(base64.b64decode(item['data'])); print('saved', p)
    return res
if __name__ == '__main__':
    call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}, sys.argv[3] if len(sys.argv) > 3 else None)
