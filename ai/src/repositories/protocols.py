from typing import Any, Protocol


class StateRepository(Protocol):
    def get(self, camera_id: str) -> dict[str, Any]: ...

    def set_bowl_position(self, camera_id: str, bowl: dict[str, int]) -> None: ...
