from mongokit import Document
from bson import objectid

class User(Document):
    structure = {
        'token': unicode, # app token
        'devices': [{
            'type': unicode, # device type
            'id': unicode, # device id
            'token': unicode # device token for push notifications
            }],
        'services': [{
            'name': unicode, # service name
            'username': unicode, # user's name on service
            'id': unicode, # user's id on service
            'token': unicode # user's access token for service
            }]
        }
    required_fields = ['token']
    default_values = {'devices': [], 'services': []}
    validators = {}

    use_dot_notation = True
    def __repr__(self):
        return '<User {0} with token {1}>'.format(self._id,
                                                  self.token)

class Call(Document):
    structure = {
        'source_id': objectid.ObjectId, # id of user making call
        'source_service': unicode, # name of service used to make call
        'source_time': int, # time source last polled server
        'target_id': objectid.ObjectId, # id of user receiving call
        'target_time': int, # time target last polled server
        'time': int, # time that call was made
        'connected': bool, # whether call has been connected
        'complete': bool # whether call is complete
        }
    required_fields = ['source_id', 'target_id']
    default_values = {'connected': False, 'complete': False}
    validators = {}

    use_dot_notation = True
    def __repr__(self):
        return '<Call from {0} to {1} started at {2}>'.format(self.source_id,
                                                               self.target_id,
                                                               self.time)

class Location(Document):
    structure = {
        'user_id': objectid.ObjectId, # user's app id
        'lat': float, # latitude
        'lon': float, # longitude
        'time': int # time location was recorded
        }
    validators = {}

    use_dot_notation = True
    def __repr__(self):
        return '<Location of {0} at {1}>'.format(self.user_id, self.time)
