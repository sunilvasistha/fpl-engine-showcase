class ShowcaseError(ValueError):
    """Raised when a showcase contract or operation is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShowcaseError(message)
