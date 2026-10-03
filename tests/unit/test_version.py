import re

import musegauge


def test_version_is_set():
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", musegauge.__version__)
