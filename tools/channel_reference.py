"""Compare exact loaded coefficients with installed official CSK reset tables."""
import json
from pathlib import Path
import re
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from radar.config import Config
from radar.recording_audit import read_register_profile,factory_matrices


def compare_reference():
    hal=ROOT.parent/'mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h'
    definitions=hal.read_text()
    addresses={name:int(value,16) for name,value in re.findall(r'#define\s+BGT60CUTR13B_REG_(MD_CAL_MAT_[HE]_\d+)\s+(0x[0-9a-fA-F]+)',definitions)}
    defaults={name:int(value,16) for name,value in re.findall(r'#define\s+BGT60CUTR13B_REG_(MD_CAL_MAT_[HE]_\d+)_rst\s+(0x[0-9a-fA-F]+)',definitions)}
    registers,_=read_register_profile(ROOT/'firmware/vendor/presence_detection_tracking.h')
    rows=[dict(register=name,address=hex(address),loaded_word=hex(registers[address]),
               official_reset_word=hex(defaults[name]),exact_match=registers[address]==defaults[name])
          for name,address in sorted(addresses.items())]
    matrices=factory_matrices(registers)
    combined=np.array([matrices['H'][0],matrices['H'][1],matrices['E'][1]])
    current=Config.load(ROOT/'configs/range-vendor-matrix-experimental.json').angle_matrix
    return dict(source='Installed Infineon sensor-xensiv-bgt60cutrxx release-v1.1.0 register HAL and README Calibration matrix update; defaults documented for plain CSK wing.',
        words=rows,all_words_match=all(r['exact_match'] for r in rows),
        current_combined_matrix_matches_loaded_candidate=bool(np.allclose(combined,current,rtol=0,atol=1e-15)),
        common_reference_row=bool(np.array_equal(matrices['H'][0],matrices['E'][0])),
        H_real=matrices['H'].real.tolist(),H_imag=matrices['H'].imag.tolist(),
        E_real=matrices['E'].real.tolist(),E_imag=matrices['E'].imag.tolist(),
        assumptions=['Upper/A halfword interpreted as real and lower/B as imaginary; HAL labels alone do not prove this convention.',
            'The reference describes plane-specific calibrated channels; combining them into a single equal-amplitude 3D steering manifold is an additional assumption.',
            'Exact coefficient equality does not establish physical stream-to-RX assignment, phase sign, sensor orientation or validity with a housing/table.',
            'Known target POSITION changes, not only rotations of the plate normal, are required to test angle signs. Body and other objects remain scene content; do not label the whole scene as only the target.'])


if __name__=='__main__':
    result=compare_reference();out=ROOT/'artifacts/qualification';out.mkdir(parents=True,exist_ok=True)
    (out/'channel-reference.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['all_words_match','current_combined_matrix_matches_loaded_candidate','common_reference_row']},indent=2))
