"""Root conftest: inject stub homeassistant modules so parser/model tests run without HA."""
from __future__ import annotations

import sys
import types


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    # Register parent packages
    parts = name.split(".")
    for i in range(1, len(parts)):
        parent_name = ".".join(parts[:i])
        parent = sys.modules.setdefault(parent_name, types.ModuleType(parent_name))
        setattr(parent, parts[i], mod if i == len(parts) - 1 else sys.modules.get(".".join(parts[: i + 1]), types.ModuleType(".".join(parts[: i + 1]))))
    return mod


class _HomeAssistant:
    pass


class _ConfigEntry:
    data: dict = {}
    options: dict = {}
    entry_id: str = ""
    title: str = ""
    domain: str = ""
    version: int = 1


class _ConfigFlow:
    VERSION = 1
    async def async_set_unique_id(self, uid): pass
    def _abort_if_unique_id_configured(self): pass
    def async_show_form(self, **kw): return {}
    def async_create_entry(self, **kw): return {}


class _OptionsFlow:
    def async_show_form(self, **kw): return {}
    def async_create_entry(self, **kw): return {}


class _DataUpdateCoordinator:
    data = None
    last_update_success = True
    def __init__(self, hass=None, logger=None, name="", update_interval=None): pass
    async def async_config_entry_first_refresh(self): pass
    def __class_getitem__(cls, item): return cls


class _CoordinatorEntity:
    coordinator = None
    def __init__(self, coordinator): self.coordinator = coordinator
    def __class_getitem__(cls, item): return cls


class _UpdateFailed(Exception):
    pass


class _SensorEntity:
    pass


class _DeviceInfo(dict):
    def __init__(self, **kw): super().__init__(kw)


class _ClientSession:
    pass


class _ClientTimeout:
    def __init__(self, **kw): pass


class _ClientError(Exception):
    pass


class _TimeoutError(Exception):
    pass


def _async_get_clientsession(hass):
    return _ClientSession()


# Register all stubs
_stub("homeassistant", HomeAssistant=_HomeAssistant)
_stub("homeassistant.core", HomeAssistant=_HomeAssistant, callback=lambda f: f)
_stub("homeassistant.config_entries",
      ConfigEntry=_ConfigEntry, ConfigFlow=_ConfigFlow, OptionsFlow=_OptionsFlow)
_stub("homeassistant.helpers")
_stub("homeassistant.helpers.aiohttp_client",
      async_get_clientsession=_async_get_clientsession)
_stub("homeassistant.helpers.entity", DeviceInfo=_DeviceInfo)
_stub("homeassistant.helpers.event", async_track_time_change=None)
_stub("homeassistant.helpers.entity_platform", AddEntitiesCallback=None)
_stub("homeassistant.helpers.update_coordinator",
      DataUpdateCoordinator=_DataUpdateCoordinator,
      CoordinatorEntity=_CoordinatorEntity,
      UpdateFailed=_UpdateFailed)
_stub("homeassistant.components")
_stub("homeassistant.components.sensor", SensorEntity=_SensorEntity)
_stub("homeassistant.util")
_stub("homeassistant.util.dt")

# aiohttp stubs (may already be installed, but ensure key attrs exist either way)
try:
    import aiohttp as _aiohttp
    if not hasattr(_aiohttp, "ClientTimeout"):
        _aiohttp.ClientTimeout = _ClientTimeout
except ImportError:
    _stub("aiohttp",
          ClientSession=_ClientSession,
          ClientTimeout=_ClientTimeout,
          ClientError=_ClientError,
          TimeoutError=_TimeoutError)

# voluptuous stub (if not installed)
try:
    import voluptuous  # noqa: F401
except ImportError:
    _vol = _stub("voluptuous")
    _vol.Schema = lambda x, **kw: x
    _vol.Required = lambda k, **kw: k
    _vol.Optional = lambda k, **kw: k
    _vol.All = lambda *a: a[0]
    _vol.Range = lambda **kw: None
