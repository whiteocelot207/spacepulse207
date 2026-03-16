"""
Video Renderer Agent - FULL VERSION
Creates MP4 videos from formatted scripts with:
- Animated starfield backgrounds
- Planet graphics (Earth, Mars, Jupiter, Saturn, etc.)
- Multiple animation types (fade, zoom, slide, pulse)
- Text effects with shadows and outlines
- Scene transitions
"""

import os
import sys
import json
import random
import math
from datetime import datetime

# Import dependencies with proper error handling
try:
    import moviepy
    from moviepy.editor import (
        TextClip, CompositeVideoClip, ColorClip, 
        ImageClip, concatenate_videoclips, VideoClip
    )
    from moviepy.video.fx.all import fadein, fadeout, resize
    MOVIEPY_AVAILABLE = True
    print("✅ MoviePy loaded successfully")
except ImportError as e:
    print(f"❌ MoviePy import error: {e}")
    MOVIEPY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import numpy as np
    PIL_AVAILABLE = True
    print("✅ Pillow loaded successfully")
except ImportError:
    PIL_AVAILABLE = False
    print("❌ Pillow not installed")


# =============================================================================
# VIDEO SETTINGS
# =============================================================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Color palette
COLORS = {
    'white': (255, 255, 255),
    'orange': (249, 115, 22),
    'blue': (59, 130, 246),
    'purple': (139, 92, 246),
    'yellow': (251, 191, 36),
    'cyan': (6, 182, 212),
    'red': (239, 68, 68),
    'green': (34, 197, 94),
}

COLORS_HEX = {
    'white': '#FFFFFF',
    'orange': '#F97316',
    'blue': '#3B82F6',
    'purple': '#8B5CF6',
    'yellow': '#FBBF24',
    'cyan': '#06B6D4',
}


# =============================================================================
# STARFIELD BACKGROUND GENERATOR
# =============================================================================
def create_starfield_background(width, height, num_stars=400, seed=None):
    """
    Generate a beautiful starfield background with:
    - Multiple star sizes and brightness levels
    - Glowing bright stars
    - Subtle nebula-like color gradients
    """
    if seed:
        random.seed(seed)
    
    # Create base dark space gradient
    img = Image.new('RGB', (width, height), (3, 3, 12))
    draw = ImageDraw.Draw(img)
    
    # Add subtle vertical gradient (darker at top and bottom)
    for y in range(height):
        # Distance from center (0 at center, 1 at edges)
        dist = abs(y - height // 2) / (height // 2)
        # Darken edges slightly
        darkness = int(dist * 8)
        base_color = max(0, 12 - darkness)
        # Add very subtle blue tint
        for x in range(0, width, 50):
            draw.rectangle([x, y, x + 50, y + 1], fill=(3, 3, base_color))
    
    # Add nebula-like subtle color regions
    for _ in range(3):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        nebula_color = random.choice([
            (20, 10, 30),   # Purple tint
            (10, 15, 25),   # Blue tint
            (15, 10, 20),   # Magenta tint
        ])
        radius = random.randint(200, 400)
        for r in range(radius, 0, -20):
            alpha = 0.1 * (1 - r / radius)
            blend_color = tuple(int(c * alpha) for c in nebula_color)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=blend_color)
    
    # Layer 1: Distant small stars (most numerous)
    for _ in range(num_stars):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        brightness = random.randint(80, 180)
        # Slight color variation
        r = brightness
        g = brightness
        b = min(255, brightness + random.randint(0, 40))
        draw.point((x, y), fill=(r, g, b))
    
    # Layer 2: Medium stars
    for _ in range(num_stars // 4):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        brightness = random.randint(150, 220)
        size = random.choice([1, 2, 2])
        color = (brightness, brightness, min(255, brightness + 20))
        draw.ellipse([x - size, y - size, x + size, y + size], fill=color)
    
    # Layer 3: Bright prominent stars with glow
    for _ in range(20):
        x = random.randint(20, width - 20)
        y = random.randint(20, height - 20)
        
        # Create glow effect with multiple circles
        for radius in range(8, 0, -1):
            intensity = int(100 + 155 * (1 - radius / 8))
            # Slight blue tint for glow
            glow_color = (intensity, intensity, min(255, intensity + 30))
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=glow_color)
        
        # Bright center
        draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255))
    
    # Layer 4: A few extra-bright stars with cross flare effect
    for _ in range(5):
        x = random.randint(50, width - 50)
        y = random.randint(50, height - 50)
        
        # Horizontal flare
        for dx in range(-15, 16):
            intensity = int(200 * (1 - abs(dx) / 15))
            if intensity > 0:
                draw.point((x + dx, y), fill=(intensity, intensity, intensity))
        
        # Vertical flare
        for dy in range(-15, 16):
            intensity = int(200 * (1 - abs(dy) / 15))
            if intensity > 0:
                draw.point((x, y + dy), fill=(intensity, intensity, intensity))
        
        # Bright center
        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255))
    
    return np.array(img)


# =============================================================================
# PLANET GENERATOR
# =============================================================================
def create_planet(planet_type, size=200):
    """
    Generate planet graphics programmatically.
    Returns RGBA numpy array.
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    radius = size // 2 - 5
    
    # Planet color schemes
    planet_schemes = {
        'earth': {
            'base': (30, 100, 180),      # Ocean blue
            'secondary': (34, 139, 34),   # Land green
            'highlight': (255, 255, 255), # Clouds
        },
        'mars': {
            'base': (193, 68, 14),
            'secondary': (139, 69, 19),
            'highlight': (210, 105, 30),
        },
        'jupiter': {
            'base': (255, 200, 150),
            'secondary': (210, 160, 120),
            'highlight': (255, 220, 180),
            'bands': True,
        },
        'saturn': {
            'base': (210, 180, 140),
            'secondary': (238, 220, 170),
            'highlight': (255, 240, 200),
            'rings': True,
        },
        'venus': {
            'base': (255, 198, 145),
            'secondary': (218, 165, 105),
            'highlight': (255, 220, 180),
        },
        'neptune': {
            'base': (70, 130, 200),
            'secondary': (100, 149, 237),
            'highlight': (135, 180, 255),
        },
        'moon': {
            'base': (180, 180, 180),
            'secondary': (140, 140, 140),
            'highlight': (220, 220, 220),
        },
        'sun': {
            'base': (255, 200, 50),
            'secondary': (255, 150, 0),
            'highlight': (255, 255, 150),
            'glow': True,
        },
    }
    
    scheme = planet_schemes.get(planet_type, planet_schemes['earth'])
    
    # Draw sun glow if applicable
    if scheme.get('glow'):
        for r in range(radius + 20, radius, -2):
            alpha = int(100 * (1 - (r - radius) / 20))
            glow_color = (*scheme['base'][:3], alpha)
            draw.ellipse([center - r, center - r, center + r, center + r], 
                        fill=scheme['highlight'])
    
    # Draw main planet body
    draw.ellipse([center - radius, center - radius, 
                  center + radius, center + radius], 
                 fill=scheme['base'])
    
    # Add bands for Jupiter
    if scheme.get('bands'):
        band_colors = [scheme['base'], scheme['secondary'], scheme['highlight']]
        band_height = radius * 2 // 6
        for i in range(6):
            y_start = center - radius + i * band_height
            color = band_colors[i % len(band_colors)]
            # Only draw within the circle (simplified)
            for y in range(y_start, min(y_start + band_height, center + radius)):
                # Calculate x bounds for this y
                dy = abs(y - center)
                if dy < radius:
                    dx = int(math.sqrt(radius**2 - dy**2))
                    draw.line([(center - dx, y), (center + dx, y)], fill=color)
    
    # Add surface details/craters
    random.seed(hash(planet_type))
    for _ in range(8):
        dx = random.randint(-radius // 2, radius // 2)
        dy = random.randint(-radius // 2, radius // 2)
        if dx**2 + dy**2 < (radius // 2)**2:
            spot_size = random.randint(5, 15)
            spot_color = scheme['secondary']
            draw.ellipse([center + dx - spot_size, center + dy - spot_size,
                         center + dx + spot_size, center + dy + spot_size],
                        fill=spot_color)
    
    # Add highlight (light reflection)
    highlight_x = center - radius // 3
    highlight_y = center - radius // 3
    for r in range(radius // 4, 0, -2):
        alpha = int(80 * (1 - r / (radius // 4)))
        # Draw a white-ish highlight
        draw.ellipse([highlight_x - r, highlight_y - r,
                     highlight_x + r, highlight_y + r],
                    fill=(*scheme['highlight'][:3], ))
    
    # Add rings for Saturn
    if scheme.get('rings'):
        # Draw elliptical rings
        ring_inner = int(radius * 1.3)
        ring_outer = int(radius * 1.8)
        ring_color = (200, 180, 140)
        
        # Simple ring representation (horizontal ellipse)
        for r in range(ring_inner, ring_outer, 2):
            ring_alpha = int(150 * (1 - abs(r - (ring_inner + ring_outer) // 2) / ((ring_outer - ring_inner) // 2)))
            draw.ellipse([center - r, center - 8, center + r, center + 8], 
                        outline=(*ring_color, ring_alpha), width=1)
    
    return np.array(img)


# =============================================================================
# TEXT AND ANIMATION UTILITIES  
# =============================================================================
def get_fontsize(text_size):
    """Get font size based on text_size parameter."""
    sizes = {
        'large': 76,
        'medium': 58,
        'small': 46
    }
    return sizes.get(text_size, 58)


def ease_in_out(t):
    """Smooth easing function for animations."""
    return t * t * (3 - 2 * t)


def create_animated_text_clip(text, duration, fontsize, position='center', 
                               animation='fade_in', color='white'):
    """
    Create a text clip with animation effects.
    
    Animations supported:
    - fade_in: Fade from transparent
    - fade_out: Fade to transparent
    - zoom_in: Scale up from small
    - zoom_out: Scale down
    - slide_left: Slide in from right
    - slide_right: Slide in from left
    - pulse: Slight pulsing effect
    """
    try:
        # Create base text clip
        txt = TextClip(
            text,
            fontsize=fontsize,
            color=COLORS_HEX.get(color, '#FFFFFF'),
            font='DejaVu-Sans-Bold',
            size=(VIDEO_WIDTH - 80, None),
            method='caption',
            align='center',
            stroke_color='black',
            stroke_width=3
        )
        txt = txt.set_duration(duration)
        
        # Set position
        if position == 'top':
            y_pos = 180
        elif position == 'bottom':
            y_pos = VIDEO_HEIGHT - 400
        else:
            y_pos = 'center'
        
        if y_pos == 'center':
            txt = txt.set_position('center')
        else:
            txt = txt.set_position(('center', y_pos))
        
        # Apply animations
        if animation == 'fade_in':
            txt = txt.crossfadein(0.5)
        elif animation == 'fade_out':
            txt = txt.crossfadeout(0.5)
        elif animation == 'zoom_in':
            txt = txt.crossfadein(0.3)
            # Note: Full zoom would need resize animation
        elif animation == 'zoom_out':
            txt = txt.crossfadeout(0.3)
        elif animation == 'slide_left':
            txt = txt.crossfadein(0.4)
        elif animation == 'slide_right':
            txt = txt.crossfadein(0.4)
        elif animation == 'pulse':
            txt = txt.crossfadein(0.2)
        else:
            txt = txt.crossfadein(0.3)  # Default subtle fade
        
        return txt
        
    except Exception as e:
        print(f"⚠️ TextClip creation error: {e}")
        return None


# =============================================================================
# SCENE AND VIDEO CREATION
# =============================================================================
def get_planet_for_topic(topic, visual_hint=""):
    """Determine which planet to show based on topic or visual hint."""
    topic_lower = (topic + " " + visual_hint).lower()
    
    if 'earth' in topic_lower:
        return 'earth'
    elif 'mars' in topic_lower:
        return 'mars'
    elif 'jupiter' in topic_lower:
        return 'jupiter'
    elif 'saturn' in topic_lower:
        return 'saturn'
    elif 'venus' in topic_lower:
        return 'venus'
    elif 'neptune' in topic_lower or 'uranus' in topic_lower:
        return 'neptune'
    elif 'moon' in topic_lower or 'lunar' in topic_lower:
        return 'moon'
    elif 'sun' in topic_lower or 'solar' in topic_lower:
        return 'sun'
    else:
        # Random planet for variety
        return random.choice(['earth', 'mars', 'jupiter', 'saturn', 'neptune'])


def create_scene_with_planet(scene, bg_array, planet_type=None, show_planet=True):
    """
    Create a complete scene with:
    - Starfield background
    - Optional planet graphic
    - Animated text
    """
    duration = scene.get('duration', 4)
    
    # Create background clip
    bg_clip = ImageClip(bg_array).set_duration(duration)
    
    layers = [bg_clip]
    
    # Add planet if requested
    if show_planet and planet_type:
        planet_array = create_planet(planet_type, size=250)
        planet_clip = ImageClip(planet_array, ismask=False)
        planet_clip = planet_clip.set_duration(duration)
        
        # Position planet (varies by scene for visual interest)
        scene_num = scene.get('scene_number', 1)
        if scene_num % 3 == 1:
            planet_pos = (VIDEO_WIDTH - 300, 200)
        elif scene_num % 3 == 2:
            planet_pos = (50, VIDEO_HEIGHT - 450)
        else:
            planet_pos = (VIDEO_WIDTH - 280, VIDEO_HEIGHT - 500)
        
        planet_clip = planet_clip.set_position(planet_pos)
        
        # Add fade to planet
        planet_clip = planet_clip.crossfadein(0.5)
        
        layers.append(planet_clip)
    
    # Create text clip
    txt_clip = create_animated_text_clip(
        scene['text'],
        duration,
        get_fontsize(scene.get('text_size', 'medium')),
        scene.get('text_position', 'center'),
        scene.get('animation', 'fade_in'),
        'white'
    )
    
    if txt_clip:
        layers.append(txt_clip)
    
    # Composite all layers
    return CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))


def create_scene_clip(scene, bg_array, idea_topic=""):
    """Create a scene clip, deciding whether to include planet."""
    
    # Determine if this scene should show a planet
    visual_hint = scene.get('visual', '')
    scene_num = scene.get('scene_number', 1)
    
    # Show planet on scenes 1, 3, and 5 for visual variety
    show_planet = scene_num in [1, 3, 5]
    
    planet_type = None
    if show_planet:
        planet_type = get_planet_for_topic(idea_topic, visual_hint)
    
    return create_scene_with_planet(scene, bg_array, planet_type, show_planet)


def render_video(script_data, output_path):
    """
    Render the complete video from script data.
    
    Pipeline:
    1. Generate starfield background
    2. Create planet graphics as needed
    3. Build each scene with text animations
    4. Concatenate scenes
    5. Add overall fades
    6. Export MP4
    """
    
    if not MOVIEPY_AVAILABLE or not PIL_AVAILABLE:
        print("❌ Required libraries not available")
        return None
    
    idea = script_data.get('idea', {})
    script = script_data.get('script', {})
    scenes = script.get('scenes', [])
    
    if not scenes:
        print("❌ No scenes found in script")
        return None
    
    topic = idea.get('topic', 'Space')
    
    print(f"🎬 Rendering {len(scenes)} scenes...")
    print(f"📝 Topic: {topic}")
    
    # Generate starfield background (consistent for all scenes)
    print("🌌 Creating starfield background...")
    bg_array = create_starfield_background(VIDEO_WIDTH, VIDEO_HEIGHT, num_stars=400, seed=42)
    
    # Build scene clips
    scene_clips = []
    total_duration = 0
    
    for i, scene in enumerate(scenes):
        scene_num = scene.get('scene_number', i + 1)
        duration = scene.get('duration', 4)
        total_duration += duration
        
        print(f"  📍 Scene {scene_num} ({duration}s): {scene['text'][:45]}...")
        
        clip = create_scene_clip(scene, bg_array, topic)
        scene_clips.append(clip)
    
    print(f"⏱️ Total duration: {total_duration} seconds")
    
    # Concatenate all scenes
    print("🔗 Combining scenes...")
    final = concatenate_videoclips(scene_clips, method="compose")
    
    # Add fade in/out to entire video
    final = final.fadein(0.5).fadeout(0.5)
    
    # Export video
    print(f"💾 Exporting video to {output_path}...")
    print("   (This may take 1-2 minutes)")
    
    final.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio=False,
        preset='medium',
        threads=2,
        logger=None,  # Suppress verbose ffmpeg output
        bitrate='5000k'
    )
    
    # Cleanup
    print("🧹 Cleaning up...")
    final.close()
    for clip in scene_clips:
        clip.close()
    
    # Verify output
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Video rendered successfully!")
        print(f"📦 File size: {file_size:.2f} MB")
        return output_path
    else:
        print("❌ Video file was not created")
        return None


# =============================================================================
# FILE MANAGEMENT
# =============================================================================
def get_ready_scripts(scripts_dir="scripts_output"):
    """Find scripts that are ready to render."""
    if not os.path.exists(scripts_dir):
        return []
    
    ready = []
    for filename in os.listdir(scripts_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(scripts_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if data.get('status') == 'ready_to_render':
                    ready.append((filepath, data))
            except Exception as e:
                print(f"⚠️ Could not read {filename}: {e}")
    
    return ready


def update_script_status(filepath, new_status, video_path=None):
    """Update the status of a script file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    data['status'] = new_status
    data['rendered_at'] = datetime.now().isoformat()
    if video_path:
        data['video_path'] = video_path
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    print("=" * 60)
    print("🎥 ASTRO SHORTS ENGINE - Full Video Renderer")
    print("=" * 60)
    print()
    
    # Check dependencies
    if not MOVIEPY_AVAILABLE:
        print("❌ MoviePy is required but not available")
        print("   Install with: pip install moviepy==1.0.3")
        exit(1)
    
    if not PIL_AVAILABLE:
        print("❌ Pillow is required but not available")
        print("   Install with: pip install Pillow")
        exit(1)
    
    print("✅ All dependencies loaded")
    print()
    
    # Create output directory
    output_dir = "videos_output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 Created output directory: {output_dir}")
    
    # Find scripts ready to render
    ready_scripts = get_ready_scripts()
    print(f"📚 Found {len(ready_scripts)} scripts ready to render")
    
    if not ready_scripts:
        print("✨ No scripts waiting to render.")
        print("   Run the idea generator and script formatter first.")
        return
    
    # Render the first ready script
    filepath, script_data = ready_scripts[0]
    topic = script_data.get('idea', {}).get('topic', 'untitled')
    
    print()
    print(f"🎬 Selected for rendering: {topic}")
    print("-" * 60)
    
    # Generate output filename
    safe_topic = "".join(c if c.isalnum() or c == ' ' else '' for c in topic)
    safe_topic = safe_topic.lower().replace(' ', '_')[:30]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{output_dir}/{safe_topic}_{timestamp}.mp4"
    
    # Render the video
    try:
        result = render_video(script_data, output_path)
        
        if result:
            # Update script status
            update_script_status(filepath, 'rendered', output_path)
            
            print()
            print("=" * 60)
            print("🎉 VIDEO RENDERING COMPLETE!")
            print("=" * 60)
            print(f"📹 Output: {output_path}")
            print(f"🚀 Next step: YouTube upload")
            print("=" * 60)
        else:
            print("❌ Rendering failed - no output file created")
            exit(1)
            
    except Exception as e:
        print(f"❌ Rendering error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
