"""Provider-independent safe failure metadata; never raw headers, paths or response text."""


class SourceError(Exception):
    def __init__(
        self, code: str, *, status: int | None = None, retry_after_seconds: int | None = None
    ):
        self.code, self.status, self.retry_after_seconds = code, status, retry_after_seconds
        super().__init__(code)
