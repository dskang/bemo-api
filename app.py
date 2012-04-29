from flask import Flask, request
from mongokit import Connection
from models import Session, Call, Location
import os, requests, urlparse, json, time, md5
app = Flask(__name__)

MONGODB = 'staging'
MONGODB_HOST = urlparse.urlparse(os.environ['MONGOLAB_URI']).geturl()
MONGODB_PORT = urlparse.urlparse(os.environ['MONGOLAB_URI']).port

RDV_TIMEOUT = 1440 * 14  # token valid for two weeks
CALL_RINGTIME = 30
CALL_LINETIME = 30 * 60
TIME_EXPIRED = 999999999999 # epoch time for expiring records

FB_APP_ID = '407078449305300'
FB_APP_SECRET = '8e4fcedc28a2705b8183b42bd5fe81c0'

def querystr_to_dict(q):
    return dict([part.split('=') for part in q.split('&')])

def find_session_by_token(token):
    sess = connection[MONGODB].sessions.Session.find_one({'token': token})
    if sess and int(time.time) < sess['expires']: return sess
    return None

def find_session_by_id(id):
    target_sessions = connection[MONGODB].sessions.Session.find({'id': id})
    if not target_sessions:
        return json.dumps({'status': 'failure', 'error': 'invalid-recipient'})
    #target_sessions.sort(key=lambda d: d['expires'], reverse=True)
    for t in target_sessions:
        if t['expires'] > int(time.time): return t
    return None

@app.route('/login', methods=['POST'])
def login():
    try:

        #TODO validate device ID with Apple servers, to avoid session invalidation DoS
        dev_type = 'iphone'
        dev_id = request.form['device_token']

        rendezvous_token = md5.new(time.time())
        rendezvous_token.update(rendezvous_id)
        rendezvous_token = rendezvous_token.hexdigest()

        if request.form['service'] == 'fbook':
            fb_req = requests.get('https://graph.facebook.com/me?access_token=%s' %
                                  request.form['service_token'])
            if fb_req.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'auth'})
            fb_params = querystr_to_dict(urlparse(fb_req.text).query)
            service_id = fb_params['id']

        else: raise KeyError

        # invalidate sessions
        connection[MONGODB].sessions.Session.find_and_modify(
            {'service': request.form['service'], 'service_id': service_id},
            {'$set': {'expires': TIME_EXPIRED}})
        connection[MONGODB].sessions.Session({
             'id': '%s%s' % (request.form['service'], service_id),
             'token': rendezvous_token,
             'expires': int(time.time) + RDV_TIMEOUT,
             'device': dev_type,
             'device_id': dev_id,
             'service': request.form['service'],
             'service_id': service_id
        }).save()

        return json.dumps({'status': 'success',
                           'session': rendezvous_token,
                           })

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/users/<int:id>/friends', methods=['POST'])
def discover(id):
    try:
        source = find_session_by_token(request.form['token'])
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})

        if request.form['service'] == 'fbook':
            r = requests.get('https://graph.facebook.com/%i/friends' % id +
                             '?access_token=' + request.form['service_token'] +
                             '?format=json')
            if r.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'service'})

            friends = []
            for friend in json.loads(r.text)['data']:
                friend_record = connection[MONGODB].sessions.Session.find_one(
                    {'id': 'fbook%s' % service_id})
                if friend_record and friend_record['expires'] > int(time.time):
                    friends.append({'name': friend['name'], 'id': friend['id'],
                    'expires': friend_record['expires']})
                else:
                    friends.append({'name': friend['name'], 'id': friend['id'],
                    'expires': TIME_EXPIRED})

        else: raise KeyError

        return json.dumps({'status': 'success', 'data': friends})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<int:id>/init')
def call_init(id):
    try:
        source = find_session_by_token(request.form['token'])
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})
        target = find_session_by_id(id)
        if not target: return json.dumps({'status': 'failure', 'error': 'offline'})

        connection[MONGODB].calls.Call.find_and_modify(
            {'source_user': source['id'], 'target_user': target['id']},
            {'$set': {'complete': True}})
        connection[MONGODB].calls.Call.find_and_modify(
            {'source_user': target['id'], 'target_user': source['id']},
            {'$set': {'complete': True}})
        connection[MONGODB].calls.Call({
            'source_user': 0,
            'target_user': id,
            'expires': int(time.time) + CALL_RINGTIME,
            'received': False,
            'complete': False
        }).save()

        return json.dumps({'status': 'success'})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<int:id>/poll')
def call_poll(id):
    try:
        source = find_session_by_token(request.form['token'])
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})
        target = find_session_by_id(id)
        if not target: raise KeyError

        calls_out = connection[MONGODB].calls.Call.find(
            {'source_user': source['id'], 'target_user': target['id']})
        calls_in = connection[MONGODB].calls.Call.find_and_update(
            {'source_user': target['id'], 'target_user': source['id']},
            {'received': True})

        calls = calls_in
        calls.extend(calls_out)
        if len(calls) == 0: raise KeyError
        calls.sort(key=lambda d: d['expires'], reverse=True)
        call = calls[-1]

        if call['complete'] or call['expires'] > int(time.time):
            return json.dumps({'status': 'success', 'call': 'disconnected'})
        if not call['received']:
            return json.dumps({'status': 'success', 'call': 'waiting'})
        return json.dumps({'status': 'success', 'call': 'connected'})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/incoming')
def incoming():
    try:
        source = find_session_by_token(request.form['token'])
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})

        calls = [c for c in connection[MONGODB].calls.Call.find_and_update(
                  {'target_user': source['id'], 'received': False})
                 if c['expires'] > int(time.time)]

        return json.dumps({'status': 'success', 'calls': calls})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/')
def hello():
    return('<div style="font: 36px Helvetica Neue, Helvetica, Arial;' +
           'font-weight: 100; text-align: center; margin: 20px 0;">Rendezvous</div>')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    connection = Connection(app.config['MONGODB_HOST'],
                            app.config['MONGODB_PORT'])
