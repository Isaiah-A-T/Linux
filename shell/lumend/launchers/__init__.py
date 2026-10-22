"""Game launcher integrations. Each one lists, installs and launches games."""

from .epic import Epic
from .gog import GOG
from .steam import Steam

LAUNCHERS = {l.id: l for l in (Steam(), Epic(), GOG())}
