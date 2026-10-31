"""One bounded acquisition per reservation; retries remain an explicit operator decision."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.gate import DatabaseGate
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.public_sources import repository
from arbit_data.public_sources.repository import ObservationResult
from arbit_data.public_sources.requests import SourceRequest, validate_request
from arbit_data.public_sources.transport import PublicResponse


class Transport(Protocol):
    def fetch(self, request: SourceRequest) -> PublicResponse: ...


class SourceService:
    def __init__(
        self,
        uow: UnitOfWork,
        store: ObjectStore,
        transport: Transport,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.uow, self.store, self.transport, self.clock = uow, store, transport, clock

    def acquire(
        self, request: SourceRequest, normalize: Callable[[Any], dict[str, Any]]
    ) -> ObservationResult:
        validate_request(request)
        now = self.clock()
        saved = repository.current(self.uow, self.store, request, now)
        if saved is not None and not saved.stale:
            return saved
        try:
            reservation = repository.reserve(self.uow, request, now)
        except SourceError:
            saved = repository.current(self.uow, self.store, request, now)
            if saved is not None:
                return saved
            raise
        try:
            with DatabaseGate(self.uow, provider=request.provider).request():
                response = self.transport.fetch(request)
            normalized = normalize(response.payload)
            return repository.publish(
                self.uow, self.store, request, reservation, response, normalized, self.clock()
            )
        except (SourceError, ValueError, OSError) as error:
            safe = error if isinstance(error, SourceError) else SourceError("VALIDATION_FAILED")
            repository.fail(self.uow, request, reservation, safe, self.clock())
            saved = repository.current(self.uow, self.store, request, self.clock())
            if saved is not None:
                return saved
            raise safe from None
