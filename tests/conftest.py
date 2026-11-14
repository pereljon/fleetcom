import pytest

from fleetcom import db


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "fleetcom.db"), create=True)
    db.migrate(c)
    yield c
    c.close()
