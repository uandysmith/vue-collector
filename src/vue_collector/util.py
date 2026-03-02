import hashlib


class VueSectionError(ValueError):
    """Raised when a .vue component section contains invalid content.

    Attributes:
        file_name: The .vue file that triggered the error.
        section:   'template', 'script', 'style', or None for file-level issues.
        message:   Human-readable description of the problem.
    """

    def __init__(self, file_name: str, section: str | None, message: str) -> None:
        self.file_name = file_name
        self.section = section
        self.message = message
        loc = f'{file_name} [{section}]' if section else file_name
        super().__init__(f'{loc}: {message}')


def _make_template_name(name: str) -> str:
    """Convert a component file name (without .vue) to a template id.

    Example: 'MyComponent' → 'template-my-component'
    """
    return 'template' + ''.join(f'-{x.lower()}' if x.capitalize() == x else x for x in name)


def _make_scope_id(file_name: str) -> str:
    """Return the first 8 hex chars of the SHA-256 hash of file_name."""
    return hashlib.sha256(file_name.encode()).hexdigest()[:8]
