from pkg_resources import DistributionNotFound, get_distribution

from .musiccast_device import (
    MusicCastData,
    MusicCastDevice,
    MusicCastGroupException,
    MusicCastZoneData,
)

from .musiccast_media_content import MusicCastMediaContent

try:
    __version__ = get_distribution('aiomusiccast').version
except DistributionNotFound:
    __version__ = '(local)'
