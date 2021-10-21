# list of supported features, directly indicated by musiccast

from enum import Flag, auto


class Feature(Flag):
    pass


class DeviceFeature(Feature):

    NONE = 0

    WIRED_LAN = auto()
    WIRELESS_LAN = auto()
    WIRELESS_DIRECT = auto()
    EXTEND_1_BAND = auto()
    DFS_OPTION = auto()
    NETWORK_STANDBY = auto()
    NETWORK_STANDBY_AUTO = auto()
    BLUETOOTH_STANDBY = auto()
    BLUETOOTH_TX_SETTING = auto()
    BLUETOOTH_TX_CONNECTIVITY_TYPE = auto()
    IR_SENSOR = auto()
    SPEAKER_A = auto()
    SPEAKER_B = auto()
    HEADPHONE = auto()
    DIMMER = auto()
    ZONE_B_VOLUME_SYNC = auto()
    HDMI_OUT_1 = auto()
    HDMI_OUT_2 = auto()
    HDMI_OUT_3 = auto()
    AIRPLAY = auto()
    STEREO_PAIR = auto()
    SPEAKER_SETTINGS = auto()
    DISKLAVIER_SETTINGS = auto()
    BACKGROUND_DOWNLOAD = auto()
    REMOTE_INFO = auto()
    NETWORK_REBOOT = auto()
    SYSTEM_REBOOT = auto()
    AUTO_PLAY = auto()
    SPEAKER_PATTERN = auto()
    PARTY_MODE = auto()
    AUTO_POWER_STANDBY = auto()
    ANALYTICS = auto()
    YPAO_VOLUME = auto()
    PARTY_VOLUME = auto()
    PARTY_MUTE = auto()
    NAME_TEXT_AVR = auto()
    HDMI_STANDBY_THROUGH = auto()

    # list of supported features that got infered indirectly
    CLOCK = auto()
    ALARM_ONEDAY = auto()
    ALARM_WEEKLY = auto()


# Zone Features
class ZoneFeature(Feature):
    NONE = 0

    POWER = auto()
    SLEEP = auto()
    VOLUME = auto()
    MUTE = auto()
    SOUND_PROGRAM = auto()
    SURROUND_3D = auto()
    DIRECT = auto()
    PURE_DIRECT = auto()
    ENHANCER = auto()
    TONE_CONTROL = auto()
    EQUALIZER = auto()
    BALANCE = auto()
    DIALOGUE_LEVEL = auto()
    DIALOGUE_LIFT = auto()
    CLEAR_VOICE = auto()
    SUBWOOFER_VOLUME = auto()
    BASS_EXTENSION = auto()
    SIGNAL_INFO = auto()
    PREPARE_INPUT_CHANGE = auto()
    LINK_CONTROL = auto()
    LINK_AUDIO_DELAY = auto()
    LINK_AUDIO_QUALITY = auto()
    SCENE = auto()
    CONTENTS_DISPLAY = auto()
    CURSOR = auto()
    MENU = auto()
    ACTUAL_VOLUME = auto()
    AUDIO_SELECT = auto()
    SURR_DECODER_TYPE = auto()
    EXTRA_BASS = auto()
    ADAPTIVE_DRC = auto()
    DTS_DIALOGUE_CONTROL = auto()
    ADAPTIVE_DSP_LEVEL = auto()
    MONO = auto()
