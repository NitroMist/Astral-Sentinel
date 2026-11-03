"""Local-only HTTP server for Astral Sentinel. AGPL-3.0-or-later."""
from __future__ import annotations
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import json
import mimetypes
import os
import sys
import threading
import webbrowser

from engine import forecast, snapshot, parse_datetime, now_utc
from profile_manager import (list_profiles,create_profile,switch_profile,update_profile,
                             delete_profile,import_profile,export_profile)
from city_lookup import search_cities
from observation_log import read_log, create_entry, delete_entry, send_to_joplin, find_joplin_port

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
DEFAULT_PORT=int(os.environ.get('ASTRAL_PORT','8765'))
MIMES={'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.json':'application/json'}


def _is_local_request(host, origin, port):
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    return (host in allowed_hosts and
            (not origin or origin in {f'http://{name}' for name in allowed_hosts}))

class Handler(BaseHTTPRequestHandler):
    server_version='AstralSentinel/1.0.0'
    def log_message(self,fmt,*args):
        print('[Astral]',fmt%args)
    def reply(self,code,payload):
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'")
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        # Reject DNS rebinding and cross-site requests even for read-only APIs.
        if not _is_local_request(self.headers.get('Host', ''), self.headers.get('Origin', ''), DEFAULT_PORT):
            return self.reply(403, {'error':'Use the local Astral Sentinel address.'})
        path=urlsplit(self.path)
        q=parse_qs(path.query)
        def val(name,default=None):return q.get(name,[default])[0]
        try:
            if path.path=='/api/health':return self.reply(200,{'ok':True,'version':'1.0.0','online_required':False})
            if path.path=='/api/profiles':return self.reply(200,list_profiles(ROOT))
            if path.path=='/api/profile/export':return self.reply(200,export_profile(ROOT,val('id','')))
            if path.path=='/api/cities':return self.reply(200,{'cities':search_cities(val('q',''))})
            if path.path=='/api/observations': return self.reply(200,{'entries':read_log(ROOT)})
            if path.path=='/api/joplin/status':
                port=find_joplin_port()
                return self.reply(200,{'available':port is not None,'port':port,'message':'Joplin Web Clipper detected.' if port else 'Joplin not detected. Start Joplin and enable Web Clipper.'})
            if path.path=='/api/snapshot':
                result=snapshot(parse_datetime(val('at')),val('house','placidus'),val('zodiac','tropical'),house_method=val('house_method','longitude'),node_mode=val('node_mode','mean'),lilith_mode=val('lilith_mode','mean'),aux_orb=float(val('aux_orb','2.0')),aux_scoring=val('aux_scoring','true')=='true')
                return self.reply(200,result)
            if path.path=='/api/forecast':
                result=forecast(parse_datetime(val('at')),int(val('days','30')),
                                val('house','placidus'),val('zodiac','tropical'),val('house_method','longitude'),val('node_mode','mean'),val('lilith_mode','mean'),val('aux_scoring','true')=='true')
                return self.reply(200,result)
            relative='index.html' if path.path=='/' else path.path.lstrip('/')
            requested=(STATIC/relative).resolve()
            if not requested.is_relative_to(STATIC.resolve()) or not requested.is_file():
                return self.reply(404,{'error':'Not found'})
            body=requested.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',MIMES.get(requested.suffix,mimetypes.guess_type(str(requested))[0] or 'application/octet-stream'))
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(body)
        except (ValueError,KeyError,OverflowError) as exc:
            self.reply(400,{'error':str(exc)})
        except Exception as exc:
            self.log_error('Unexpected exception: %r',exc)
            self.reply(500,{'error':'Calculation failed. See terminal for details.'})


    def do_POST(self):
        parsed=urlsplit(self.path)
        # Only a JSON request initiated by this local UI is allowed to write data.
        origin=self.headers.get('Origin', '')
        host=self.headers.get('Host', '')
        if not _is_local_request(host, origin, DEFAULT_PORT):
            return self.reply(403, {'error':'Only the local Astral Sentinel interface can write observations.'})
        if not self.headers.get('Content-Type','').split(';')[0].strip().lower()=='application/json':
            return self.reply(415, {'error':'JSON requests only.'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 1 <= size <= 40000:
                return self.reply(413, {'error':'Invalid request size.'})
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict):
                return self.reply(400, {'error':'Invalid request.'})
            if parsed.path=='/api/profiles/create':
                return self.reply(201,create_profile(ROOT,payload))
            if parsed.path=='/api/profiles/import':
                return self.reply(201,import_profile(ROOT,payload))
            if parsed.path=='/api/profiles/select':
                return self.reply(200,switch_profile(ROOT,payload.get('id')))
            if parsed.path=='/api/profiles/update':
                return self.reply(200,update_profile(ROOT,payload.get('id'),payload.get('profile')))
            if parsed.path=='/api/profiles/delete':
                return self.reply(200,delete_profile(ROOT,payload.get('id')))
            if parsed.path=='/api/observations':
                return self.reply(201,{'entry':create_entry(ROOT,payload,snapshot)})
            if parsed.path=='/api/observations/delete':
                key=str(payload.get('id',''))
                return self.reply(200, {'deleted':delete_entry(ROOT,key)})
            if parsed.path=='/api/joplin/send':
                return self.reply(200,send_to_joplin(ROOT,str(payload.get('id','')),
                                                   payload.get('token',''),int(payload.get('port',41184))))
            return self.reply(404,{'error':'Unknown API endpoint.'})
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            return self.reply(400,{'error':str(exc)})
        except Exception as exc:
            self.log_error('Observation error: %r',exc)
            return self.reply(500,{'error':'Unable to process the observation. See local server output.'})

if __name__=='__main__':
    port=DEFAULT_PORT
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    url=f'http://127.0.0.1:{port}'
    print(f'\n  ASTRAL SENTINEL v1.0.0  |  {url}\n  Offline local server. Press Ctrl+C to stop.\n')
    if '--no-browser' not in sys.argv:
        threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
