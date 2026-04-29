"""
Video Renderer Agent - PATCHED: BUG FIX + OUTRO SUPPORT
========================================================
Changes in this version:

  BUG FIX
  - Fixed TypeError in build_ducked_music / make_frame.
    MoviePy passes `t` as a numpy array; we now handle both
    scalar and array cases correctly.

  NEW: OUTRO FRAME
  - 3-second "follow / like" end card, mirroring the hook style.
  - Outro TTS is controlled SEPARATELY from scene TTS:
      --outro-tts / --no-outro-tts
      OUTRO_TTS_ENABLED=true env var
  - This means you can have scene narration ON + outro TTS OFF,
    or any combination.

CLI examples:
    python scripts/video_renderer.py
    python scripts/video_renderer.py --no-upload
    python scripts/video_renderer.py --tts --no-outro-tts
    python scripts/video_renderer.py --no-tts --outro-tts
    python scripts/video_renderer.py --no-upload --tts --voice en-GB-RyanNeural
"""

import argparse
import asyncio
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

# ── deps ──────────────────────────────────────────────────────────────────────
try:
    import moviepy
    from moviepy.editor import (
        TextClip, CompositeVideoClip, ImageClip,
        AudioFileClip, concatenate_videoclips, concatenate_audioclips,
    )
    from moviepy.audio.fx.all import audio_fadeout, audio_fadein
    from moviepy.audio.AudioClip import AudioClip, CompositeAudioClip
    MOVIEPY_AVAILABLE = True
    print("✅ MoviePy loaded successfully")
except ImportError as e:
    print(f"❌ MoviePy import error: {e}")
    MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw
    import numpy as np
    if not hasattr(Image, "ANTIALIAS"):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    PIL_AVAILABLE = True
    print("✅ Pillow loaded successfully")
except ImportError:
    PIL_AVAILABLE = False
    print("❌ Pillow not installed")

try:
    import edge_tts as _edge_tts_check
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

# =============================================================================
# VIDEO SETTINGS
# =============================================================================
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS          = 30

AUDIO_DIR    = "assets/audio"
MUSIC_VOLUME = 0.30

SCENE_CROSSFADE    = 0.35
TEXT_ENTRANCE_TIME = 0.60
TEXT_EXIT_TIME     = 0.30

COLORS_HEX = {
    "white":  "#FFFFFF",
    "orange": "#F97316",
    "blue":   "#3B82F6",
    "purple": "#8B5CF6",
    "yellow": "#FBBF24",
    "cyan":   "#06B6D4",
    "red":    "#EF4444",
    "green":  "#22C55E",
}

# =============================================================================
# HOOK / OUTRO / TTS SETTINGS
# =============================================================================
HOOK_DURATION     = 3.0
OUTRO_DURATION    = 4.0              # seconds for the outro end card
TTS_TAIL_DELAY    = 0.5
TTS_VOICE_DEFAULT = "en-US-GuyNeural"
DUCK_LEVEL        = 0.25
DUCK_FADE_SEC     = 0.25

# Default outro TTS text  (can be overridden via OUTRO_TTS_TEXT env var)
OUTRO_TTS_TEXT_DEFAULT = (
    "Like and subscribe for more mind-blowing space facts every day!"
)

# =============================================================================
# CLI
# =============================================================================
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="SpacePulse207 Video Renderer")
    p.add_argument("--no-upload", action="store_true",
                   help="Skip YouTube upload (test mode). Also: NO_UPLOAD=1")

    # ── scene TTS ──
    p.add_argument("--tts",    dest="tts", action="store_true",  default=None,
                   help="Enable Edge-TTS narration for scenes")
    p.add_argument("--no-tts", dest="tts", action="store_false",
                   help="Disable Edge-TTS narration for scenes")
    p.add_argument("--voice", default=None,
                   help=f"Edge-TTS voice (default: {TTS_VOICE_DEFAULT})")

    # ── outro TTS  (independent toggle) ──
    p.add_argument("--outro-tts",    dest="outro_tts", action="store_true",  default=None,
                   help="Enable TTS for the outro card")
    p.add_argument("--no-outro-tts", dest="outro_tts", action="store_false",
                   help="Disable TTS for the outro card (default)")

    return p.parse_args(argv)


def resolve_flags(args):
    no_upload = args.no_upload or os.environ.get("NO_UPLOAD","").lower() in ("1","true","yes")

    # scene TTS
    if args.tts is not None:
        tts_enabled = args.tts
    else:
        tts_enabled = os.environ.get("TTS_ENABLED","false").lower() in ("1","true","yes")

    voice = args.voice or os.environ.get("TTS_VOICE", TTS_VOICE_DEFAULT)

    # outro TTS (separate flag)
    if args.outro_tts is not None:
        outro_tts = args.outro_tts
    else:
        outro_tts = os.environ.get("OUTRO_TTS_ENABLED","false").lower() in ("1","true","yes")

    return no_upload, tts_enabled, voice, outro_tts

# =============================================================================
# AUDIO HELPERS
# =============================================================================
def get_available_music():
    music_files = []
    if os.path.exists(AUDIO_DIR):
        for f in os.listdir(AUDIO_DIR):
            if f.lower().endswith((".mp3",".wav",".ogg",".m4a")):
                music_files.append(os.path.join(AUDIO_DIR, f))
    return music_files


def select_random_music():
    music_files = get_available_music()
    if not music_files:
        print("⚠️ No music files found in assets/audio/")
        return None
    selected = random.choice(music_files)
    print(f"🎵 Selected music: {os.path.basename(selected)}")
    return selected


def add_background_music(video_clip, music_path, volume=MUSIC_VOLUME):
    if not music_path or not os.path.exists(music_path):
        print("⚠️ No music file available, video will be silent")
        return video_clip, None
    try:
        audio = AudioFileClip(music_path)
        video_duration = video_clip.duration
        if audio.duration < video_duration:
            loops_needed = int(video_duration / audio.duration) + 1
            audio = concatenate_audioclips([audio] * loops_needed)
        audio = audio.subclip(0, video_duration)
        audio = audio.volumex(volume)
        audio = audio_fadein(audio, 0.5)
        audio = audio_fadeout(audio, 1.0)
        video_with_audio = video_clip.set_audio(audio)
        print(f"✅ Added background music ({video_duration:.1f}s)")
        return video_with_audio, audio
    except Exception as e:
        print(f"⚠️ Could not add music: {e}")
        return video_clip, None

# =============================================================================
# TTS HELPERS
# =============================================================================
async def _tts_save(text, path, voice):
    import edge_tts
    comm = edge_tts.Communicate(text, voice)
    await comm.save(path)


def generate_tts_audio(text, path, voice):
    """Generate TTS audio. Returns duration in seconds, or 0.0 on failure."""
    if not EDGE_TTS_AVAILABLE:
        print("⚠️ edge-tts not installed — pip install edge-tts")
        return 0.0
    try:
        asyncio.run(_tts_save(text, path, voice))
        result = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json","-show_streams", path],
            capture_output=True, text=True)
        dur = float(json.loads(result.stdout)["streams"][0]["duration"])
        print(f"   🎙️ TTS '{text[:40]}...' → {dur:.2f}s")
        return dur
    except Exception as e:
        print(f"⚠️ TTS generation failed: {e}")
        return 0.0


def make_silence_mp3(path, duration):
    subprocess.run([
        "ffmpeg","-y","-f","lavfi",
        "-i","anullsrc=r=44100:cl=mono",
        "-t", str(duration),"-c:a","libmp3lame","-q:a","9", path
    ], capture_output=True)


def concat_audio_files(file_list, output):
    list_path = output + ".list.txt"
    with open(list_path,"w") as f:
        for fp in file_list:
            f.write(f"file '{fp}'\n")
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0",
        "-i", list_path,"-c","copy", output
    ], capture_output=True)
    os.remove(list_path)


def get_audio_duration(path):
    result = subprocess.run(
        ["ffprobe","-v","quiet","-print_format","json","-show_format", path],
        capture_output=True, text=True)
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0

# =============================================================================
# AUDIO DUCKING  ← BUG FIXED HERE
# =============================================================================
def build_ducked_music(music_path, video_duration, tts_segments):
    """
    Return an AudioClip where the music dips to DUCK_LEVEL during TTS segments.
    tts_segments: list of (start_sec, end_sec).

    FIX: MoviePy can call make_frame(t) with t as a numpy array.
    We handle both scalar and array cases.
    """
    if not music_path or not os.path.exists(music_path):
        return None
    try:
        music = AudioFileClip(music_path)
        if music.duration < video_duration:
            loops = int(video_duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        music = music.subclip(0, video_duration)
        music = audio_fadein(music, 0.5)
        music = audio_fadeout(music, 1.0)

        n_frames = int(video_duration * FPS) + 2
        vol      = np.ones(n_frames, dtype=np.float64) * MUSIC_VOLUME
        fade_f   = max(1, int(DUCK_FADE_SEC * FPS))

        for seg_start, seg_end in tts_segments:
            s = int(seg_start * FPS)
            e = int(seg_end   * FPS)
            vol[s:e] = MUSIC_VOLUME * DUCK_LEVEL
            for i in range(fade_f):
                idx = s - fade_f + i
                if 0 <= idx < n_frames:
                    t_ratio = i / fade_f
                    vol[idx] = MUSIC_VOLUME * (1 - t_ratio * (1 - DUCK_LEVEL))
            for i in range(fade_f):
                idx = e + i
                if 0 <= idx < n_frames:
                    t_ratio = i / fade_f
                    vol[idx] = MUSIC_VOLUME * (DUCK_LEVEL + t_ratio * (1 - DUCK_LEVEL))

        music_fps = music.fps

        # ── FIXED make_frame ──────────────────────────────────────────────
        def make_frame(t):
            raw = music.get_frame(t)
            if isinstance(t, np.ndarray):
                # t is an array of time values → vectorised lookup
                idxs = np.clip((t * FPS).astype(int), 0, n_frames - 1)
                gains = vol[idxs]                    # shape (N,)
                # raw shape is (N, channels); gains shape (N,) → broadcast
                if raw.ndim == 2:
                    return raw * gains[:, np.newaxis]
                return raw * gains
            else:
                # t is a scalar
                idx = int(min(t * FPS, n_frames - 1))
                idx = max(0, idx)
                return raw * float(vol[idx])

        ducked = AudioClip(make_frame, duration=video_duration, fps=music_fps)
        return ducked
    except Exception as e:
        print(f"⚠️ Audio ducking failed, using flat music: {e}")
        return None

# =============================================================================
# STARFIELD BACKGROUND
# =============================================================================
def create_starfield_background(width, height, num_stars=400, seed=None):
    if seed is not None:
        random.seed(seed)
    img  = Image.new("RGB", (width, height), (3,3,12))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        dist = abs(y - height//2) / max(1, height//2)
        bc   = max(0, 12 - int(dist*8))
        draw.line([(0,y),(width,y)], fill=(3,3,bc))
    for _ in range(3):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        nc = random.choice([(20,10,30),(10,15,25),(15,10,20)])
        r  = random.randint(220, 420)
        for ri in range(r, 0, -24):
            af = 1.0 - ri/r
            draw.ellipse([cx-ri,cy-ri,cx+ri,cy+ri],
                         fill=tuple(int(c*0.12*af) for c in nc))
    for _ in range(num_stars):
        x,y = random.randint(0,width-1), random.randint(0,height-1)
        b   = random.randint(80,180)
        draw.point((x,y), fill=(b,b,min(255,b+40)))
    for _ in range(num_stars//4):
        x,y = random.randint(0,width-1), random.randint(0,height-1)
        b   = random.randint(150,220)
        sz  = random.choice([1,2,2])
        draw.ellipse([x-sz,y-sz,x+sz,y+sz], fill=(b,b,min(255,b+20)))
    for _ in range(20):
        x = random.randint(20,width-20)
        y = random.randint(20,height-20)
        for r in range(8,0,-1):
            i2 = int(100+155*(1-r/8))
            draw.ellipse([x-r,y-r,x+r,y+r], fill=(i2,i2,min(255,i2+30)))
        draw.ellipse([x-1,y-1,x+1,y+1], fill=(255,255,255))
    for _ in range(5):
        x = random.randint(50,width-50)
        y = random.randint(50,height-50)
        for dx in range(-15,16):
            i2=int(200*(1-abs(dx)/15))
            if i2>0 and 0<=x+dx<width:
                draw.point((x+dx,y), fill=(i2,i2,i2))
        for dy in range(-15,16):
            i2=int(200*(1-abs(dy)/15))
            if i2>0 and 0<=y+dy<height:
                draw.point((x,y+dy), fill=(i2,i2,i2))
        draw.ellipse([x-2,y-2,x+2,y+2], fill=(255,255,255))
    return np.array(img, dtype=np.uint8)


def create_moving_starfield_clip(duration, seed=42):
    ow = int(VIDEO_WIDTH*1.08)
    oh = int(VIDEO_HEIGHT*1.08)
    bg = create_starfield_background(ow, oh, num_stars=450, seed=seed)
    base = ImageClip(bg).set_duration(duration)
    xm = max(0,(ow-VIDEO_WIDTH)//2)
    ym = max(0,(oh-VIDEO_HEIGHT)//2)
    return base.set_position(
        lambda t: (
            -xm + int(12*math.sin((t/max(duration,0.001))*math.pi)),
            -ym + int(-24*(t/max(duration,0.001)))
        )
    )

# =============================================================================
# PLANET GENERATOR
# =============================================================================
def create_planet(planet_type, size=200):
    img    = Image.new("RGBA",(size,size),(0,0,0,0))
    draw   = ImageDraw.Draw(img)
    center = size//2
    radius = size//2-5
    schemes = {
        "earth":   {"base":(30,100,180),"secondary":(34,139,34),"highlight":(255,255,255)},
        "mars":    {"base":(193,68,14),"secondary":(139,69,19),"highlight":(210,105,30)},
        "jupiter": {"base":(255,200,150),"secondary":(210,160,120),"highlight":(255,220,180),"bands":True},
        "saturn":  {"base":(210,180,140),"secondary":(238,220,170),"highlight":(255,240,200),"rings":True},
        "venus":   {"base":(255,198,145),"secondary":(218,165,105),"highlight":(255,220,180)},
        "neptune": {"base":(70,130,200),"secondary":(100,149,237),"highlight":(135,180,255)},
        "moon":    {"base":(180,180,180),"secondary":(140,140,140),"highlight":(220,220,220)},
        "sun":     {"base":(255,200,50),"secondary":(255,150,0),"highlight":(255,255,150),"glow":True},
    }
    s = schemes.get(planet_type, schemes["earth"])
    if s.get("glow"):
        for r in range(radius+20,radius,-2):
            draw.ellipse([center-r,center-r,center+r,center+r],fill=s["highlight"])
    draw.ellipse([center-radius,center-radius,center+radius,center+radius],fill=s["base"])
    if s.get("bands"):
        bc = [s["base"],s["secondary"],s["highlight"]]
        bh = max(1,radius*2//6)
        for i in range(6):
            ys = center-radius+i*bh
            col = bc[i%len(bc)]
            for y in range(ys, min(ys+bh,center+radius)):
                dy = abs(y-center)
                if dy<radius:
                    dx=int(math.sqrt(radius**2-dy**2))
                    draw.line([(center-dx,y),(center+dx,y)],fill=col)
    rng = random.Random(planet_type)
    for _ in range(8):
        dx=rng.randint(-radius//2,radius//2)
        dy=rng.randint(-radius//2,radius//2)
        if dx**2+dy**2<(radius//2)**2:
            sp=rng.randint(5,15)
            draw.ellipse([center+dx-sp,center+dy-sp,center+dx+sp,center+dy+sp],fill=s["secondary"])
    hx,hy = center-radius//3, center-radius//3
    for r in range(radius//4,0,-2):
        draw.ellipse([hx-r,hy-r,hx+r,hy+r],fill=s["highlight"])
    if s.get("rings"):
        for r in range(int(radius*1.3),int(radius*1.8),2):
            draw.ellipse([center-r,center-8,center+r,center+8],outline=(200,180,140),width=1)
    return np.array(img, dtype=np.uint8)

# =============================================================================
# TEXT & ANIMATION
# =============================================================================
def get_fontsize(text_size):
    return {"large":76,"medium":58,"small":46}.get(text_size,58)


def get_text_base_y(position):
    if position=="top":    return 180
    if position=="bottom": return VIDEO_HEIGHT-500
    return VIDEO_HEIGHT//2-100


def create_animated_text_clip(text, duration, fontsize, position="center",
                               animation="fade_in", color="white"):
    try:
        txt = TextClip(
            text, fontsize=fontsize,
            color=COLORS_HEX.get(color,"#FFFFFF"),
            font="DejaVu-Sans-Bold",
            size=(VIDEO_WIDTH-80,None),
            method="caption", align="center",
            stroke_color="black", stroke_width=3,
        ).set_duration(duration)
        base_y = get_text_base_y(position)
        if animation=="slide_left":
            sx,ex = VIDEO_WIDTH+120,(VIDEO_WIDTH-txt.w)//2
            txt=txt.set_position(
                lambda t:(int(sx+(ex-sx)*min(t/TEXT_ENTRANCE_TIME,1.0)),base_y)
            ).crossfadein(0.18)
        elif animation=="slide_right":
            sx,ex = -txt.w-120,(VIDEO_WIDTH-txt.w)//2
            txt=txt.set_position(
                lambda t:(int(sx+(ex-sx)*min(t/TEXT_ENTRANCE_TIME,1.0)),base_y)
            ).crossfadein(0.18)
        elif animation=="zoom_in":
            txt=txt.resize(
                lambda t:0.80+0.20*min(t/TEXT_ENTRANCE_TIME,1.0)
            ).set_position(("center",base_y)).crossfadein(0.20)
        elif animation=="pulse":
            txt=txt.resize(
                lambda t:1.0+0.035*math.sin(2*math.pi*1.8*t)
            ).set_position(("center",base_y)).crossfadein(0.20)
        elif animation=="fade_out":
            txt=txt.set_position(("center",base_y)).crossfadeout(0.45)
        else:
            txt=txt.set_position(("center",base_y)).crossfadein(0.35)
        if duration>1.2 and animation!="fade_out":
            txt=txt.crossfadeout(min(TEXT_EXIT_TIME,max(0.15,duration*0.08)))
        return txt
    except Exception as e:
        print(f"⚠️ TextClip error: {e}")
        return None

# =============================================================================
# HOOK FRAME
# =============================================================================
def create_hook_clip(hook_text, sub_text=""):
    """3-second hook / thumbnail title card."""
    duration = HOOK_DURATION
    bg       = create_moving_starfield_clip(duration=duration, seed=99)
    layers   = [bg]

    #try:
    #    badge = TextClip(
    #        "SPACE FACT", fontsize=34,
    #        color="#8B5CF6", font="DejaVu-Sans-Bold",
    #        stroke_color="black", stroke_width=2,
    #        method="label",
    #    ).set_duration(duration).set_position(("center",160)).crossfadein(0.25)
    #    layers.append(badge)
    #except Exception as e:
    #    print(f"⚠️ Hook badge: {e}")

    hook_clip = create_animated_text_clip(
        hook_text.upper(), duration,
        fontsize=80, position="center",
        animation="zoom_in", color="white",
    )
    if hook_clip:
        hook_clip = hook_clip.set_position(("center", VIDEO_HEIGHT//2 - 220))
        layers.append(hook_clip)

    #try:
    #    div_arr = np.full((4, VIDEO_WIDTH-240, 4), [139,92,246,200], dtype=np.uint8)
    #    div_img = Image.fromarray(div_arr, "RGBA")
    #    div_clip = (
    #        ImageClip(np.array(div_img))
    #        .set_duration(duration)
    #        .set_position(((VIDEO_WIDTH-(VIDEO_WIDTH-240))//2, VIDEO_HEIGHT//2-55))
    #        .crossfadein(0.40)
    #    )
    #    layers.append(div_clip)
    #except Exception as e:
    #    print(f"⚠️ Hook divider: {e}")

    if sub_text:
        sub = create_animated_text_clip(
            sub_text, duration,
            fontsize=48, position="center",
            animation="fade_in", color="white",
        )
        if sub:
            sub = sub.set_position(("center", VIDEO_HEIGHT//2 - 10))
            layers.append(sub)

    scene = CompositeVideoClip(layers, size=(VIDEO_WIDTH,VIDEO_HEIGHT)).set_duration(duration)
    return scene.crossfadeout(SCENE_CROSSFADE)

# =============================================================================
# OUTRO FRAME  ← NEW
# =============================================================================
def create_outro_clip(channel_name="SpacePulse"):
    """
    4-second outro end card with:
      - Subscribe / Like CTA
      - Channel name
      - Pulsing star accent
    Design mirrors the hook but uses a gold/orange palette.
    """
    duration = OUTRO_DURATION
    bg       = create_moving_starfield_clip(duration=duration, seed=77)
    layers   = [bg]

    # ── Top label ──────────────────────────────────────────────────────────
    try:
        label = TextClip(
            "MORE SPACE FACTS DAILY", fontsize=30,
            color="#F97316", font="DejaVu-Sans-Bold",
            stroke_color="black", stroke_width=2,
            method="label",
        ).set_duration(duration).set_position(("center", 155)).crossfadein(0.30)
        layers.append(label)
    except Exception as e:
        print(f"⚠️ Outro label: {e}")

    # ── CTA line 1: "👍 LIKE if this blew your mind!" ──────────────────────
    cta1 = create_animated_text_clip(
        "👍  LIKE\nif this blew your mind!",
        duration, fontsize=68,
        position="center", animation="zoom_in", color="yellow",
    )
    if cta1:
        cta1 = cta1.set_position(("center", VIDEO_HEIGHT//2 - 340))
        layers.append(cta1)

    # ── Accent divider (orange) ─────────────────────────────────────────────
    try:
        div_arr = np.full((4, VIDEO_WIDTH-240, 4), [249,115,22,200], dtype=np.uint8)
        div_img = Image.fromarray(div_arr, "RGBA")
        div_clip = (
            ImageClip(np.array(div_img))
            .set_duration(duration)
            .set_position(((VIDEO_WIDTH-(VIDEO_WIDTH-240))//2, VIDEO_HEIGHT//2 - 100))
            .crossfadein(0.45)
        )
        layers.append(div_clip)
    except Exception as e:
        print(f"⚠️ Outro divider: {e}")

    # ── CTA line 2: "🔔 SUBSCRIBE for daily shorts" ────────────────────────
    cta2 = create_animated_text_clip(
        "🔔  FOLLOW\nfor daily space shorts",
        duration, fontsize=62,
        position="center", animation="fade_in", color="white",
    )
    if cta2:
        cta2 = cta2.set_position(("center", VIDEO_HEIGHT//2 - 20))
        layers.append(cta2)

    # ── Channel name at bottom ─────────────────────────────────────────────
    try:
        ch = TextClip(
            f"@{channel_name}", fontsize=40,
            color="#8B5CF6", font="DejaVu-Sans-Bold",
            stroke_color="black", stroke_width=2,
            method="label",
        ).set_duration(duration).set_position(("center", VIDEO_HEIGHT - 500)).crossfadein(0.50)
        layers.append(ch)
    except Exception as e:
        print(f"⚠️ Outro channel name: {e}")

    scene = CompositeVideoClip(layers, size=(VIDEO_WIDTH,VIDEO_HEIGHT)).set_duration(duration)
    return scene.crossfadein(SCENE_CROSSFADE).fadeout(0.40)

# =============================================================================
# SCENE CREATION
# =============================================================================
def get_planet_for_topic(topic, visual_hint=""):
    tl = (topic+" "+visual_hint).lower()
    for key in ("earth","mars","jupiter","saturn","venus","moon","sun"):
        if key in tl:
            return key
    if "neptune" in tl or "uranus" in tl:
        return "neptune"
    return random.choice(["earth","mars","jupiter","saturn","neptune"])


def create_scene_with_planet(scene, planet_type=None, show_planet=True, bg_seed=42):
    duration = scene.get("duration",4)
    bg_clip  = create_moving_starfield_clip(duration=duration, seed=bg_seed)
    layers   = [bg_clip]
    if show_planet and planet_type:
        pa = create_planet(planet_type, size=250)
        pc = ImageClip(pa, ismask=False).set_duration(duration)
        sn = scene.get("scene_number",1)
        if   sn%3==1: sx,sy = VIDEO_WIDTH-300, 200
        elif sn%3==2: sx,sy = 50, VIDEO_HEIGHT-450
        else:         sx,sy = VIDEO_WIDTH-280, VIDEO_HEIGHT-500
        pc = pc.set_position(
            lambda t:(sx+int(10*math.sin(2*math.pi*0.18*t)),
                      sy+int(16*math.sin(2*math.pi*0.24*t)))
        ).resize(lambda t:1.0+0.03*math.sin(2*math.pi*0.22*t)
        ).crossfadein(0.35).crossfadeout(0.25)
        layers.append(pc)
    txt = create_animated_text_clip(
        scene["text"], duration,
        get_fontsize(scene.get("text_size","medium")),
        scene.get("text_position","center"),
        scene.get("animation","fade_in"),
        "white",
    )
    if txt:
        layers.append(txt)
    return CompositeVideoClip(layers, size=(VIDEO_WIDTH,VIDEO_HEIGHT)).set_duration(duration)


def create_scene_clip(scene, idea_topic="", bg_seed=42):
    sn = scene.get("scene_number",1)
    show_planet = sn in [1,3,5]
    pt = get_planet_for_topic(idea_topic, scene.get("visual","")) if show_planet else None
    return create_scene_with_planet(scene, pt, show_planet, bg_seed+sn)

# =============================================================================
# MAIN RENDER
# =============================================================================
def render_video(script_data, output_path,
                 tts_enabled=False, voice=TTS_VOICE_DEFAULT,
                 outro_tts=False):
    if not MOVIEPY_AVAILABLE or not PIL_AVAILABLE:
        print("❌ Required libraries not available"); return None

    idea   = script_data.get("idea",{})
    script = script_data.get("script",{})
    scenes = script.get("scenes",[])
    if not scenes:
        print("❌ No scenes found in script"); return None

    topic        = idea.get("topic","Space")
    channel_name = os.environ.get("CHANNEL_NAME","SpacePulse")
    outro_text   = os.environ.get("OUTRO_TTS_TEXT", OUTRO_TTS_TEXT_DEFAULT)

    print(f"🎬 Rendering {len(scenes)} scenes  |  topic: {topic}")
    print(f"🎙️  Scene TTS : {'ON — '+voice if tts_enabled else 'OFF'}")
    print(f"🎙️  Outro TTS : {'ON' if outro_tts else 'OFF'}")

    # ── TTS pre-generation ─────────────────────────────────────────────────
    tts_tmpdir     = None
    tts_audio_path = None
    tts_segments   = []
    adjusted_scenes = []

    if tts_enabled or outro_tts:
        tts_tmpdir    = tempfile.mkdtemp(prefix="spacepulse_tts_")
        cursor        = HOOK_DURATION
        section_files = []

        # Hook silence
        hook_sil = os.path.join(tts_tmpdir, "hook_sil.mp3")
        make_silence_mp3(hook_sil, HOOK_DURATION)

        # Per-scene TTS
        for i, scene in enumerate(scenes):
            text       = scene.get("text","")
            audio_path = os.path.join(tts_tmpdir, f"scene_{i}.mp3")

            if tts_enabled:
                dur = generate_tts_audio(text, audio_path, voice)
            else:
                dur = 0.0

            if dur > 0:
                scene_dur = dur + TTS_TAIL_DELAY
                tts_segments.append((cursor, cursor + dur))
                section_files.append(audio_path)
            else:
                scene_dur = scene.get("duration", 4)
                sil_path  = os.path.join(tts_tmpdir, f"scene_{i}_sil.mp3")
                make_silence_mp3(sil_path, scene_dur)
                section_files.append(sil_path)

            adj = dict(scene)
            adj["duration"] = scene_dur
            adjusted_scenes.append(adj)
            cursor += scene_dur

        # Outro TTS
        outro_audio_path = None
        if outro_tts:
            outro_audio_path = os.path.join(tts_tmpdir, "outro.mp3")
            outro_dur = generate_tts_audio(outro_text, outro_audio_path, voice)
            if outro_dur > 0:
                tts_segments.append((cursor, cursor + outro_dur))
            else:
                outro_audio_path = None
        # Outro silence pad (always needed for concat)
        outro_sil = os.path.join(tts_tmpdir, "outro_sil.mp3")
        make_silence_mp3(outro_sil, OUTRO_DURATION)
        if outro_audio_path:
            section_files.append(outro_audio_path)
        else:
            section_files.append(outro_sil)

        combined = os.path.join(tts_tmpdir, "narration.mp3")
        concat_audio_files([hook_sil] + section_files, combined)
        tts_audio_path = combined
        print(f"✅ TTS ready ({get_audio_duration(combined):.1f}s total)")
    else:
        adjusted_scenes = scenes

    # ── Build scene clips ──────────────────────────────────────────────────
    print(f"\n🖼️  Building scene clips...")
    total_duration = HOOK_DURATION
    scene_clips    = []

    for i, scene in enumerate(adjusted_scenes):
        sn  = scene.get("scene_number", i+1)
        dur = scene.get("duration", 4)
        total_duration += dur
        print(f"  📍 Scene {sn} ({dur:.1f}s): {scene.get('text','')[:45]}...")
        clip = create_scene_clip(scene, topic, bg_seed=42)
        clip = clip.set_duration(dur)
        scene_clips.append(clip)

    # ── Outro clip ─────────────────────────────────────────────────────────
    print(f"\n🎬 Building outro ({OUTRO_DURATION}s)...")
    outro_clip = create_outro_clip(channel_name=channel_name)
    total_duration += OUTRO_DURATION
    print(f"⏱️  Total: {total_duration:.1f}s")

    # ── Hook clip ──────────────────────────────────────────────────────────
    hook_text = (
        script.get("thumbnail_text")
        or idea.get("hook")
        or scenes[0].get("text", topic)
    )
    print(f"\n🎬 Hook ({HOOK_DURATION}s): \"{hook_text[:60]}\"")
    hook_clip = create_hook_clip(hook_text)

    # ── Concatenate: hook → scenes → outro ────────────────────────────────
    print("🔗 Combining hook + scenes + outro...")
    all_clips    = [hook_clip] + scene_clips + [outro_clip]
    transitioned = []
    for i, clip in enumerate(all_clips):
        c = clip
        if i > 0:               c = c.crossfadein(SCENE_CROSSFADE)
        if i < len(all_clips)-1: c = c.crossfadeout(SCENE_CROSSFADE)
        transitioned.append(c)

    final = concatenate_videoclips(transitioned, method="compose",
                                   padding=-SCENE_CROSSFADE)
    final = final.fadein(0.18).fadeout(0.18)

    # ── Audio ──────────────────────────────────────────────────────────────
    print("🎵 Building audio...")
    music_path = select_random_music()
    audio_obj  = None

    if (tts_enabled or outro_tts) and tts_audio_path:
        ducked = build_ducked_music(music_path, final.duration, tts_segments)
        tts_ac = AudioFileClip(tts_audio_path)
        if tts_ac.duration < final.duration:
            pad = os.path.join(tts_tmpdir,"tail_sil.mp3")
            make_silence_mp3(pad, final.duration - tts_ac.duration)
            tts_ac = concatenate_audioclips([tts_ac, AudioFileClip(pad)])
        tts_ac = tts_ac.subclip(0, final.duration)

        if ducked:
            mixed     = CompositeAudioClip([ducked, tts_ac])
            final     = final.set_audio(mixed)
            audio_obj = mixed
            print("✅ Ducked music + TTS mixed")
        else:
            final, audio_obj = add_background_music(final, music_path)
            if final.audio:
                final = final.set_audio(CompositeAudioClip([final.audio, tts_ac]))
    else:
        if music_path:
            final, audio_obj = add_background_music(final, music_path)

    # ── Export ─────────────────────────────────────────────────────────────
    print(f"\n💾 Exporting → {output_path}")
    final.write_videofile(
        output_path, fps=FPS,
        codec="libx264", audio_codec="aac",
        preset="medium", threads=2,
        logger=None, bitrate="5000k",
    )

    # ── Cleanup ────────────────────────────────────────────────────────────
    print("🧹 Cleaning up...")
    for obj in ([audio_obj, final.audio if hasattr(final,"audio") else None, final]
                + all_clips):
        try:
            if obj is not None: obj.close()
        except Exception:
            pass
    if tts_tmpdir:
        shutil.rmtree(tts_tmpdir, ignore_errors=True)

    if os.path.exists(output_path):
        mb = os.path.getsize(output_path)/(1024*1024)
        print(f"✅ Video rendered! ({mb:.2f} MB)")
        return output_path
    print("❌ Video file was not created")
    return None

# =============================================================================
# FILE MANAGEMENT
# =============================================================================
def get_ready_scripts(scripts_dir="scripts_output"):
    if not os.path.exists(scripts_dir):
        return []
    ready = []
    for filename in os.listdir(scripts_dir):
        if filename.endswith(".json"):
            fp = os.path.join(scripts_dir, filename)
            try:
                with open(fp,"r",encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status")=="ready_to_render":
                    ready.append((fp, data))
            except Exception as e:
                print(f"⚠️ Could not read {filename}: {e}")
    return ready


def update_script_status(filepath, new_status, video_path=None):
    with open(filepath,"r",encoding="utf-8") as f:
        data = json.load(f)
    data["status"]      = new_status
    data["rendered_at"] = datetime.now().isoformat()
    if video_path:
        data["video_path"] = video_path
    with open(filepath,"w",encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    args = parse_args()
    no_upload, tts_enabled, voice, outro_tts = resolve_flags(args)

    print("="*60)
    print("🎥 ASTRO SHORTS ENGINE - Video Renderer")
    print(f"   Hook frame    : {HOOK_DURATION}s title card  ✓")
    print(f"   Outro frame   : {OUTRO_DURATION}s end card   ✓")
    print(f"   Scene TTS     : {'ON ('+voice+')' if tts_enabled else 'OFF'}")
    print(f"   Outro TTS     : {'ON' if outro_tts else 'OFF'}")
    print(f"   Audio ducking : {'ON' if (tts_enabled or outro_tts) else 'n/a'}")
    print(f"   Upload        : {'SKIP — test mode' if no_upload else 'ENABLED'}")
    print("="*60)
    print()

    if not MOVIEPY_AVAILABLE:
        print("❌ MoviePy required"); raise SystemExit(1)
    if not PIL_AVAILABLE:
        print("❌ Pillow required"); raise SystemExit(1)
    if (tts_enabled or outro_tts) and not EDGE_TTS_AVAILABLE:
        print("⚠️ edge-tts not installed (pip install edge-tts) — disabling TTS")
        tts_enabled = False
        outro_tts   = False

    print(f"🎵 Found {len(get_available_music())} music tracks")
    os.makedirs("videos_output", exist_ok=True)

    ready = get_ready_scripts()
    print(f"📚 {len(ready)} scripts ready to render")
    if not ready:
        print("✨ No scripts waiting."); return

    filepath, script_data = ready[0]
    topic = script_data.get("idea",{}).get("topic","untitled")
    print(f"\n🎬 Selected: {topic}")
    print("-"*60)

    safe     = "".join(c if c.isalnum() or c==" " else "" for c in topic)
    safe     = safe.lower().replace(" ","_")[:30]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"videos_output/{safe}_{ts}.mp4"

    try:
        result = render_video(script_data, out_path,
                              tts_enabled=tts_enabled, voice=voice,
                              outro_tts=outro_tts)
        if result:
            update_script_status(filepath, "rendered", out_path)
            print()
            print("="*60)
            print("🎉 VIDEO RENDERING COMPLETE!")
            print(f"📹 {out_path}")
            if no_upload:
                print("⏭️  Upload skipped (--no-upload / test mode)")
            else:
                print("🚀 Next: python scripts/youtube_uploader.py")
            print("="*60)
        else:
            print("❌ Rendering failed"); raise SystemExit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback; traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
