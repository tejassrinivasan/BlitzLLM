"""
Custom exceptions for BlitzAgent-Agno.

This module defines all custom exception classes used throughout the package
for better error handling and debugging.
"""

from typing import Any, Dict, Optional


class BlitzAgentError(Exception):
    """Base exception class for all BlitzAgent-Agno errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(BlitzAgentError):
    """Raised when there's an error in configuration."""
    
    def __init__(self, message: str, config_section: Optional[str] = None, **kwargs) -> None:
        details = kwargs
        if config_section:
            details["config_section"] = config_section
        super().__init__(message, details)


class ModelError(BlitzAgentError):
    """Raised when there's an error with the language model."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if model_name:
            details["model_name"] = model_name
        if provider:
            details["provider"] = provider
        super().__init__(message, details)


class MemoryError(BlitzAgentError):
    """Raised when there's an error with the memory system."""
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if session_id:
            details["session_id"] = session_id
        if user_id:
            details["user_id"] = user_id
        super().__init__(message, details)


class MCPError(BlitzAgentError):
    """Raised when there's an error with MCP operations."""
    
    def __init__(
        self,
        message: str,
        server_url: Optional[str] = None,
        tool_name: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if server_url:
            details["server_url"] = server_url
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(message, details)


class MCPConnectionError(MCPError):
    """Raised when there's an error connecting to MCP server."""
    pass


class MCPTimeoutError(MCPError):
    """Raised when MCP operation times out."""
    pass


class ToolError(BlitzAgentError):
    """Raised when there's an error with tool execution."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if tool_name:
            details["tool_name"] = tool_name
        if tool_params:
            details["tool_params"] = tool_params
        super().__init__(message, details)


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""
    pass


class ToolRegistrationError(ToolError):
    """Raised when tool registration fails."""
    pass


class MetricsError(BlitzAgentError):
    """Raised when there's an error with metrics collection."""
    
    def __init__(
        self,
        message: str,
        metric_name: Optional[str] = None,
        metric_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if metric_name:
            details["metric_name"] = metric_name
        if metric_type:
            details["metric_type"] = metric_type
        super().__init__(message, details)


class DatabaseError(BlitzAgentError):
    """Raised when there's an error with database operations."""
    
    def __init__(
        self,
        message: str,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if table_name:
            details["table_name"] = table_name
        if operation:
            details["operation"] = operation
        super().__init__(message, details)


class AuthenticationError(BlitzAgentError):
    """Raised when there's an authentication error."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        auth_method: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if user_id:
            details["user_id"] = user_id
        if auth_method:
            details["auth_method"] = auth_method
        super().__init__(message, details)


class AuthorizationError(BlitzAgentError):
    """Raised when there's an authorization error."""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if user_id:
            details["user_id"] = user_id
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action
        super().__init__(message, details)


class ValidationError(BlitzAgentError):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if field_name:
            details["field_name"] = field_name
        if field_value is not None:
            details["field_value"] = field_value
        super().__init__(message, details)


class TimeoutError(BlitzAgentError):
    """Raised when an operation times out."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation
        super().__init__(message, details)


class RateLimitError(BlitzAgentError):
    """Raised when rate limits are exceeded."""
    
    def __init__(
        self,
        message: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if limit:
            details["limit"] = limit
        if window_seconds:
            details["window_seconds"] = window_seconds
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details)


class ConnectionError(BlitzAgentError):
    """Raised when there's a connection error."""
    
    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if host:
            details["host"] = host
        if port:
            details["port"] = port
        if protocol:
            details["protocol"] = protocol
        super().__init__(message, details)


class SerializationError(BlitzAgentError):
    """Raised when there's a serialization/deserialization error."""
    
    def __init__(
        self,
        message: str,
        data_type: Optional[str] = None,
        format_type: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs
        if data_type:
            details["data_type"] = data_type
        if format_type:
            details["format_type"] = format_type
        super().__init__(message, details)


# Exception mapping for HTTP status codes
HTTP_EXCEPTION_MAP = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: BlitzAgentError,
    408: TimeoutError,
    429: RateLimitError,
    500: BlitzAgentError,
    502: ConnectionError,
    503: BlitzAgentError,
    504: TimeoutError,
}


def create_http_exception(status_code: int, message: str, **kwargs) -> BlitzAgentError:
    """Create appropriate exception based on HTTP status code."""
    exception_class = HTTP_EXCEPTION_MAP.get(status_code, BlitzAgentError)
    return exception_class(message, **kwargs)


def handle_exception(func):
    """Decorator to handle and log exceptions consistently."""
    import functools
    import structlog
    
    logger = structlog.get_logger()
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BlitzAgentError as e:
            logger.error(
                "BlitzAgent error",
                function=func.__name__,
                error_type=e.__class__.__name__,
                message=e.message,
                details=e.details,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error",
                function=func.__name__,
                error_type=e.__class__.__name__,
                message=str(e),
            )
            # Convert to BlitzAgent error
            raise BlitzAgentError(f"Unexpected error in {func.__name__}: {str(e)}")
    
    return wrapper


def handle_async_exception(func):
    """Decorator to handle and log exceptions consistently for async functions."""
    import functools
    import structlog
    
    logger = structlog.get_logger()
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BlitzAgentError as e:
            logger.error(
                "BlitzAgent error",
                function=func.__name__,
                error_type=e.__class__.__name__,
                message=e.message,
                details=e.details,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error",
                function=func.__name__,
                error_type=e.__class__.__name__,
                message=str(e),
            )
            # Convert to BlitzAgent error
            raise BlitzAgentError(f"Unexpected error in {func.__name__}: {str(e)}")
    
    return wrapper 