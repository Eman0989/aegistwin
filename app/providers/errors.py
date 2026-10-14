
class ProviderError(RuntimeError):
    """Error raised when a model provider fails."""

    def __init__(
        self,
        message: str,
        code: str = "provider_error",
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
