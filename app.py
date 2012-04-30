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

FB_SERVICE_ID = 'facebook'

def find_user_by_token(token):
    """Return user for given app token"""
    user = database.users.User.find_one({'token': token})
    return user

def find_user_by_service(service_name, service_id):
    """Return user for given service name and service id"""
    user = database.users.User.find_one({
            'services.name': service_name,
            'services.id': service_id
            })
    return user

def find_user_by_id(id):
    """Return user for given id"""
    user = database.users.User.find_one({'_id': id})
    return user

@app.route('/login', methods=['POST'])
def login():
    """Update user information or create new user"""
    try:
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

        user = find_user_by_token(token)
        if not user: return json.dumps({'status': 'failure', 'error': 'auth'})

        for service in user.services:
            if service['name'] == FB_SERVICE_ID:
                # Request friends list
                r = requests.get('https://graph.facebook.com/{0}/friends?access_token={1}'.format(service['id'], service['token']))
                if r.status_code != 200:
                    return json.dumps({'status': 'failure', 'error': 'service'})
                # Filter list to app users
                result = json.loads(r.text)
                friends = []
                for friend in result['data']:
                    friend_account = find_user_by_service(service['name'], friend['id'])
                    if friend_account:
                        # Populate list with friend name and our app id
                        friends.append({'name': friend['name'], 'id': friend_account._id})

        return json.dumps({'status': 'success', 'data': friends})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/init', methods=['POST'])
def call_init(target_id):
    """Initiate the call"""
    try:
        # Parse request
        device_type = request.json['device']
        token = request.json['token']

        # Determine source and target
        source = find_user_by_token(token)
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})
        target = find_user_by_id(target_id)
        if not target: raise KeyError

        # Invalidate previous calls
        database.calls.find_and_modify(
            {'source_id': source._id,
             'target_id': target._id,
             'complete': False},
            {'$set': {'complete': True}})
        database.calls.find_and_modify(
            {'source_id': target._id,
             'target_id': source._id,
             'complete': False},
            {'$set': {'complete': True}})

        # Create call
        call = database.calls.Call()
        call.source_id = source._id
        call.target_id = target._id
        call.expires = int(time.time()) + CALL_RINGTIME
        call.save()

        # TODO: Send push notification to target

        return json.dumps({'status': 'success'})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/poll')
def call_poll(target_id):
    """Return target's location if call is connected"""
    try:
        token = request.args['token']

        # Determine source and target
        source = find_user_by_token(token)
        if not source: return json.dumps({'status': 'failure', 'error': 'auth'})
        target = find_user_by_id(target_id)
        if not target: raise KeyError

        # Check for incoming and outgoing calls
        call_in = database.calls.find_one(
            {'source_id': target._id,
             'target_id': source._id,
             'complete': False})
        call_out = database.calls.Call.find_one(
            {'source_id': source._id,
             'target_id': target._id,
             'complete': False})

        # Choose more recent call if simultaneous init
        if call_in and call_out:
            if call_in.expires > call_out.expires:
                other = call_out
                call = call_in
            else:
                other = call_in
                call = call_out
            # Complete older call
            other.complete = True
            other.save()
        elif call_in:
            call = call_in
        elif call_out:
            call = call_out
        else:
            return json.dumps({'status': 'failure', 'error': 'disconnected'})

        # Check if call has expired
        if call.expires > int(time.time()):
            call.complete = True
            return json.dumps({'status': 'failure', 'error': 'disconnected'})

        if call == call_in:
            # Receive call if not already connected
            if call.connected == False:
                call.connected = True
                call.save()
        else:
            # Check if partner has received call
            if call_out.connected == False:
                return json.dumps({'status': 'failure', 'error': 'waiting'})

        # TODO: Return location of partner
        location = get_location_by_id(target._id)
        return json.dumps({'status': 'success', 'data': location})

    except KeyError: pass
    return json.dumps({'status': 'failure', 'error': 'invalid'})

@app.route('/incoming')
def incoming():
    try:
        source = find_user_by_token(request.form['token'])
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
