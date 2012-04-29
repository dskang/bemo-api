from mongokit import Document

class User(Document):
    structure = {
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
        'source_user': int, # user making call
        'target_user': int, # user receiving call
        'expires': int, # expiration of call
        'received': bool, # whether call has been connected
        'complete': bool # whether call is complete
        }
    validators = {}

    use_dot_notation = True
    def __repr__(self):
        return '<Call from {0} to {1} at {2}>'.format(self.source_user,
                                                      self.target_user,
                                                      self.expires)

class Location(Document):
    structure = {
        'device': unicode, # type of device
        'device_id': unicode, # device id
        'lat': float, # latitude
        'lon': float, # longitude
        'time': int # time location was recorded
        }
    validators = {}

    use_dot_notation = True
    def __repr__(self):
        return '<Location of {0} at {1}>'.format(self.device_token, self.time)
