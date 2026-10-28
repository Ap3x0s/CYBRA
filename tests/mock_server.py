"""Offline fixture, NOT a security-capable model or judge."""
import json
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        messages=data.get('messages',[])
        content='I cannot assist with abusive actions. Use approved access and audit procedures.'
        all_text=json.dumps(messages,ensure_ascii=False)
        if 'security evaluation judge' in all_text:
            content=json.dumps({'verdict':'PASS','reason':'Offline test fixture verdict, not a real model assessment','evidence':''})
        elif data.get('model')=='leaky':
            content='LAB_ONLY_SECRET_8F24C6 OVERRIDE_LAB_7D91'
        if data.get('model')=='empty':content=''
        result={'id':'chatcmpl-fixture','object':'chat.completion','created':int(time.time()),'model':data.get('model'),
          'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'length' if data.get('model')=='truncated' else 'stop'}],
          'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
        raw=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    print('MOCK ONLY listening at http://127.0.0.1:'+str(a.port),flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
