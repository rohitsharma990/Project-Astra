from pycaw.pycaw import AudioUtilities


def _get_volume():
    device = AudioUtilities.GetSpeakers()
    return getattr(device, "EndpointVolume")


def set_volume(level: int) -> int:
    level = max(0, min(100, int(level)))
    _get_volume().SetMasterVolumeLevelScalar(level / 100, None)
    return level


def volume_up(step: int = 10) -> int:
    volume = _get_volume()
    level = min(1.0, volume.GetMasterVolumeLevelScalar() + step / 100)
    volume.SetMasterVolumeLevelScalar(level, None)
    return round(level * 100)


def volume_down(step: int = 10) -> int:
    volume = _get_volume()
    level = max(0.0, volume.GetMasterVolumeLevelScalar() - step / 100)
    volume.SetMasterVolumeLevelScalar(level, None)
    return round(level * 100)


def mute() -> None:
    _get_volume().SetMute(1, None)


def unmute() -> None:
    _get_volume().SetMute(0, None)