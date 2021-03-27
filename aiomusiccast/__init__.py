from pkg_resources import DistributionNotFound, get_distribution

from .musiccast_device import (
    MusicCastData,
    MusicCastDevice,
    MusicCastGroupException,
    MusicCastZoneData,
)


try:
    __version__ = get_distribution('aiomusiccast').version
except DistributionNotFound:
    __version__ = '(local)'
