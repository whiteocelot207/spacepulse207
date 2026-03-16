"""
Idea Generator Agent
Generates astrophysics YouTube Shorts ideas using Gemini API.
"""

import os
import json
import requests
from datetime import datetime

def generate_idea():
    """Generate a single Short idea from Gemini."""
    
    # Get API key from environment (GitHub Secrets injects this)
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found in environment")
        return None
    
    # The prompt that tells Gemini what to generate
    prompt = """You are a viral astrophysics YouTube Shorts content strategist.

Generate ONE idea for a 20-second silent infographic Short about space or astrophysics.

Requirements:
- Hook must be attention-grabbing (question or surprising statement)
- Facts must be scientifically accurate
- Include specific numbers when possible
- Payoff should be surprising or thought-provoking

Return ONLY this JSON format, no other text:
{
    "topic": "brief topic name",
    "topic_family": "scale_comparison OR travel_time OR planetary_facts OR cosmic_mystery",
    "hook": "the opening question or statement",
    "facts": [
        "fact 1 with specific numbers",
        "fact 2 with specific numbers",
        "fact 3 with specific numbers"
    ],
    "payoff": "surprising conclusion",
    "title": "YouTube title with emoji",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}"""

    # Call Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("🚀 Calling Gemini API...")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract the text from Gemini's response
        text = data['candidates'][0]['content']['parts'][0]['text']
        
        # Clean up the response (remove markdown code blocks if present)
        clean_text = text.replace('```json', '').replace('```', '').strip()
        
        # Parse the JSON
        idea = json.loads(clean_text)
        
        # Add metadata
        idea['generated_at'] = datetime.now().isoformat()
        idea['status'] = 'pending'
        
        print("✅ Idea generated successfully!")
        print(json.dumps(idea, indent=2))
        
        return idea
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse Gemini response as JSON: {e}")
        print(f"Raw response: {text}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def save_idea(idea, filename="ideas.json"):
    """Save idea to a JSON file."""
    
    # Load existing ideas or create empty list
    ideas = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            ideas = json.load(f)
    
    # Add new idea
    ideas.append(idea)
    
    # Save back to file
    with open(filename, 'w') as f:
        json.dump(ideas, f, indent=2)
    
    print(f"💾 Saved to {filename} (total ideas: {len(ideas)})")
    return filename


if __name__ == "__main__":
    print("=" * 50)
    print("🌌 ASTRO SHORTS ENGINE - Idea Generator")
    print("=" * 50)
    print()
    
    idea = generate_idea()
    
    if idea:
        save_idea(idea)
        print()
        print("=" * 50)
        print("🎬 Ready for next step: Script formatting")
        print("=" * 50)
    else:
        print()
        print("❌ Failed to generate idea. Check errors above.")
        exit(1)
