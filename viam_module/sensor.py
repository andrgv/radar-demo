"""Viam Sensor API adapter; acquisition and DSP live outside the SDK wrapper."""
import asyncio
from typing import ClassVar

from viam.components.sensor import Sensor
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import struct_to_dict

from .runtime import RadarRuntime, validate


class UpennMmwave(Sensor, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily('carlyworkspace', 'upenn-mmwave'), 'infineon-mmwave')

    @classmethod
    def validate_config(cls, config):
        validate(struct_to_dict(config.attributes))
        return [], []

    @classmethod
    def new(cls, config, dependencies):
        cls.validate_config(config)
        self = super().new(config, dependencies)
        self.runtime = RadarRuntime(struct_to_dict(config.attributes))
        return self

    async def get_readings(self, *, extra=None, timeout=None, **kwargs):
        return self.runtime.readings()

    async def do_command(self, command, *, timeout=None, **kwargs):
        return self.runtime.command(command)

    async def get_status(self, *, timeout=None, **kwargs):
        return self.runtime.readings()

    async def get_geometries(self, *, extra=None, timeout=None):
        return []

    async def close(self):
        await asyncio.to_thread(self.runtime.close)
