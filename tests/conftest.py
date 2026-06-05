import pytest
import fakeredis

@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)