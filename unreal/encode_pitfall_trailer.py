"""Encode the ten-second PitFall movie with an original ambient sound bed.

Uses Python's standard library and the installed FFmpeg executable.
All generated media stays in the project's ignored Saved directory.
"""
import argparse
from array import array
import math
from pathlib import Path
import random
import subprocess
import sys
import wave

DURATION = 10
FPS = 24
SAMPLE_RATE = 48000
SAVED = Path(__file__).resolve().parent/'ResonanceVR'/'Saved'/'PitFallTrailer'


def ambience(destination):
    rng=random.Random(6046)
    samples=array('h')
    low=0.
    for i in range(DURATION*SAMPLE_RATE):
        t=i/SAMPLE_RATE
        noise=rng.uniform(-1.,1.)
        low=.965*low+.035*noise
        breath=.72+.28*math.sin(math.tau*t*.19)
        drone=(.065*math.sin(math.tau*47*t)+.026*math.sin(math.tau*71*t)
               +.018*math.sin(math.tau*94*t))*breath
        wind=low*(.11+.07*min(1.,t/8))+noise*.006
        age=(t-1.)%2.8
        warning=.018*math.sin(math.tau*220*t)*math.exp(-age*9) if age<.65 else 0.
        fade=min(1.,t/.6,(DURATION-t)/.8)
        value=(drone+wind+warning)*max(0.,fade)
        samples.append(round(max(-1.,min(1.,value))*32767))
    if sys.byteorder != 'little':
        samples.byteswap()
    with wave.open(str(destination),'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(samples.tobytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--frames',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    frames=args.frames or SAVED/('Preview' if args.preview else 'Frames4K')
    output=args.output or SAVED/('PitFall-Trailer-Preview.mp4' if args.preview else 'PitFall-Trailer-4K.mp4')
    expected=[frames/f'PitFall.{i:04d}.png' for i in range(FPS*DURATION)]
    missing=[str(p) for p in expected if not p.is_file()]
    if missing:
        raise SystemExit('Incomplete render: '+missing[0])
    SAVED.mkdir(parents=True,exist_ok=True)
    sound=SAVED/'PitFall-Ambience.wav'
    ambience(sound)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-n',
        '-framerate',str(FPS),'-start_number','0','-i',str(frames/'PitFall.%04d.png'),
        '-i',str(sound),'-vf','fade=t=in:st=0:d=0.3,fade=t=out:st=9.3:d=0.7',
        '-t',str(DURATION),'-c:v','libx264','-preset','slow','-crf','16',
        '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True)
    print(output)


if __name__=='__main__':
    main()
