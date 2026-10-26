"""Independent PPAC business module; never imports Area or Traffic."""
from .service import calculate
__all__ = ['calculate']
