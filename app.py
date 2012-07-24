import os, urlparse, json, time, md5

import requests
from flask import Flask, request, jsonify
from mongokit import Connection
from bson import objectid, errors
from apns import APNs, Payload, PayloadAlert

from models import User, Call, Location

app = Flask(__name__)

# Environment
BEMO_ENV = os.environ['BEMO_ENV']
STAGING = 'staging'
PRODUCTION = 'production'

CALL_RINGTIME_THRESHOLD = 60 * 60 # number of seconds until unreceived call expires
CALL_POLL_THRESHOLD = 30 # number of seconds for which no polling results in disconnection
LOC_TIME_THRESHOLD = 60 # number of seconds until location expires

FB_SERVICE_ID = 'facebook'

# Push notification messages
INCOMING_CALL = 'INCOMING_CALL'
MISSED_CALL = 'MISSED_CALL'

def get_user_by_token(token):
    """Return user for given app token"""
    user = database.users.User.find_one({'token': token})
    return user

def get_user_by_id(user_id):
    """Return user for given id"""
    user = database.users.User.find_one({'_id': user_id})
    return user

def get_location(user_id):
    """Return location of user for given user id"""
    location = database.locations.Location.find_one({
            'user_id': user_id
            })
    return location

def get_service_from_user(service_name, user):
    """Return a service from user using service_name"""
    for service in user['services']:
        if service['name'] == service_name:
            return service
    return None

def add_service_to_user(service, user):
    """Add service to user or update service with same name"""
    s = get_service_from_user(service['name'], user)
    if s:
        # Update service
        s['username'] = service['username']
        s['id'] = service['id']
        s['token'] = service['token']
        user.save()
    else:
        # Add service
        user.services.append(service)
        user.save()

def get_device_from_user(device_type, user):
    """Return a device from user using device_type"""
    for device in user.devices:
        if device['type'] == device_type:
            return device
    return None

def add_device_to_user(device, user):
    """Add device to user or update device with same type"""
    d = get_device_from_user(device['type'], user)
    if d:
        # Update device
        # Note: this will overwrite any existing device for same type
        d['id'] = device['id']
        d['token'] = device['token']
        user.save()
    else:
        # Add device
        user.devices.append(device)
        user.save()

def notify_by_push(message_key, source_service, source_id, target_device_token):
    """
    Sends a push notification for an incoming call.
    Return True on success and False on failure
    """
    source_name = source_service['username']
    if message_key == INCOMING_CALL:
        custom = {}
        custom['id'] = source_id
        custom['service'] = {
            'name': source_service['name'],
            'id': source_service['id']
            }
        alert = PayloadAlert(body = None,
                             action_loc_key = 'VIEW',
                             loc_key = message_key,
                             loc_args = [source_name])
        payload = Payload(alert=alert, sound="default", custom=custom)
    elif message_key == MISSED_CALL:
        alert = PayloadAlert(body = None,
                             action_loc_key = 'OK',
                             loc_key = message_key,
                             loc_args = [source_name])
        payload = Payload(alert=alert, sound="default")
    elif message_key == None:
        # Send empty payload
        payload = Payload(sound="default")

    try:
        # Send notification
        apns_dev.gateway_server.send_notification(target_device_token, payload)
        apns_prod.gateway_server.send_notification(target_device_token, payload)
    except TypeError:
        app.logger.warning("Invalid device token for receiving push notifications: {0}".format(target_device_token))
        return False
    except IOError as e:
        app.logger.warning("Broken connection to APNS: {}".format(e))
        # Reconnect to APNS
        connect_to_apns()
        # return False

    # Get feedback messages
    for (token_hex, fail_time) in apns_dev.feedback_server.items():
        # TODO: Use fail_time to determine if user reregistered
        # device after push failed (cannot support with current DB
        # structure)

        # TODO: Remove device if appropriate and remove user if he
        # has no more devices
        app.logger.warning("Dev feedback server returned failure")
        # return False

    for (token_hex, fail_time) in apns_prod.feedback_server.items():
        app.logger.warning("Prod feedback server returned failure")

    return True

@app.route('/login', methods=['POST'])
def login():
    """Update user information or create new user"""
    try:
        # Read in request data
        device = {
            'type': unicode(request.json['device']),
            'id': unicode(request.json['device_id']),
            'token': unicode(request.json['device_token'])
            }
        service = {
            'name': unicode(request.json['service']),
            'token': unicode(request.json['service_token'])
            }

        # Make sure we accept the service
        if service['name'] == FB_SERVICE_ID:
            r = requests.get('https://graph.facebook.com/me?access_token={0}'.format(service['token']))
            if r.status_code != 200:
                return jsonify({'status': 'failure', 'error': 'service'})
            # Parse FB response
            results = json.loads(r.text)
            service['username'] = unicode(results['name'])
            service['id'] = unicode(results['id'])
        else: raise KeyError

        # Search for user in database by device
        user_by_device = database.users.User.find_one({
                'devices.type': device['type'],
                'devices.id': device['id']
             })
        # Search for user in database by service
        user_by_service = database.users.User.find_one({
                'services.name': service['name'],
                'services.id': service['id']
                })

        # Check if user exists in database
        if user_by_device or user_by_service:
            if user_by_device:
                user = user_by_device
            else:
                user = user_by_service
            # Reuse app token
            app_token = user.token
            # Add service or update it
            add_service_to_user(service, user)
            # Add device or update it
            add_device_to_user(device, user)
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

        return jsonify({'status': 'success', 'data': {'token': app_token}})

    except KeyError:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/friends', methods=['GET'])
def discover():
    """Return the list of friends for the user with given token"""
    try:
        token = request.args['token']

        user = get_user_by_token(token)
        if not user:
            return jsonify({'status': 'failure', 'error': 'auth'})

        friends = []
        for service in user.services:
            if service['name'] == FB_SERVICE_ID:
                # Request entire friends list
                r = requests.get('https://graph.facebook.com/me/friends?access_token={0}&limit=5000'.format(service['token']))
                if r.status_code != 200:
                    return jsonify({'status': 'failure', 'error': 'service'})
                result = json.loads(r.text)
                # Grab Facebook IDs of friends
                friend_ids = [friend['id'] for friend in result['data']]
                # Find friends in database
                friends_cursor = database.users.find({
                        'services.name': service['name'],
                        'services.id': {'$in': friend_ids}
                        })
                # Populate list with friend name and our app id
                for friend in friends_cursor:
                    s = get_service_from_user(service['name'], friend)
                    friend_service = {
                        'name': s['name'],
                        'id': s['id']
                        }
                    friends.append({'name': s['username'],
                                    'id': str(friend['_id']),
                                    'service': friend_service})

        return jsonify({'status': 'success', 'data': friends})

    except KeyError:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/init', methods=['POST'])
def call_init(target_id):
    """Initiate the call"""
    try:
        # Parse request
        token = request.json['token']
        service_name = request.json['service']

        # Determine source and target
        source = get_user_by_token(token)
        if not source:
            return jsonify({'status': 'failure', 'error': 'auth'})
        target_id = objectid.ObjectId(target_id)
        target = get_user_by_id(target_id)
        if not target:
            raise KeyError

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
        call.source_service = unicode(service_name)
        call.source_time = int(time.time())
        call.target_id = target._id
        call.time = int(time.time())
        call.save()

        # Send push notification to all of target's devices
        source_service = get_service_from_user(service_name, source)
        push_success = False
        for device in target.devices:
            device_token = device['token']
            push_success = notify_by_push(INCOMING_CALL, source_service, str(source._id), device_token) or push_success
            # TODO: Send multiple notifications

        # Return invalid if unable to notify any of target's devices
        if not push_success:
            return jsonify({'status': 'failure', 'error': 'invalid'})

        return jsonify({'status': 'success'})

    except KeyError:
        pass
    except TypeError:
        pass
    except errors.InvalidId:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/location/update', methods=['POST'])
def location_update():
    """Update location of user"""
    try:
        token = request.json['token']
        lat = request.json['latitude']
        lon = request.json['longitude']

        # Determine user
        user = get_user_by_token(token)
        if not user:
            return jsonify({'status': 'failure', 'error': 'auth'})

        # Check for existing location
        loc = get_location(user._id)
        if not loc:
            # Create location
            loc = database.locations.Location()
            loc.user_id = user._id

        # Update location
        loc.lat = float(lat)
        loc.lon = float(lon)
        loc.time = int(time.time())
        loc.save()
        return jsonify({'status': 'success'})

    except KeyError:
        pass

    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/receive', methods=['POST'])
def call_receive(target_id):
    """Connect user with an incoming call from target_id"""
    try:
        token = request.json['token']

        # Determine source and target
        source = get_user_by_token(token)
        if not source:
            return jsonify({'status': 'failure', 'error': 'auth'})
        target_id = objectid.ObjectId(target_id)
        target = get_user_by_id(target_id)
        if not target:
            raise KeyError

        # Check for incoming call
        call_in = database.calls.Call.find_one(
            {'source_id': target._id,
             'target_id': source._id,
             'complete': False})
        if not call_in:
            return jsonify({'status': 'failure', 'error': 'disconnected'})
        else:
            # Receive call
            call_in.connected = True
            call_in.target_time = int(time.time())
            call_in.save()
            return jsonify({'status': 'success'})

    except KeyError:
        pass
    except errors.InvalidId:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/end', methods=['POST'])
def call_end(target_id):
    """End call between user and target_id"""
    try:
        token = request.json['token']

        # Determine source and target
        source = get_user_by_token(token)
        if not source:
            return jsonify({'status': 'failure', 'error': 'auth'})
        target_id = objectid.ObjectId(target_id)
        target = get_user_by_id(target_id)
        if not target:
            raise KeyError

        # Check for calls
        call_in = database.calls.Call.find_one(
            {'source_id': target._id,
             'target_id': source._id,
             'complete': False})
        call_out = database.calls.Call.find_one(
            {'source_id': source._id,
             'target_id': target._id,
             'complete': False})

        # Send push notification saying that the target user
        # missed a Lumo request if the call was not connected upon end
        if call_out and not call_out.connected:
            service_name = call_out.source_service
            source_service = get_service_from_user(service_name, source)
            for device in target.devices:
                device_token = device['token']
                notify_by_push(MISSED_CALL, source_service, str(source._id), device_token)

        # Close open calls
        if call_in:
            call_in.complete = True
            call_in.save()
        if call_out:
            call_out.complete = True
            call_out.save()
        return jsonify({'status': 'success'})

    except KeyError:
        pass
    except errors.InvalidId:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/call/<target_id>/poll')
def call_poll(target_id):
    """Return target's location if call is connected"""
    try:
        token = request.args['token']

        # Determine source and target
        source = get_user_by_token(token)
        if not source:
            return jsonify({'status': 'failure', 'error': 'auth'})
        target_id = objectid.ObjectId(target_id)
        target = get_user_by_id(target_id)
        if not target:
            raise KeyError

        # Check for incoming and outgoing calls
        call_in = database.calls.Call.find_one(
            {'source_id': target._id,
             'target_id': source._id,
             'complete': False})
        call_out = database.calls.Call.find_one(
            {'source_id': source._id,
             'target_id': target._id,
             'complete': False})
        if call_in:
            # Make sure call has been received
            if not call_in.connected:
                return jsonify({'status': 'failure', 'error': 'receive call'})
            call = call_in
            partner_time = call_in.source_time
            # Update time of last poll
            call_in.target_time = int(time.time())
            call_in.save()
        elif call_out:
            call = call_out
            partner_time = call_out.target_time
            # Update time of last poll
            call_out.source_time = int(time.time())
            call_out.save()
        else:
            return jsonify({'status': 'failure', 'error': 'disconnected'})

        # Check if call is expired or disconnected
        now = int(time.time())
        expired = not call.connected and now > call.time + CALL_RINGTIME_THRESHOLD
        disconnected = call.connected and now > partner_time + CALL_POLL_THRESHOLD
        if expired or disconnected:
            call.complete = True
            call.save()
            return jsonify({'status': 'failure', 'error': 'disconnected'})

        # Check if partner has received call if outgoing call
        if call == call_out and not call_out.connected:
            return jsonify({'status': 'failure', 'error': 'waiting'})

        # Return location of partner if it's still recent
        location = get_location(target_id)
        if location and int(time.time()) <= location.time + LOC_TIME_THRESHOLD:
            loc_data = {
                'latitude': location.lat,
                'longitude': location.lon
                }
        else:
            # Return fake location until we receive real one
            loc_data = {
                'latitude': 0,
                'longitude': 0
                }

        return jsonify({'status': 'success', 'data': loc_data})

    except KeyError:
        pass
    except errors.InvalidId:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/incoming')
def incoming():
    """Return an incoming call, if any"""
    try:
        token = request.args['token']

        user = get_user_by_token(token)
        if not user:
            return jsonify({'status': 'failure', 'error': 'auth'})

        call = database.calls.Call.find_one({
                'target_id': user._id,
                'connected': False,
                'complete': False
                })
        if call:
            return jsonify({'status': 'success', 'data': {'source_id': str(call.source_id)}})
        else:
            return jsonify({'status': 'failure', 'error': 'waiting'})

    except KeyError:
        pass
    return jsonify({'status': 'failure', 'error': 'invalid'})

@app.route('/')
def hello():
    raise Exception('Sentry test')
    return('<div style="font: 36px Helvetica Neue, Helvetica, Arial;' +
           'font-weight: 100; text-align: center; margin: 20px 0;">Bemo</div>')

def connect_to_apns():
    """Connect to APNS"""
    global apns_dev
    global apns_prod

    apns_dev = APNs(use_sandbox=True, cert_file='apns-dev-cert.pem', key_file='apns-key.pem')
    apns_prod = APNs(use_sandbox=False, cert_file='apns-prod-cert.pem', key_file='apns-key.pem')

def connect_to_db():
    """Connect to database"""
    global database

    MONGOLAB_URI = os.environ['MONGOLAB_URI']
    MONGODB_HOST = urlparse.urlparse(MONGOLAB_URI).geturl()
    MONGODB_PORT = urlparse.urlparse(MONGOLAB_URI).port
    DATABASE_NAME = urlparse.urlparse(MONGOLAB_URI).path[1:]

    connection = Connection(MONGODB_HOST, MONGODB_PORT)
    connection.register([User, Call, Location])
    database = connection[DATABASE_NAME]

def start_sentry():
    """Start Sentry"""
    global sentry

    from raven.contrib.flask import Sentry
    sentry = Sentry(app)

def start_server():
    """Start the server"""
    port = int(os.environ.get("PORT", 5000))
    if port == 5000:
        app.run(debug=True)
    else:
        start_sentry()

        # Use Tornado in production
        from tornado.wsgi import WSGIContainer
        from tornado.httpserver import HTTPServer
        from tornado.ioloop import IOLoop
        import tornado.options

        # Parse command line options
        tornado.options.parse_command_line()
        # Start the server
        http_server = HTTPServer(WSGIContainer(app))
        http_server.listen(port)
        IOLoop.instance().start()

if __name__ == "__main__":
    connect_to_apns()
    connect_to_db()
    start_server()
