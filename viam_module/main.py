import asyncio
import json
import sys
from viam.module.module import Module
from viam_module.sensor import UpennMmwave

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from viam_module.processing import EchoProcessor, radar_config
        from radar.synthetic import Target, generate
        cfg = radar_config({'config_path': 'configs/exploratory-roll90-phase.json'})
        result = EchoProcessor(cfg).process(generate(
            cfg, targets=[Target(float(cfg.ranges[4]))], seed=1))
        assert result['echo_count'] >= 1
        assert str(UpennMmwave.MODEL) == 'carlyworkspace:upenn-mmwave:infineon-mmwave'
        print(json.dumps(result, allow_nan=False))
    else:
        asyncio.run(Module.run_from_registry())
