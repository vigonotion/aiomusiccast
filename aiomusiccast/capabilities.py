from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict


class EntityTypes(Enum):
    REGULAR = 1
    CONFIG = 2
    DIAGNOSTIC = 3
    SYSTEM = 4


class Capability(ABC):
    id: str
    name: str
    entity_type: EntityTypes
    get_current: Callable

    def __init__(self, capability_id, name, entity_type, get_current):
        self.id = capability_id
        self.name = name
        self.entity_type = entity_type
        self.get_current = get_current

    @property
    def current(self) -> Any:
        return self.get_current()


class SetableCapability(Capability, ABC):
    set_current: Callable

    def __init__(self, capability_id, name, entity_type, get_current, set_current):
        super().__init__(capability_id, name, entity_type, get_current)
        self.set_current = set_current

    async def set(self, value):
        await self.set_current(value)


class NumberSensor(Capability):
    pass


class BinarySensor(Capability):
    pass


class TextSensor(Capability):
    pass


class NumberSetter(SetableCapability):
    min_value: float
    max_value: float
    step: float

    def __init__(self, capability_id, name, entity_type, get_current, set_current, min_value, max_value, step):
        super().__init__(capability_id, name, entity_type, get_current, set_current)
        self.min_value = min_value
        self.max_value = max_value
        self.step = step


class OptionSetter(SetableCapability):
    options: Dict[str, str]

    def __init__(self, capability_id, name, entity_type, get_current, set_current, options):
        super().__init__(capability_id, name, entity_type, get_current, set_current)
        self.options = options
        
    async def set(self, value):
        if value not in self.options.keys():
            raise ValueError("The given value is not a valid option")
        await super(OptionSetter, self).set(value)


class BinarySetter(SetableCapability):
    pass
