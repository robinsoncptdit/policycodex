from dataclasses import dataclass


@dataclass
class _StubState:
    next_url: str = "/catalog/"


def lifecycle_state(request):
    return _StubState()
