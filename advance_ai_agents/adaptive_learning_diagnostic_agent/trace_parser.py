def parse_steps(steps):
    """Convert a list of reasoning steps into a single string for matching."""
    return " ".join(steps).lower()