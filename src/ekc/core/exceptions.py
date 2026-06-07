from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class LLMTimeoutError(Exception):
    """Raised when Ollama does not respond within the timeout window."""
    pass


class LLMUnavailableError(Exception):
    """Raised when Ollama is unreachable."""
    pass


class IngestionError(Exception):
    """Raised when the ingestion pipeline fails for a document."""
    pass