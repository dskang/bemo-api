from flask import Flask, request
from mongokit import Connection
from models import User, Call, Location
import os, requests, urlparse, json, time, md5

app = Flask(__name__)

MONGOLAB_URI = os.environ['MONGOLAB_URI']
MONGODB_HOST = urlparse.urlparse(MONGOLAB_URI).geturl()
MONGODB_PORT = urlparse.urlparse(MONGOLAB_URI).port
DATABASE_NAME = urlparse.urlparse(MONGOLAB_URI).path[1:]

RDV_TIMEOUT = 1440 * 14  # token valid for two weeks
CALL_RINGTIME = 30
CALL_LINETIME = 30 * 60
TIME_EXPIRED = 999999999999 # epoch time for expiring records

FB_SERVICE_ID = 'fb'

def find_session_by_token(token):
    """Return session for given app token"""
    session = database.sessions.Session.find_one({'token': token})
    if session and int(time.time()) < session['expires']: return session
    return None

def find_session_by_id(id):
    """Return session for given id"""
    target_sessions = database.sessions.Session.find({'id': id})
    if not target_sessions:
        return json.dumps({'status': 'failure', 'error': 'invalid-recipient'})
    #target_sessions.sort(key=lambda d: d['expires'], reverse=True)
    for t in target_sessions:
        if t['expires'] > int(time.time()): return t
    return None

@app.route('/login', methods=['POST'])
def login():
    """Create a session for the user and return an app token"""
    try:
        # TODO: validate device ID with Apple servers, to avoid session invalidation DoS
        # Read in request data
        device = {
            'type': unicode(request.json['device']),
            'id': unicode(request.json['device_token'])
            }
        service = {
            'name': unicode(request.json['service']),
            'token': unicode(request.json['service_token'])
            }

        # Make sure we accept the service
        if service['name'] == FB_SERVICE_ID:
            r = requests.get('https://graph.facebook.com/me?access_token={0}'.format(service['token']))
            if r.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'auth'})
            # Parse FB response
            results = json.loads(r.text)
            service['id'] = unicode(results['id'])
        else: raise KeyError

        # Check if user exists in database
        user = database.users.User.find_one({
                'devices.type': device['type'],
                'devices.id': device['id']
             })

        if user:
            app_token = user.token
            # Add service if not already there
            exists = False
            for s in user.services:
                if s['name'] == service['name']:
                    exists = True
                    break
            if not exists:
                user.services.append(service)
        else:
            # Generate app token
            app_token = md5.new(str(time.time()))
            app_token.update(service['id'])
            app_token = unicode(app_token.hexdigest())

            # Add user to database
            user = database.users.User()
            user.token = app_token
            user.devices.append(device)
            user.services.append(service)
            user.save()

        return json.dumps({'status': 'success', 'token': app_token})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/friends', methods=['GET'])
def discover():
    """Return the list of friends for the user with given token"""
    try:
        token = request.args['token']

        session = find_session_by_token(token)
        if not session: return json.dumps({'status': 'failure', 'error': 'auth'})

        service = session.service
        service_token = session.service_token

        if service == FB_SERVICE_ID:
            r = requests.get('https://graph.facebook.com/{0}/friends?access_token={1}'.format(id, service_token))
            if r.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'service'})

            # Filter friends to app users
            results = json.loads(r.text)
            friends = []
            for friend in results['data']:
                friend_id = friend['id']
                friend_name = friend['name']
                friend_record = database.sessions.Session.find_one(
                    {'service': unicode(service),
                     'service_id': unicode(friend_id)})
                if friend_record and friend_record['expires'] > int(time.time()):
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

        database.calls.Call.find_and_modify(
            {'source_user': source['id'], 'target_user': target['id']},
            {'$set': {'complete': True}})
        database.calls.Call.find_and_modify(
            {'source_user': target['id'], 'target_user': source['id']},
            {'$set': {'complete': True}})
        database.calls.Call({
            'source_user': 0,
            'target_user': id,
            'expires': int(time.time()) + CALL_RINGTIME,
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

        calls_out = database.calls.Call.find(
            {'source_user': source['id'], 'target_user': target['id']})
        calls_in = database.calls.Call.find_and_update(
            {'source_user': target['id'], 'target_user': source['id']},
            {'received': True})

        calls = calls_in
        calls.extend(calls_out)
        if len(calls) == 0: raise KeyError
        calls.sort(key=lambda d: d['expires'], reverse=True)
        call = calls[-1]

        if call['complete'] or call['expires'] > int(time.time()):
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

        calls = [c for c in database.calls.Call.find_and_update(
                  {'target_user': source['id'], 'received': False})
                 if c['expires'] > int(time.time())]

        return json.dumps({'status': 'success', 'calls': calls})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/')
def hello():
    return('<div style="font: 36px Helvetica Neue, Helvetica, Arial;' +
           'font-weight: 100; text-align: center; margin: 20px 0;">Rendezvous</div>')

if __name__ == "__main__":
    try:
        # Connect to database
        connection = Connection(MONGODB_HOST, MONGODB_PORT)
        connection.register([User, Call, Location])
        database = connection[DATABASE_NAME]
    except:
        print "Error: Unable to connect to database"

    # Start the server
    app.debug = True
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
