"""Shared fixtures for supervisor tests."""
import pytest
from supervisor.service_table import ManagedService, ServiceState


@pytest.fixture
def svc() -> ManagedService:
    return ManagedService(
        name="player",
        healthz_url="http://player:8080/healthz",
        container_name="player",
        priority="critical",
    )


@pytest.fixture
def state(svc: ManagedService) -> ServiceState:
    return ServiceState(name=svc.name)
