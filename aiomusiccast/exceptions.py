class MusicCastException(Exception):
    pass


class MusicCastUnsupportedException(Exception):
    pass


class MusicCastGroupException(MusicCastException):
    pass


class MusicCastConnectionException(MusicCastException):
    pass


class MusicCastConfigurationException(MusicCastGroupException):
    pass


class MusicCastParamException(MusicCastException):
    pass
