"""Stage-specific public failures; messages deliberately exclude credentials."""


class PipelineError(RuntimeError):
    """A run cannot be published safely."""


class ExtractionError(PipelineError):
    """The source is unavailable, incomplete, or structurally different."""


class QualityError(PipelineError):
    """A dataset violates the consumer contract."""


class LoadError(PipelineError):
    """A destination could not commit or verify its snapshot."""
