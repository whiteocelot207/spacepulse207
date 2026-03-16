"""
Script Formatter Agent
Transforms raw ideas into scene-by-scene video scripts ready for rendering.
"""

import os
import json
import requests
from datetime import datetime

def load_ideas(filename="ideas.json"):
    """Load ideas from the JSON file."""
    if not os.path.exists(filename):
        print(f"❌ {filename} not found")
        return []
    
    with open(filename, 'r') as f:
        ideas = json.load(f)
    
    return ideas


def get_pending_ideas(ideas):
    """Get ideas that haven't been formatted yet."""
    return [idea for idea in ideas if idea.get('status') == 'pending']


def format_script(idea):
    """Use Gemini to create a detailed scene-by-scene script."""
    
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found")
        return None
    
    prompt = f"""You are a YouTube Shorts video script director.

Take this video idea and create a detailed scene-by-scene script for a 20-second silent infographic Short.

IDEA:
- Topic: {idea.get('topic')}
- Hook: {idea.get('hook')}
- Facts: {json.dumps(idea.get('facts', []))}
- Payoff: {idea.get('payoff')}

Create exactly 5 scenes that fit in 20 seconds total.

For each scene, specify:
1. Duration (in seconds)
2. Exact text to display (short, punchy, fits on screen)
3. Visual description (what the viewer sees)
4. Animation type (fade_in, zoom_in, zoom_out, slide_left, slide_right, pulse, none)
5. Text position (top, center, bottom)
6. Text size (large, medium, small)

Return ONLY this JSON format, no other text:
{{
    "total_duration": 20,
    "scenes": [
        {{
            "scene_number": 1,
            "start_time": 0,
            "duration": 3,
            "text": "Hook text here",
            "text_position": "center",
            "text_size": "large",
            "visual": "Description of background/visual",
            "animation": "fade_in"
        }},
        {{
            "scene_number": 2,
            "start_time": 3,
            "duration": 4,
            "text": "First fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "zoom_in"
        }},
        {{
            "scene_number": 3,
            "start_time": 7,
            "duration": 4,
            "text": "Second fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "slide_left"
        }},
        {{
            "scene_number": 4,
            "start_time": 11,
            "duration": 4,
            "text": "Third fact",
            "text_position": "center",
            "text_size": "medium",
            "visual": "Visual description",
            "animation": "slide_right"
        }},
        {{
            "scene_number": 5,
            "start_time": 15,
            "duration": 5,
            "text": "Payoff/conclusion",
            "text_position": "center",
            "text_size": "large",
            "animation": "pulse",
            "visual": "Final impactful visual"
        }}
    ],
    "thumbnail_text": "Short punchy text for thumbnail",
    "background_style": "space_dark OR space_nebula OR space_stars OR earth_orbit"
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        print(f"🎬 Formatting script for: {idea.get('topic')}...")
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Clean and parse JSON
        clean_text = text.replace('```json', '').replace('```', '').strip()
        script = json.loads(clean_text)
        
        print("✅ Script formatted successfully!")
        return script
        
    except Exception as e:
        print(f"❌ Error formatting script: {e}")
        return None


def save_script(idea, script, scripts_dir="scripts_output"):
    """Save the formatted script to a file."""
    
    # Create output directory if it doesn't exist
    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)
    
    # Create filename from topic
    safe_topic = idea.get('topic', 'untitled').lower().replace(' ', '_')[:30]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{scripts_dir}/{safe_topic}_{timestamp}.json"
    
    # Combine idea and script data
    full_script = {
        "idea": idea,
        "script": script,
        "formatted_at": datetime.now().isoformat(),
        "status": "ready_to_render"
    }
    
    with open(filename, 'w') as f:
        json.dump(full_script, f, indent=2)
    
    print(f"💾 Saved script to: {filename}")
    return filename


def update_idea_status(ideas, idea_index, new_status, ideas_file="ideas.json"):
    """Update the status of an idea in the JSON file."""
    ideas[idea_index]['status'] = new_status
    ideas[idea_index]['formatted_at'] = datetime.now().isoformat()
    
    with open(ideas_file, 'w') as f:
        json.dump(ideas, f, indent=2)


def main():
    print("=" * 50)
    print("🎬 ASTRO SHORTS ENGINE - Script Formatter")
    print("=" * 50)
    print()
    
    # Load all ideas
    ideas = load_ideas()
    if not ideas:
        print("No ideas found. Run the idea generator first.")
        return
    
    print(f"📚 Found {len(ideas)} total ideas")
    
    # Get pending ideas
    pending = get_pending_ideas(ideas)
    print(f"⏳ {len(pending)} ideas pending formatting")
    
    if not pending:
        print("✨ All ideas have been formatted!")
        return
    
    # Format the first pending idea
    idea = pending[0]
    idea_index = ideas.index(idea)
    
    print()
    print(f"📝 Processing: {idea.get('topic')}")
    print("-" * 40)
    
    script = format_script(idea)
    
    if script:
        # Save the script
        script_file = save_script(idea, script)
        
        # Update idea status
        update_idea_status(ideas, idea_index, 'formatted')
        
        print()
        print("=" * 50)
        print(f"✅ Script ready: {script_file}")
        print("🎬 Next step: Video rendering")
        print("=" * 50)
        
        # Print preview
        print()
        print("📋 Script Preview:")
        print("-" * 40)
        for scene in script.get('scenes', []):
            print(f"  Scene {scene['scene_number']} ({scene['duration']}s): {scene['text'][:50]}...")
    else:
        print("❌ Failed to format script")
        exit(1)


if __name__ == "__main__":
    main()
