"""Authored bounded facial showcase, not audio emotion recognition.

Only upper face, cheeks and nose are owned here. ACE retains mouth/jaw control.
The builder bakes these trajectories into native Unreal CurveFloat assets.
"""
DURATION = 36.0
CHANNELS = (
    'EyeBlinkLeft', 'EyeBlinkRight', 'EyeWideLeft', 'EyeWideRight',
    'EyeSquintLeft', 'EyeSquintRight', 'BrowInnerUp',
    'BrowOuterUpLeft', 'BrowOuterUpRight', 'BrowDownLeft', 'BrowDownRight',
    'CheekSquintLeft', 'CheekSquintRight', 'NoseSneerLeft', 'NoseSneerRight',
)
BLINKS = (1.5, 5.8, 10.3, 15.9, 20.9, 25.9, 30.3, 34.8)
PHASES = (
    (0.0, 'Speech with subtle brows + natural blinking'),
    (12.0, 'Raised brows + wide eyes / forehead wrinkles'),
    (17.0, 'Puzzled brow / forehead furrow'),
    (22.0, 'Eyelid squint + cheek raise'),
    (27.0, 'Nose wrinkle / sneer'),
    (31.0, 'Asymmetric questioning brow'),
    (35.0, 'Return to neutral'),
)


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def envelope(t, start, end, fade=0.65):
    return smooth((t - start) / fade) * smooth((end - t) / fade)


def values(seconds):
    t = max(0.0, seconds) % DURATION
    blink = max((envelope(t, b, b + 0.28, 0.12) for b in BLINKS), default=0.0)
    raised = 0.25 * envelope(t, 3.0, 6.5) + 0.8 * envelope(t, 12.2, 16.5)
    furrow = 0.18 * envelope(t, 7.0, 10.0) + 0.75 * envelope(t, 17.2, 21.5)
    squint = envelope(t, 22.2, 26.5)
    nose = envelope(t, 27.2, 30.5)
    asymmetric = envelope(t, 31.2, 34.5)
    open_eyes = 1.0 - blink
    return dict(zip(CHANNELS, (
        blink, blink, raised * 0.65 * open_eyes, raised * 0.65 * open_eyes,
        squint * 0.65 * open_eyes, squint * 0.65 * open_eyes,
        raised * 0.8, raised + asymmetric * 0.8, raised,
        furrow, furrow + asymmetric * 0.5,
        squint * 0.75 + nose * 0.2, squint * 0.75 + nose * 0.2,
        nose * 0.8, nose * 0.8,
    )))
