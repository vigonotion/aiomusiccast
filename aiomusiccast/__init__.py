from pkg_resources import DistributionNotFound, get_distribution

from .musiccast_device import (
    MusicCastDevice,
)
from .musiccast_data import MusicCastData, MusicCastZoneData

from .exceptions import MusicCastException, MusicCastConnectionException, MusicCastGroupException

from .musiccast_media_content import MusicCastMediaContent

from .features import DeviceFeature, ZoneFeature

try:
    __version__ = get_distribution('aiomusiccast').version
except DistributionNotFound:
    __version__ = '(local)'
