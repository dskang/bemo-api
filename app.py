from flask import Flask, request
import os, requests, urlparse, json
app = Flask(__name__)

FB_APP_ID = '407078449305300'
FB_APP_SECRET = '8e4fcedc28a2705b8183b42bd5fe81c0'
FB_DUMMY_REDIRECT = 'http%3A%2F%2Flocalhost%2F'

#global stores:
# open sessions
user_id, session token, 

def querystr_to_dict(q):
    return dict([part.split('=') for part in q.split('&')])

@app.route('/login', method='POST')
def login():
    try:

        #TODO make this non-blocking by pushing to an event queue        
        ''' Single sign-on with mobile CSRF protection; not used for iOS app
        if request.form['service'] == 'fbmob':
            fb_req = requests.get('https://graph.facebook.com/oauth/' +
                                  'access_token?client_id=' + FB_APP_ID + 
                                  '&redirect_uri=' + YOUR_REDIRECT_URI + 
                                  '&client_secret=' + FB_APP_SECRET + 
                                  '&code=' + request.form['service_token'])            
            # verify Facebook user
            if fb_req.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'auth'})
            fb_params = querystr_to_dict(urlparse(fb_req.text).query)
                              '''

        if request.form['service'] == 'fbook':

            # look up user id and session
            requests.get(fbid query)
            fbid = get fbid from requests.text
            user = users.get(users, fbid=fbid)

            # directly call discover() to get the friends list
            request.form['service_token']
            
            return json.dumps({'status': 'success',
                               'id': 0,
                               'session': 0,
                               'newuser': 0})

    return json.dumps({'status': 'failure'})

#TODO look at possibility of CSRF attack
@app.route('/users/<int:id>/friends', method='POST')
def discover(id):

    try:
        if request.form['service'] == 'fbook':

            # request friends list from facebok
            r = requests.get('https://graph.facebook.com/%i/friends' % id + 
                             '?access_token=' + request.form['service_token'] +
                             '?format=json')
            if r.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'service'})

            # lookup facebook friends in database
            #TODO
            friends = []
            for fb_id in json.loads(r.text)['data']:
                rdv_id = dblookup(fb_id['id'])
                if rdv_id:
                    friends.push(rdv_id)

            return json.dumps({'status': 'success', 'data': friends})

    return json.dumps({'status': 'failure'})

@app.route('/call/<int:id>/init')
def call_init(id):
    return 'Unimplemented'

@app.route('/call/<int:id>/poll')
def call_poll(id):
    return 'Unimplemented'

@app.route('/incoming')
def incoming():
    return 'Unimplemented'

@app.route('/')
def hello():
    return "Rendezvous backend. Nothing here."

@app.route('')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
