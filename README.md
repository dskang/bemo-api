
Backend Architecture
====================

Contact: [Raymond](raymondz@princeton.edu) is responsible for this document.

App ID/API Key

    407078449305300

App Secret

    8e4fcedc28a2705b8183b42bd5fe81c0

App Namespace

    rendezvous_princeton


Service Architecture
--------------------

### Overview

A user obtains a token from each of three tiers to use the service.

- Device ('device_token')
- Sign-on ('service_token')
- Backend ('token')

The only supported device is iPhone and the only supported service is Facebook.

An iPhone token should be obtained using APNS (Apple Push
Notifications Service). A device obtains a Rendezvous token by sending
the former two tokens to the server using POST /login.

### Authentication

User authentication is distributed on the client-side. For each SSO
service supported by Rendezvous (currently only Facebook), the client
obtains an OAuth key and passes it to the server. The server verifies
the users is properly authenticated by making a request to the
service. The server then discards the Facebook authentication token,
issuing the user a Rendezvous token valid for a set time.

Friend discovery is conducted by using the server as a proxy. Friends
are relayed back to the user and never stored on the server. The
server stores the OAuth token as a session identifier.

NB: This architecture scales to multiple SSO services (i.e.
simultaneously logging into different services to combine contact
lists) while preserving privacy. The client should POST to /login for
each service that it hosts, telling the server to associate the
device's ID with the SSO ID for as long as the device remains logged
in.

### Notification Services

At login or when refreshing the friends list, the server fetches the
user's contacts and translates them to Rendezvous IDs, which are
passed back to the users. Additionally, every time the list is
displayed, the server is queried and looks up who is online by
indexing into the sessions table.

When making a call, the client passes the server its ID and token. If
the call is valid, a push notification is sent to the target and the
call is recorded in the table. The server continues to send push
notifications by checking the calls table for active calls at an
interval.

When answering a call, the client opens a connection to the server and
sends its lat/lon at a known interval until it disconnects or it is
informed the other side has disconnected. If the client does not hang
up properly, the server tells recipients the location has been lost up
to the expiration time or a set timeout.

API
---

Data sent to the server by GET is encoded in a query string. Data sent
with POST is and data returned are in JSON.

Sign in or register using an OAuth single sign-on service. The server
checks your OAuth token. You get a Rendezvous user ID and a session
token valid for two weeks. We only support Facebook right now.

    POST /login
    Content: {device: 'iphone', device_id: str, device_token: str,
              service: 'facebook', service_token: str}

    Returns {status: 'success', data: { token: str}}
    Returns {status: 'failure', error: 'auth'} if OAuth fails

Discover friends of a user who are also on the app.

    GET /friends?token=TOKEN

    Returns {status: 'success', data: [ {name: str, id: str, service_id: str} ]}
    Returns {status: 'failure', error: 'service'} if request to service fails

Initiate a location call.

    POST /call/:target_id/init
    Content: {device: 'iphone',
              service: 'facebook',
              token: str}

    Returns {status: 'success'} if request successfully placed
    Returns {status: 'failure', error: 'auth'} if not authorized

Receive a location call.

    POST /call/:target_id/receive
    Content: {device: 'iphone', # device you're receiving from
              token: str}

    Returns {status: 'success'} if call successfully received
    Returns {status: 'failure', error: 'disconnected'} if other user disconnected
    Returns {status: 'failure', error: 'auth'} if not authorized

End a location call.

    POST /call/:target_id/end
    Content: {token: str}

    Returns {status: 'success'} if call successfully ended or call is already over
    Returns {status: 'failure', error: 'auth'} if not authorized

Update location.

    POST /location/update
    Content: {device: 'iphone',
              latitude: float,
              longitude: float,
              token: str}

    Returns {status: 'success'} if location successfully updated
    Returns {status: 'failure', error: 'auth'} if not authorized

Poll for a location. (Alternative to push)

    GET /call/:target_id/poll?token=TOKEN

    Returns {status: 'failure', error: 'waiting'} if the other user has not responded to the call
    Returns {status: 'success', data: {latitude: float, longitude: float}} if the other user has accepted the call
    Returns {status: 'failure', error: 'disconnected'} at most once if the other user has disconnected or timed out
    Returns {status: 'failure', error: 'receive call'} if there is a call to be received before polling
    Returns {status: 'failure', error: 'invalid'} if the target is invalid

Poll for incoming calls. (Alternative to push)

    GET /incoming?token=TOKEN

    Returns {status: 'failure', error: 'waiting'} if no calls
    Returns {status: 'success', data: { source_id: str }} if there are incoming calls
    Returns {status: 'failure', error: 'auth'} if not authorized

Database
--------

User

    'token': unicode, # app token
    'devices': [{
        'type': unicode, # device type
        'id': unicode # device id
        }],
    'services': [{
        'name': unicode, # service name
        'id': unicode, # user's id on service
        'token': unicode # user's access token for service
        }]

Call

    'source_id': objectid.ObjectId, # id of user making call
    'source_device': unicode, # type of device
    'target_id': objectid.ObjectId, # id of user receiving call
    'target_device': unicode, # type of device
    'expires': int, # expiration of call
    'connected': bool, # whether call has been connected
    'complete': bool # whether call is complete

Location

    'user_id': objectid.ObjectId, # user's app id
    'device': unicode, # type of device
    'lat': float, # latitude
    'lon': float, # longitude
    'time': int # time location was recorded

Trivia
------

Run the server:

    source ./server-env/bin/activate
    python app.py


Deploy to Heroku.

    git add .
    git commit
    git push heroku
    heroku open
