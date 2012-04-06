
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

A user connects obtains a token for each of three tiers to use the service.

- Device ('device_token')
- Sign-on ('service_token')
- Backend ('token')

The only supported device is iPhone and the only supported service is Facebook.

An iPhone token should be obtained using APNS (Apple Push Notifications Service). A device obtains a Rendezvous token by sending the former two tokens to the server using POST /login.

### Authentication

User authentication is distributed on the client-side. For each SSO service supported by Rendezvous (currently only Facebook), the client obtains an OAuth key and passes it to the server. The server verifies the users is properly authenticated by making a request to the service. The server then discards the Facebook authentication token, issuing the user a Rendezvous token valid for a set time.

Friend discovery is conducted by using the server as a proxy. Friends are relayed back to the user and never stored on the server. The server stores the OAuth token as a session identifier.

NB: This architecture scales to multiple SSO services (i.e. simultaneously logging into different services to combine contact lists) while preserving privacy. The client should POST to /login for each service that it hosts, telling the server to associate the device's ID with the SSO ID for as long as the device remains logged in.

### Notification Services

At login or when refreshing the friends list, the server fetches the user's contacts and translates them to Rendezvous IDs, which are passed back to the users. Additionally, every time the list is displayed, the server is queried and looks up who is online by indexing into the sessions table.

When making a call, the client passes the server its ID and token. If the call is valid, a push notification is sent to the target and the call is recorded in the table. The server continues to send push notifications by checking the calls table for active calls at an interval.

When answering a call, the client opens a connection to the server and sends its lat/lon at a known interval until it disconnects or it is informed the other side has disconnected. If the client does not hang up properly, the server tells recipients the location has been lost up to the expiration time or a set timeout.

API
---

Data sent to the server by GET is encoded in a query string. Data sent with POST is and data returned are in JSON.

Sign in or register using an OAuth single sign-on service. The server checks your OAuth token. You get a Rendezvous user ID and a session token valid for two weeks. We only support Facebook right now.

	POST /login
	Content: {device: 'iphone', device_token: str,
	          service: 'fbook', service_token: str}

	Returns {status: 'success', id: int, session: str, newuser: boolean}
	Returns {status: 'failure', error: 'auth'} if OAuth fails

Discover friends of a user.

	POST /users/:id/friends
	Content: {service: 'fbook', service_token: str}

	Returns {status: 'success', data: [ {name: str, id: int} ]}
	Returns {status: 'failure', error: 'service'} if request to service fails

Initiate a location call.

	POST /call/:id/init
	Content: {device: 'iphone', device_token: str, 
             target	          
	          id: int, token: str, target_id: int}

	Returns {status: 'success'} if request successfully placed
	Returns {status: 'failure', error: 'offline'} if other user is not logged in
	Returns {status: 'failure', error: 'auth'} if not authorized

Poll for a location. (In case of failure to open a socket.)

	GET /call/:id/poll
	Params: str uuid, int id, str token

	Returns {status: 'waiting'} if the other user has not responded to the call
	Returns {status: 'success', latitude: float, longitude: float} if the other user has accepted the call
	Returns {status: 'disconnected'} at most once if the other user has disconnected or timed out
	Returns {status: 'failure'} if the target is invalid

Poll for incoming calls. (In case of failure to open a socket.)

	GET /incoming
	Params: str uuid, int id, str token

	Returns {status: 'success', data: null} if no calls
	Returns {status: 'success', data: [ {source_id: int, expires: int} ]} if there are incoming calls
	Returns {status: 'failure', error: 'auth'} if not authorized

Database
--------

Sessions

    int user, char token, int expires,
    char device, char device_token,
    char service, char service_token

Calls

    int source_user, int target_user, int expires, bool authorized
    
Locations

    char device, char device_token, double lat, double lon

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
