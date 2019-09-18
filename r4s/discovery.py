import yaml

from bluepy.btle import Peripheral, UUID

from r4s import UnsupportedDeviceException

_UUID_SRV_R4S = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"  # GATT Service Custom: R4S custom service.
_UUID_SRV_GENERIC = 0x1800  # GATT Service: Generic Access.

_UUID_CCCD = "00002902-0000-1000-8000-00805f9b34fb"  # GATT Descriptors: Client Characteristic Configuration Descriptor.
_UUID_CHAR_GENERIC = 0x2a00  # GATT Characteristics - Device Name.
_UUID_CHAR_CONN = 0x2a04  # GATT Characteristics - Peripheral Preferred Connection Parameters.
_UUID_CHAR_CMD = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # GATT Characteristics Custom: Write commands.
_UUID_CHAR_RSP = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # GATT Characteristics Custom: Read commands responses.


class DeviceBTAttrs:

    def __init__(self, name=None, cmd=None, ccc=None):
        self.name = name
        self.ccc = ccc
        self.cmd = cmd

    def is_complete(self):
        return self.name is not None and self.ccc is not None and self.cmd is not None

    def as_dict(self):
        return {
            'name': self.name,
            'ccc': self.ccc,
            'cmd': self.cmd,
        }

    def get_class(self):
        from r4s.devices import known_devices
        cls = known_devices[self.name]['cls'] if self.name in known_devices else None
        if cls is None:
            raise UnsupportedDeviceException('The device {} is not supported.', self.name)
        if cls is NotImplemented:
            raise NotImplemented('The device {} is known but not yet implemented.', self.name)
        return cls


class DeviceDiscovery:

    def __init__(self):
        self._discovered = {}

    def discover_device(self, peripheral: Peripheral, mac: str):
        if mac in self._discovered and self._discovered[mac].is_complete():
            return self._discovered[mac]

        if mac not in self._discovered:
            self._discovered[mac] = DeviceBTAttrs()
        self._discover_device(self._discovered[mac], peripheral)
        self._on_success(self._discovered[mac])
        return self._discovered[mac]

    def _on_success(self, new_attr):
        pass

    def as_dict(self):
        result = {}
        for key, value in self._discovered.items():
            result[key] = value.as_dict()
        return result

    @staticmethod
    def _discover_device(attrs, peripheral):
        # Services.
        services = peripheral.discoverServices()
        r4s_custom_uuid = UUID(_UUID_SRV_R4S)
        if r4s_custom_uuid not in services:
            raise UnsupportedDeviceException('The device is not supported.')
        r4s_service = services[UUID(_UUID_SRV_R4S)]
        generic_srv = services[UUID(_UUID_SRV_GENERIC)]
        # Main characteristics.
        if attrs.name is None:
            device_name_char = generic_srv.getCharacteristics(_UUID_CHAR_GENERIC)[0]
            # Generic params.
            attrs.name = peripheral.readCharacteristic(device_name_char.valHandle).decode("utf-8")

        # R4S characteristics.
        if attrs.cmd is None:
            cmd_char = r4s_service.getCharacteristics(_UUID_CHAR_CMD)[0]
            attrs.cmd = cmd_char.valHandle
        if attrs.ccc is None:
            cccd = r4s_service.getDescriptors(_UUID_CCCD)[0]
            attrs.ccc = cccd.handle


class DeviceDiscoveryYml(DeviceDiscovery):

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        try:
            with open(self.filename, 'r') as stream:
                config = yaml.safe_load(stream)
                for mac, attrs in config.items():
                    self._discovered[mac] = DeviceBTAttrs(**attrs)
        except FileNotFoundError:
            pass

    def _on_success(self, new_attr=None):
        with open(self.filename, 'w+') as stream:
            yaml.safe_dump(self.as_dict(), stream)