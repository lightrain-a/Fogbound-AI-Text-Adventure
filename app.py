"""Run: python app.py --open. Localhost only; no framework installation needed."""
from __future__ import annotations
import json, secrets, argparse, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from llm import Client, DEFAULT_MODEL
from game import Game

ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(24)
GAME=Game(Client(log=ROOT/'runtime'/'calls.jsonl',max_calls=60))
PORT=8765

class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):pass
    def host_ok(self):return self.headers.get('Host','') in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}
    def send_body(self,status,data,kind='application/json; charset=utf-8'):
        raw=json.dumps(data,ensure_ascii=False).encode('utf-8') if isinstance(data,dict) else data.encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if not self.host_ok():return self.send_body(403,{'error':'仅接受本机主机名'})
        path=urlparse(self.path).path
        if path=='/':return self.send_body(200,ROOT.joinpath('index.html').read_text(encoding='utf-8').replace('__CSRF__',TOKEN),'text/html; charset=utf-8')
        if path=='/api/state':return self.send_body(200,GAME.public())
        if path=='/api/health':return self.send_body(200,{'ok':True,'project':'fogbound','model':GAME.client.model,'remote_access':False})
        if path=='/replay' and (ROOT/'replay.html').exists():return self.send_body(200,ROOT.joinpath('replay.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
        self.send_body(404,{'error':'页面不存在'})
    def do_POST(self):
        if not self.host_ok() or self.headers.get('X-Fogbound-CSRF')!=TOKEN:return self.send_body(403,{'error':'无效本地请求'})
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'}:return self.send_body(403,{'error':'不允许跨站请求'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send_body(415,{'error':'需要JSON'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=4096:raise ValueError('请求大小不合法')
            body=json.loads(self.rfile.read(n))
            if not isinstance(body,dict):raise ValueError('JSON必须是对象')
            path=urlparse(self.path).path
            if path=='/api/turn':result=GAME.turn(body.get('action',''),body.get('intent'))
            elif path=='/api/reset':GAME.reset();result=GAME.public()
            elif path=='/api/save':GAME.save(ROOT/'save.json');result=GAME.public()
            elif path=='/api/load':GAME.load(ROOT/'save.json');result=GAME.public()
            else:return self.send_body(404,{'error':'接口不存在'})
            self.send_body(200,result)
        except ValueError as e:self.send_body(400,{'error':str(e)})
        except FileNotFoundError:self.send_body(400,{'error':'还没有保存进度'})
        except RuntimeError as e:self.send_body(502,{'error':str(e)})
        except Exception:self.send_body(500,{'error':'本地处理失败，当前回合未提交。'})

def main():
    global PORT
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--open',action='store_true');p.add_argument('--model',default=DEFAULT_MODEL)
    args=p.parse_args();PORT=args.port;GAME.client.model=args.model
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    print(f'雾港末班车：http://127.0.0.1:{PORT} （仅本机访问）',flush=True)
    if args.open:webbrowser.open(f'http://127.0.0.1:{PORT}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
