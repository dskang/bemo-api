from flask import Flask, request
from mongokit import Connection
from models import Session, Call, Location
import os, requests, urlparse, json, time, md5
app = Flask(__name__)

RDV_TIMEOUT = 1440 * 14  # token valid for two weeks

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27107

FB_APP_ID = '407078449305300'
FB_APP_SECRET = '8e4fcedc28a2705b8183b42bd5fe81c0'
FB_DUMMY_REDIRECT = 'http%3A%2F%2Flocalhost%2F'

def querystr_to_dict(q):
    return dict([part.split('=') for part in q.split('&')])

@app.route('/login', methods=['POST'])
def login():
    try:

        dev_type = 'iphone'
        dev_id = request.form['device_token']
        # TODO: validate the device ID by talking to Apple servers
        # otherwise, we are vulnerable to DoS attacks invalidating real devices' sessions

        rendezvous_token = md5.new(time.time())
        rendezvous_token.update(rendezvous_id)            

        if request.form['service'] == 'fbook':
            fb_req = requests.get('https://graph.facebook.com/me?access_token=%s' % 
                                  request.form['service_token'])
            if fb_req.status_code != 200:
                return json.dumps({'status': 'failure', 'error': 'auth'})
            fb_params = querystr_to_dict(urlparse(fb_req.text).query)
            service_id = fb_params['id']

        else:
            raise KeyError

        # TODO: invalidate previous sessions
        s = Session({'token': rendezvous_token.hexdigest(),
                     'expires': int(time.time) + RDV_TIMEOUT,
                     'device': dev_type,
                     'device_id': dev_id,
                     'service': request.form['service'],
                     'service_id': service_id
                     })
        s.save()

        return json.dumps({'status': 'success',
                           'session': rendezvous_token,
                           })

    except KeyError:
        pass
    return json.dumps({'status': 'failure'})

#TODO look at possibility of CSRF attack
@app.route('/users/<int:id>/friends', methods=['POST'])
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
            #TODO this using sapply
            friends = []
            for fb_id in json.loads(r.text)['data']:
                rdv_id = dblookup(fb_id['id'])
                if rdv_id:
                    friends.push(rdv_id)
                    
        return json.dumps({'status': 'success', 'data': friends})

    except KeyError:
        pass

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    connection = Connection(app.config['MONGODB_HOST'],
                            app.config['MONGODB_PORT'])
