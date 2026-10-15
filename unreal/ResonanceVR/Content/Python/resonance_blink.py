"""Bounded blink profile; runtime Blueprint samples random pauses/durations."""

FIRST_PAUSE = (1.5, 4.0)
PAUSE = (2.8, 6.5)
DURATION = (0.24, 0.34)
STRENGTH = (0.96, 1.0)


def closure(phase):
    """Fast close, brief hold, slower reopening; zero outside one blink."""
    def smooth(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3.0 - 2.0 * x)
    return smooth(phase / 0.22) * (1.0 - smooth((phase - 0.32) / 0.68))
