from mongokit import Document

class Session(Document):
    structure = {
        'token': unicode, # app token
        'expires': int, # expiration of session
        'device': unicode, # type of device
        'device_id': unicode, # device id
        'service': unicode, # service being used
        'service_id': unicode, # user's id on service
        'service_token': unicode # token used to access service
        }
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Session {0} expiring at {1}>'.format(self.token, self.expires)

class Call(Document):
    structure = {
        'source_user': int, # user making call
        'target_user': int, # user receiving call
        'expires': int, # expiration of call
        'received': bool, # whether call has been connected
        'complete': bool # whether call is complete
        }
    validators = {
        }

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
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Location of {0} at {1}>'.format(self.device_token, self.time)
