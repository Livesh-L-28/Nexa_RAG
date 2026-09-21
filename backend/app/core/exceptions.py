"""Custom domain exceptions and error codes."""

from typing import Any

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base exception for all application-level errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


class DocumentNotFoundError(AppException):
    def __init__(self, message: str = "The requested document does not exist."):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="DOCUMENT_NOT_FOUND",
            message=message,
        )


class DocumentProcessingError(AppException):
    def __init__(self, message: str = "Failed to process the document."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="DOCUMENT_PROCESSING_FAILED",
            message=message,
        )


class InvalidFileTypeError(AppException):
    def __init__(self, message: str = "Unsupported file type."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_FILE_TYPE",
            message=message,
        )


class FileTooLargeError(AppException):
    def __init__(self, message: str = "File size exceeds allowed limit."):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="FILE_TOO_LARGE",
            message=message,
        )


class UserAlreadyExistsError(AppException):
    def __init__(self, message: str = "A user with this email already exists."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="USER_ALREADY_EXISTS",
            message=message,
        )


class InvalidCredentialsError(AppException):
    def __init__(self, message: str = "Invalid email or password."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message=message,
        )


class UnauthorizedAccessError(AppException):
    def __init__(self, message: str = "Could not validate authentication credentials."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message,
        )


class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class SessionNotFoundError(AppException):
    def __init__(self, message: str = "The requested chat session does not exist."):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SESSION_NOT_FOUND",
            message=message,
        )


class VectorDimensionMismatchError(AppException):
    def __init__(self, expected: int, actual: int):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="VECTOR_DIMENSION_MISMATCH",
            message=f"Embedding dimension mismatch: expected {expected}, received {actual}.",
        )


class LLMProviderError(AppException):
    def __init__(self, message: str = "Error interacting with language model provider."):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="LLM_PROVIDER_ERROR",
            message=message,
        )


# Backward-compatible aliases
AuthenticationException = UnauthorizedAccessError
AuthorizationException = ForbiddenError
ConflictException = UserAlreadyExistsError
FileValidationException = InvalidFileTypeError
LLMException = LLMProviderError
