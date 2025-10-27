from importlib import metadata

from .exceptions import MusicCastConnectionException, MusicCastException, MusicCastGroupException
from .features import DeviceFeature, ZoneFeature
from .musiccast_data import MusicCastData, MusicCastZoneData
from .musiccast_device import (
    MusicCastDevice,
)
from .musiccast_media_content import MusicCastMediaContent

__all__ = [
    "DeviceFeature",
    "MusicCastConnectionException",
    "MusicCastData",
    "MusicCastDevice",
    "MusicCastException",
    "MusicCastGroupException",
    "MusicCastMediaContent",
    "MusicCastZoneData",
    "ZoneFeature",
]

try:
    __version__ = metadata.version("aiomusiccast")
except metadata.PackageNotFoundError:
    __version__ = "(local)"
