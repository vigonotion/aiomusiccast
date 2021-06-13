from aiomusiccast.exceptions import MusicCastGroupException
import asyncio
import logging
import math
from datetime import datetime
from typing import Dict, List

from .pyamaha import AsyncDevice, Clock, Dist, NetUSB, System, Tuner, Zone

_LOGGER = logging.getLogger(__name__)

MC_LINK = "mc_link"
MAIN_SYNC = "main_sync"
MC_LINK_SOURCES = [MC_LINK, MAIN_SYNC]

NULL_GROUP = "00000000000000000000000000000000"

class MusicCastData:
    """Object that holds data for a MusicCast device."""

    def __init__(self):
        """Ctor."""
        # device info
        self.device_id = None
        self.model_name = None
        self.system_version = None
        self.api_version = None

        # network status
        self.mac_addresses = None
        self.network_name = None

        # features
        self.zones: Dict[str, MusicCastZoneData] = {}
        self.input_names: Dict[str, str] = {}

        # NetUSB data
        self.netusb_input = None
        self.netusb_playback = None
        self.netusb_repeat = None
        self.netusb_shuffle = None
        self.netusb_artist = None
        self.netusb_album = None
        self.netusb_track = None
        self.netusb_albumart_url = None
        self.netusb_play_time = None
        self.netusb_play_time_updated = None
        self.netusb_total_time = None

        self.netusb_preset_list = {}

        # Tuner
        self.band = None
        self.am_freq = 1
        self.fm_freq = 1
        self.rds_text_a = ""
        self.rds_text_b = ""

        self.dab_service_label = ""
        self.dab_dls = ""

        # Group
        self.last_group_role = None
        self.last_group_id = None
        self.group_id = None
        self.group_name = None
        self.group_role = None
        self.group_server_zone = None
        self.group_client_list = []
        self.group_update_lock = asyncio.locks.Lock()

        self.has_clock = False

        # Alarm
        self.has_alarm = False
        self.alarm_enabled = None
        self.alarm_volume = None
        self.alarm_volume_range = (0, 0)
        self.alarm_volume_step = 1
        self.alarm_fade_range = (0, 0)
        self.alarm_fade_step = 1
        self.alarm_time = None
        self.alarm_playback_type = None
        self.alarm_resume_input_list = []
        self.alarm_resume_input = None
        self.alarm_preset_list = []
        self.alarm_preset = None
        self.alarm_preset_type = None
        self.alarm_preset_info = None

    @property
    def fm_freq_str(self):
        """Return a formatted string with fm frequency."""
        return "FM {:.2f} MHz".format(self.fm_freq / 1000)

    @property
    def am_freq_str(self):
        """Return a formatted string with am frequency."""
        return f"AM {self.am_freq:.2f} KHz"


class MusicCastZoneData:
    """Object that holds data for a MusicCast device zone."""

    def __init__(self):
        """Ctor."""
        self.power = None
        self.min_volume = 0
        self.max_volume = 100
        self.current_volume = 0
        self.mute: bool = False
        self.input_list = []
        self.input = None
        self.sound_program_list = []
        self.sound_program = None
        self.func_list = []


class MusicCastDevice:
    """Dummy MusicCastDevice (device for HA) for Hello World example."""

    device: AsyncDevice

    def __init__(self, ip, client):
        """Init dummy MusicCastDevice."""
        self.ip = ip
        self.client = client

        try:
            self.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.event_loop = asyncio.new_event_loop()

        self.device = AsyncDevice(client, ip, self.event_loop, self.handle)
        self._callbacks = set()
        self._group_update_callbacks = set()
        self.data = MusicCastData()

        # the following data must not be updated frequently
        self._zone_ids: List = []
        self._network_status = None
        self._device_info = None
        self._features: Dict = {}
        self._netusb_play_info = None
        self._tuner_play_info = None
        self._clock_info = None
        self._distribution_info: Dict = {}
        self._name_text = None

    @classmethod
    async def check_yamaha_ssdp(cls, location, client):
        res = await client.get(location)
        text = await res.text()
        return text.find('<yamaha:X_yxcControlURL>/YamahaExtendedControl/v1/</yamaha:X_yxcControlURL>') != -1

    @classmethod
    async def get_device_info(cls, ip, client):
        try:
            event_loop = asyncio.get_running_loop()
        except RuntimeError:
            event_loop = asyncio.new_event_loop()
        device = AsyncDevice(client, ip, event_loop)
        return await device.request_json(System.get_device_info())

    # -----UDP messaging-----

    async def handle(self, message):
        """Handle udp events."""
        for parameter in message:
            if parameter in ["main", "zone2", "zone3", "zone4"]:
                new_zone_data = message[parameter]

                self.data.zones[parameter].current_volume = new_zone_data.get(
                    "volume", self.data.zones[parameter].current_volume
                )
                self.data.zones[parameter].power = new_zone_data.get(
                    "power", self.data.zones[parameter].power
                )
                self.data.zones[parameter].mute = new_zone_data.get(
                    "mute", self.data.zones[parameter].mute
                )
                self.data.zones[parameter].input = new_zone_data.get(
                    "input", self.data.zones[parameter].input
                )

                if new_zone_data.get("play_info_updated") or new_zone_data.get(
                        "status_updated"
                ):
                    await self._fetch_zone(parameter)

        if "netusb" in message.keys():
            if message.get("netusb").get("play_info_updated"):
                await self._fetch_netusb()

            play_time = message.get("netusb").get("play_time")
            if play_time:
                self.data.netusb_play_time = play_time
                self.data.netusb_play_time_updated = datetime.utcnow()

            if message.get("netusb").get("preset_info_updated"):
                await self._fetch_netusb_presets()

        if "tuner" in message.keys():
            if message.get("tuner").get("play_info_updated"):
                await self._fetch_tuner()

        if "dist" in message.keys():
            if message.get("dist").get("dist_info_updated"):
                await self._fetch_distribution_data()

        if "clock" in message.keys():
            if message.get("clock").get("settings_updated"):
                await self._fetch_clock_data()

        for callback in self._callbacks:
            callback()

    def register_callback(self, callback):
        """Register callback, called when MusicCastDevice changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # -----Data Fetching-----

    async def _fetch_netusb(self):
        """Fetch NetUSB data."""
        _LOGGER.debug("Fetching netusb...")
        self._netusb_play_info = await self.device.request_json(NetUSB.get_play_info())

        self.data.netusb_input = self._netusb_play_info.get(
            "input", self.data.netusb_input
        )
        self.data.netusb_playback = self._netusb_play_info.get(
            "playback", self.data.netusb_playback
        )
        self.data.netusb_repeat = self._netusb_play_info.get(
            "repeat", self.data.netusb_repeat
        )
        self.data.netusb_shuffle = self._netusb_play_info.get(
            "shuffle", self.data.netusb_shuffle
        )
        self.data.netusb_artist = self._netusb_play_info.get(
            "artist", self.data.netusb_artist
        )
        self.data.netusb_album = self._netusb_play_info.get(
            "album", self.data.netusb_album
        )
        self.data.netusb_track = self._netusb_play_info.get(
            "track", self.data.netusb_track
        )
        self.data.netusb_albumart_url = self._netusb_play_info.get(
            "albumart_url", self.data.netusb_albumart_url
        )
        self.data.netusb_total_time = self._netusb_play_info.get("total_time", None)
        self.data.netusb_play_time = self._netusb_play_info.get("play_time", None)

        self.data.netusb_play_time_updated = datetime.utcnow()

    async def _fetch_tuner(self):
        """Fetch tuner data."""
        _LOGGER.debug("Fetching tuner...")
        self._tuner_play_info = await self.device.request_json(Tuner.get_play_info())

        self.data.band = self._tuner_play_info.get("band", self.data.band)

        self.data.fm_freq = self._tuner_play_info.get("fm", {}).get(
            "freq", self.data.fm_freq
        )
        self.data.am_freq = self._tuner_play_info.get("am", {}).get(
            "freq", self.data.am_freq
        )
        self.data.rds_text_a = (
            self._tuner_play_info.get("rds", {})
                .get("radio_text_a", self.data.rds_text_a)
                .strip()
        )
        self.data.rds_text_b = (
            self._tuner_play_info.get("rds", {})
                .get("radio_text_b", self.data.rds_text_b)
                .strip()
        )
        self.data.dab_service_label = (
            self._tuner_play_info.get("dab", {})
                .get("service_label", self.data.dab_service_label)
                .strip()
        )
        self.data.dab_dls = (
            self._tuner_play_info.get("dab", {}).get("dls", self.data.dab_dls).strip()
        )

    async def _fetch_zone(self, zone_id):
        _LOGGER.debug("Fetching zone %s...", zone_id)
        zone = await self.device.request_json(Zone.get_status(zone_id))
        zone_data: MusicCastZoneData = self.data.zones.get(zone_id, MusicCastZoneData())

        zone_data.power = zone.get("power")
        zone_data.current_volume = zone.get("volume")
        zone_data.mute = zone.get("mute")
        zone_data.input = zone.get("input")
        zone_data.sound_program = zone.get("sound_program")

        self.data.zones[zone_id] = zone_data

    async def _fetch_distribution_data(self):
        _LOGGER.debug("Fetching Distribution data...")
        self._distribution_info = (
            await self.device.request_json(Dist.get_distribution_info())
        )
        self.data.last_group_role = self.data.group_role
        self.data.last_group_id = self.data.group_id
        self.data.group_id = self._distribution_info.get("group_id", None)
        self.data.group_name = self._distribution_info.get("group_name", None)
        self.data.group_role = self._distribution_info.get("role", None)
        self.data.group_server_zone = self._distribution_info.get("server_zone", None)
        self.data.group_client_list = [
            client.get("ip_address", "")
            for client in self._distribution_info.get("client_list", [])
        ]
        if not self.data.group_update_lock.locked():
            for cb in self._group_update_callbacks:
                await cb()

    async def _fetch_clock_data(self):
        _LOGGER.debug("Fetching Clock data...")
        self._clock_info = (
            await self.device.request_json(Clock.get_clock_settings())
        )

        one_day_info = self._clock_info.get('alarm', {}).get('oneday', {})

        self.data.alarm_enabled = self._clock_info.get('alarm', {}).get(
            'alarm_on', False
        )
        self.data.alarm_time = one_day_info.get('time', None)
        self.data.alarm_playback_type = one_day_info.get('playback_type', None)
        self.data.alarm_resume_input = one_day_info.get('resume', {}).get('input', None)
        self.data.alarm_preset = one_day_info.get('preset', {}).get('num', None)
        self.data.alarm_preset_type = one_day_info.get('preset', {}).get('type', None)
        self.data.alarm_preset_info = (
            one_day_info.get('preset', {}).get('netusb_info', {})
            if self.data.alarm_preset_type == "netusb"
            else one_day_info.get('preset', {}).get('tuner_info', {})
        )
        self.data.alarm_volume = self._clock_info.get('alarm', {}).get("volume", None)

    async def fetch(self):
        """Fetch data from musiccast device."""
        if self.device.transport is None:
            await self.device.enable_polling()
        if not self._network_status:
            self._network_status = await self.device.request_json(System.get_network_status())

            self.data.network_name = self._network_status.get("network_name")
            self.data.mac_addresses = self._network_status.get("mac_address")

        if not self._device_info:
            self._device_info = await self.device.request_json(System.get_device_info())

            self.data.device_id = self._device_info.get("device_id")
            self.data.model_name = self._device_info.get("model_name")
            self.data.system_version = self._device_info.get("system_version")
            self.data.api_version = self._device_info.get("api_version")

        if not self._features:
            self._features = await self.device.request_json(System.get_features())

            self._zone_ids = [zone.get("id") for zone in self._features.get("zone", [])]

            for zone in self._features.get("zone", []):
                zone_id = zone.get("id")

                zone_data: MusicCastZoneData = self.data.zones.get(
                    zone_id, MusicCastZoneData()
                )

                range_volume = next(
                    item for item in zone.get("range_step") if item["id"] == "volume"
                )

                zone_data.min_volume = range_volume.get("min")
                zone_data.max_volume = range_volume.get("max")

                zone_data.sound_program_list = zone.get("sound_program_list", [])
                zone_data.input_list = zone.get("input_list", [])
                zone_data.func_list = zone.get('func_list')

                self.data.zones[zone_id] = zone_data

            if "clock" in self._features.keys():
                if "alarm" in self._features.get('clock', {}).get('func_list', []):
                    self.data.has_alarm = True

                if "date_and_time" in self._features.get('clock', {}).get(
                        'func_list', []
                ):
                    self.data.has_clock = True

                for value_range in self._features.get('clock', {}).get(
                        'range_step', []
                ):
                    if value_range.get('id') == "alarm_volume":
                        self.data.alarm_volume_range = (
                            value_range.get('min', 0),
                            value_range.get('max', 0),
                        )
                        self.data.alarm_volume_step = value_range.get('step', 1)

                    if value_range.get('id') == "alarm_fade":
                        self.data.alarm_fade_range = (
                            value_range.get('min', 0),
                            value_range.get('max', 0),
                        )
                        self.data.alarm_fade_step = value_range.get('step', 1)

                self.data.alarm_preset_list = self._features.get('clock', {}).get(
                    'alarm_preset_list', []
                )
                self.data.alarm_resume_input_list = self._features.get('clock', {}).get(
                    'alarm_input_list', []
                )

        self._name_text = await self.device.request_json(System.get_name_text(None))

        self.data.input_names = {
            source.get("id"): source.get("text")
            for source in self._name_text.get("input_list")
        }

        await self._fetch_netusb()
        await self._fetch_netusb_presets()
        await self._fetch_tuner()
        await self._fetch_distribution_data()
        if self.data.has_alarm:
            await self._fetch_clock_data()

        for zone in self._zone_ids:
            await self._fetch_zone(zone)

    # -----Commands-----
    async def turn_on(self, zone_id):
        """Turn the media player on."""
        await self.device.request(
            Zone.set_power(zone_id, "on")
        )

    async def turn_off(self, zone_id):
        """Turn the media player off."""
        await self.device.request(
            Zone.set_power(zone_id, "standby")
        )

    async def mute_volume(self, zone_id, mute):
        """Mute the volume."""
        await self.device.request(
            Zone.set_mute(zone_id, mute)
        )

    async def set_volume_level(self, zone_id, volume):
        """Set the volume level, range 0..1."""
        vol = self.data.zones[zone_id].min_volume + (
                self.data.zones[zone_id].max_volume - self.data.zones[zone_id].min_volume
        ) * volume

        await self.device.request(
            Zone.set_volume(zone_id, round(vol), 1)
        )

    async def netusb_play(self):
        await self.device.request(NetUSB.set_playback("play"))

    async def netusb_pause(self):
        await self.device.request(NetUSB.set_playback("pause"))

    async def netusb_stop(self):
        await self.device.request(NetUSB.set_playback("stop"))

    async def netusb_shuffle(self, shuffle: bool):
        if self.data.api_version < 1.19:
            if (self.data.netusb_shuffle == "on") != shuffle:
                await self.device.request(NetUSB.toggle_shuffle())
        else:
            await self.device.request(NetUSB.set_shuffle("on" if shuffle else "off"))

    async def select_sound_mode(self, zone_id, sound_mode):
        """Select sound mode."""
        await self.device.request(
            Zone.set_sound_program(zone_id, sound_mode)
        )

    async def netusb_previous_track(self):
        await self.device.request(
            NetUSB.set_playback("previous")
        )

    async def netusb_next_track(self):
        await self.device.request(
            NetUSB.set_playback("next")
        )

    async def tuner_previous_station(self):
        if self.data.band in ("fm", "am"):
            await self.device.request(
                Tuner.set_freq(self.data.band, "auto_down", 0)
            )
        elif self.data.band == "dab":
            await self.device.request(
                Tuner.set_dab_service("previous")
            )

    async def tuner_next_station(self):
        if self.data.band in ("fm", "am"):
            await self.device.request(
                Tuner.set_freq(self.data.band, "auto_up", 0)
            )
        elif self.data.band == "dab":
            await self.device.request(
                Tuner.set_dab_service("next")
            )

    async def netusb_repeat(self, mode):
        """Sets the repeat mode.
        @param mode: Value : "off" / "one" / "all"
        """
        if self.data.api_version < 1.19:
            if self.data.netusb_repeat != mode and self.data.netusb_repeat != "one":
                await self.device.request(NetUSB.toggle_repeat())
        else:
            await self.device.request(NetUSB.set_repeat(mode))

    async def select_source(self, zone_id, source):
        await self.device.request(
            Zone.set_input(zone_id, source, "")
        )

    async def recall_netusb_preset(self, zone_id, preset):
        """Play the selected preset."""
        await self.device.get(NetUSB.recall_preset(zone_id, preset))

    async def store_netusb_preset(self, preset):
        """Play the selected preset."""
        await self.device.get(NetUSB.store_preset(preset))

    async def set_sleep_timer(self, zone_id, sleep_time=0):
        """Set sleep time"""
        sleep_time = math.ceil(sleep_time / 30) * 30
        await self.device.get(Zone.set_sleep(zone_id, sleep_time))

    async def configure_alarm(self, enable=None, volume=None, alarm_time=None, source=""):
        """Setup alarm"""
        enable = self.data.alarm_enabled if enable is None else enable
        resume_input = None
        preset_type = None
        preset_num = None
        playback_type = None

        source_parts = source.split(':')
        if len(source_parts) > 0 and source_parts[0] != "":
            playback_type = source_parts[0]
            if playback_type == "resume":
                resume_input = source_parts[1]
            elif playback_type == "preset":
                preset_type = source_parts[1]
                preset_num = int(source_parts[2])
            else:
                playback_type = None

        if isinstance(alarm_time, str):
            time_parts = alarm_time.split(':')
            alarm_time = time_parts[0] + time_parts[1]

        await self.device.post(
            *Clock.set_alarm_settings(enable, volume=volume, mode="oneday" if playback_type or alarm_time else None,
                                      day="oneday" if playback_type or alarm_time else None,
                                      playback_type=playback_type, alarm_time=alarm_time, preset_num=preset_num,
                                      preset_type=preset_type, enable=enable if playback_type or alarm_time else None,
                                      resume_input=resume_input)
        )

    # -----NetUSB Browsing-----
    async def get_list_info(self, source, start_index):
        return (
            await self.device.request_json(
                NetUSB.get_list_info(source, start_index, 8, "en", "main")
            )
        )

    async def select_list_item(self, item, zone_id):
        await self.device.request(
            NetUSB.set_list_control(
                "main", "select", item, zone_id
            )
        )

    async def return_in_list(self, zone_id):
        await self.device.request(
            NetUSB.set_list_control("main", "return", "", zone_id)
        )

    async def play_list_media(self, item, zone_id):
        await self.device.request(
            NetUSB.set_list_control("main", "play", item, zone_id)
        )

    # -----Properties-----

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return (
            f"http://{self.device.ip}{self.data.netusb_albumart_url}"
            if self.data.netusb_albumart_url else ""
        )

    @property
    def tuner_media_title(self):
        if self.data.band == "dab":
            return self.data.dab_dls
        else:
            if (
                    self.data.rds_text_a == ""
                    and self.data.rds_text_b != ""
            ):
                return self.data.rds_text_b
            elif (
                    self.data.rds_text_a != ""
                    and self.data.rds_text_b == ""
            ):
                return self.data.rds_text_a
            elif (
                    self.data.rds_text_a != ""
                    and self.data.rds_text_b != ""
            ):
                return f"{self.data.rds_text_a} / {self.data.rds_text_b}"

    @property
    def tuner_media_artist(self):
        if self.data.band == "dab":
            return self.data.dab_service_label
        elif self.data.band == "fm":
            return self.data.fm_freq_str
        elif self.data.band == "am":
            return self.data.am_freq_str

        return None

    @property
    def alarm_input_list(self):
        inputs = {"resume:" + inp: "Resume " + inp for inp in self.data.alarm_resume_input_list}
        if "netusb" in self.data.alarm_preset_list:
            inputs = {**inputs, **{"preset:netusb:" + str(index): entry[0] + " - " + entry[1]
                                   for index, entry in self.data.netusb_preset_list.items()}
                      }

        return inputs

    # -----Group Management------

    def register_group_update_callback(self, callback):
        """Register async methods called after changes of the distribution data here."""
        self._group_update_callbacks.add(callback)

    # Simple check functions for better code readability

    def _check_clients_removed(self, clients):
        return all([client not in self.data.group_client_list for client in clients])

    def _check_clients_added(self, clients):
        return all([client in self.data.group_client_list for client in clients])

    def _check_group_id(self, group_id):
        return self.data.group_id == group_id

    def _check_source(self, source, zone):
        return self.data.zones[zone].input == source

    def _check_group_role(self, role):
        return self.data.group_role == role

    def _check_group_server_zone(self, zone):
        return self.data.group_server_zone == zone

    # Group update checking functions

    async def wait_for_data_update(self, checks):
        while True:
            if all([check() for check in checks]):
                return
            await asyncio.sleep(0.1)

    async def check_group_data(self, checks):
        try:
            await asyncio.wait_for(self.wait_for_data_update(checks), 1)
        except asyncio.exceptions.TimeoutError:
            _LOGGER.warning(
                "Coordinator of %s did not receive the expected group data update via UDP. "
                "Fetching manually.",
                self.ip,
            )
            await self._fetch_distribution_data()
        return all([check() for check in checks])

    # Group server functions

    async def mc_server_group_extend(self, zone, client_ips, group_id, distribution_num, retry=True):
        """Extend the given group by the given clients.

        If the group does not exist, it will be created.
        """
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(group_id, zone, "add", client_ips)
            )
            await self.device.get(Dist.start_distribution(distribution_num))
            if await self.check_group_data(
                    [
                        lambda: self._check_clients_added(client_ips),
                        lambda: self._check_group_id(group_id),
                        lambda: self._check_group_role("server"),
                        lambda: self._check_group_server_zone(zone),
                    ]
            ):
                return

        if retry:
            await self.mc_server_group_extend(zone, client_ips, group_id, distribution_num, False)
        else:
            raise MusicCastGroupException(
                self.ip + ": Failed to extent group by clients " + str(client_ips)
            )

    async def mc_server_group_reduce(self, zone, client_ips_for_removal, distribution_num, retry=True):
        """Reduce the current group by the given clients."""
        async with self.data.group_update_lock:
            await self.device.post(
                *Dist.set_server_info(
                    self.data.group_id,
                    zone,
                    "remove",
                    client_ips_for_removal,
                )
            )
            if await self.check_group_data(
                    [lambda: self._check_clients_removed(client_ips_for_removal)]
            ):
                if self.data.group_client_list:
                    await self.device.get(Dist.start_distribution(distribution_num))
                return

        if retry:
            await self.mc_server_group_reduce(zone, client_ips_for_removal, distribution_num, False)
        else:
            raise MusicCastGroupException(
                self.ip
                + ": Failed to reduce group by clients "
                + str(client_ips_for_removal)
            )

    async def mc_server_group_close(self, retry=True):
        """Close the current group."""
        async with self.data.group_update_lock:
            await self.device.get(Dist.stop_distribution())
            await self.device.post(*Dist.set_server_info(""))
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_server_group_close(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to close group.")

    # Group client functions

    async def mc_client_join(self, server_ip, group_id, zone, retry=True):
        """Join the given group as a client."""
        async with self.data.group_update_lock:
            await self.device.post(*Dist.set_client_info(group_id, zone, server_ip))
            await self.device.request(Zone.set_input(zone, MC_LINK, ""))
            if await self.check_group_data(
                    [
                        lambda: self._check_group_id(group_id),
                        lambda: self._check_group_role("client"),
                        lambda: self._check_source(MC_LINK, zone),
                    ]
            ):
                return

        if retry:
            await self.mc_client_join(server_ip, group_id, zone, False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to join the group.")

    async def mc_client_unjoin(self, retry=True):
        """Unjoin the current group."""
        async with self.data.group_update_lock:
            await self.device.post(*Dist.set_client_info(""))
            if await self.check_group_data([lambda: self._check_group_id(NULL_GROUP)]):
                return

        if retry:
            await self.mc_client_unjoin(False)
        else:
            raise MusicCastGroupException(self.ip + ": Failed to leave group")

    # Misc

    def get_save_inputs(self, zone_id):
        """Return a save save source for the given zone_id.

        A save input can be any input except netusb ones if the netusb module is
        already in use."""

        netusb_in_use = any(
            [zone.input == self.data.netusb_input for zone in self.data.zones.values()]
        )

        zone = self.data.zones.get(zone_id)

        return [
            source.get('id')
            for source in self._features.get('system', {}).get('input_list', [])
            if source.get('distribution_enable') and
            (source.get('play_info_type') != 'netusb' or not netusb_in_use) and
            source.get('id') not in MC_LINK_SOURCES and
            source.get('id') in (zone.input_list if zone else [])
        ]

    async def _fetch_netusb_presets(self):
        result = await self.device.request_json(NetUSB.get_preset_info())
        self.data.netusb_preset_list = {
            index + 1: (entry.get('input'), entry.get('text'))
            for index, entry in enumerate(result.get('preset_info', []))
            if entry.get('input') != 'unknown'
        }
