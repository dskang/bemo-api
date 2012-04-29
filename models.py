from mongokit import Document

class Session(Document):
    structure = {
        'token': unicode,
        'expires': int,
        'device': unicode,
        'device_id': unicode,
        'service': unicode,
        'service_id': unicode,
        'service_token': unicode
        }
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Session {0} expiring at {1}>'.format(self.token, self.expires)

class Call(Document):
    structure = {
        'source_user': int,
        'target_user': int,
        'expires': int,
        'received': bool,
        'complete': bool
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
        'device': unicode,
        'device_id': unicode,
        'lat': float,
        'lon': float,
        'time': int
        }
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Location of {0} at {1}>'.format(self.device_token, self.time)
