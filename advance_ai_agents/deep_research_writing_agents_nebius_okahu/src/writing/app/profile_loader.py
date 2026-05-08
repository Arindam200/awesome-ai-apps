"""Profile loading from shipped markdown files."""

import logging

from writing.config.constants import PROFILES_DIR
from writing.models.schemas import Profile, Profiles

logger = logging.getLogger(__name__)


def load_profiles() -> Profiles:
    """Load all writing profiles from the shipped markdown files.

    Returns:
        A Profiles container with structure, terminology, character,
        and branding profiles.

    Raises:
        FileNotFoundError: If a profile file is missing.
    """

    structure_path = PROFILES_DIR / "structure_profile.md"
    terminology_path = PROFILES_DIR / "terminology_profile.md"
    character_path = PROFILES_DIR / "character_profile.md"
    branding_path = PROFILES_DIR / "branding_profile.md"

    for path in [structure_path, terminology_path, character_path, branding_path]:
        if not path.exists():
            msg = f"Profile file not found: {path}"
            raise FileNotFoundError(msg)

    return Profiles(
        structure=Profile(
            name="structure_profile",
            content=structure_path.read_text(encoding="utf-8"),
        ),
        terminology=Profile(
            name="terminology_profile",
            content=terminology_path.read_text(encoding="utf-8"),
        ),
        character=Profile(
            name="character_profile",
            content=character_path.read_text(encoding="utf-8"),
        ),
        branding=Profile(
            name="branding_profile",
            content=branding_path.read_text(encoding="utf-8"),
        ),
    )
