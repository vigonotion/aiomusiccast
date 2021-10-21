from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict


class EntityTypes(Enum):
    REGULAR = 1
    CONFIG = 2
    DIAGNOSTIC = 3


class ConfigFeature(ABC):
    id: str
    name: str
    entity_type: EntityTypes
    get_current: Callable

    def __init__(self, id, name, entity_type, get_current):
        self.id = id
        self.name = name
        self.entity_type = entity_type
        self.get_current = get_current

    @property
    def current(self) -> Any:
        return self.get_current()


class SetableConfigFeature(ConfigFeature, ABC):
    set_current: Callable

    def __init__(self, id, name, entity_type, get_current, set_current):
        super().__init__(id, name, entity_type, get_current)
        self.set_current = set_current

    async def set(self, value):
        await self.set_current(value)


class NumberSensor(ConfigFeature):
    pass


class BinarySensor(ConfigFeature):
    pass


class TextSensor(ConfigFeature):
    pass


class NumberSetter(SetableConfigFeature):
    min_value: float
    max_value: float
    step: float

    def __init__(self, id, name, entity_type, get_current, set_current, min_value, max_value, step):
        super().__init__(id, name, entity_type, get_current, set_current)
        self.min_value = min_value
        self.max_value = max_value
        self.step = step


class OptionSetter(SetableConfigFeature):
    options: Dict[str, str]

    def __init__(self, id, name, entity_type, get_current, set_current, options):
        super().__init__(id, name, entity_type, get_current, set_current)
        self.options = options


class BinarySetter(SetableConfigFeature):
    pass
