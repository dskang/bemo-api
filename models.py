from mongokit import Document

class Session(Document):
    structure = {
        'token': unicode,
        'expires': int,
        'device': unicode, 'device_id': unicode,
        'service': unicode, 'service_id': unicode
        }
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Session %r expiring at %i>' % (self.user, self.expires)

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
        return '<Call from %i to %i at %i>' % (self.source_user,
                                               self.target_user, self.expires)

class Location(Document):
    structure = {
        'device': unicode, 'device_id': unicode,
        'lat': float, 'lon': float, 'time': int
        }
    validators = {
        }

    use_dot_notation = True
    def __repr__(self):
        return '<Location of %r at %i>' & (self.device_token, self.time)
