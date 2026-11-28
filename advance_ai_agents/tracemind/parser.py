def parse_trace(trace: str) -> list[str]:
    """Split a student's reasoning trace into individual steps."""
    steps = []

    for line in trace.splitlines():
        step = line.strip()
        if step:
            steps.append(step)

    return steps
