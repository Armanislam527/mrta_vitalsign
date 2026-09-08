import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from env_sensors import SensorReading, read_temperature, read_noise_level


def test_noise_and_temperature_helpers_create_a_stable_tuple():
    temp = read_temperature(23.0)
    noise = read_noise_level(45.0)

    assert isinstance(temp, SensorReading)
    assert isinstance(noise, SensorReading)
    assert temp.value == 23.0
    assert noise.value == 45.0
