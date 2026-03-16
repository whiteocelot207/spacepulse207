"""
YouTube Uploader Agent
Automatically uploads rendered videos to YouTube as Shorts.
"""

import os
import json
import time
from datetime import datetime

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
    print("✅ Google API libraries loaded")
except ImportError as e:
    GOOGLE_API_AVAILABLE = False
    print(f"❌ Google API import error: {e}")


# YouTube API settings
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Video settings
DEFAULT_CATEGORY_ID = "28"  # Science & Technology
DEFAULT_PRIVACY = "public"  # or "private", "unlisted"


def get_authenticated_service():
    """Create an authenticated YouTube API service."""
    
    # Load token from environment variable
    token_json = os.environ.get('YOUTUBE_TOKEN')
    if not token_json:
        print("❌ YOUTUBE_TOKEN environment variable not found")
        return None
    
    try:
        token_data = json.loads(token_json)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse YOUTUBE_TOKEN: {e}")
        return None
    
    # Load client secrets for token refresh
    client_secret_json = os.environ.get('YOUTUBE_CLIENT_SECRET')
    if not client_secret_json:
        print("❌ YOUTUBE_CLIENT_SECRET environment variable not found")
        return None
    
    try:
        client_data = json.loads(client_secret_json)
        # Handle both formats (installed app vs web app)
        if 'installed' in client_data:
            client_info = client_data['installed']
        elif 'web' in client_data:
            client_info = client_data['web']
        else:
            client_info = client_data
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse YOUTUBE_CLIENT_SECRET: {e}")
        return None
    
    # Create credentials object
    credentials = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=token_data.get('client_id') or client_info.get('client_id'),
        client_secret=token_data.get('client_secret') or client_info.get('client_secret'),
        scopes=token_data.get('scopes', SCOPES)
    )
    
    # Refresh token if expired
    if credentials.expired and credentials.refresh_token:
        print("🔄 Refreshing access token...")
        try:
            credentials.refresh(Request())
            print("✅ Token refreshed successfully")
        except Exception as e:
            print(f"❌ Failed to refresh token: {e}")
            return None
    
    # Build the YouTube service
    try:
        service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)
        print("✅ YouTube API service created")
        return service
    except Exception as e:
        print(f"❌ Failed to build YouTube service: {e}")
        return None


def upload_video(service, video_path, title, description, tags, category_id=DEFAULT_CATEGORY_ID, privacy=DEFAULT_PRIVACY):
    """
    Upload a video to YouTube.
    
    For Shorts:
    - Video should be vertical (9:16)
    - Under 60 seconds
    - Include #Shorts in title or description
    """
    
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return None
    
    file_size = os.path.getsize(video_path) / (1024 * 1024)
    print(f"📹 Uploading: {video_path} ({file_size:.1f} MB)")
    
    # Ensure #Shorts is in the title or description for YouTube to recognize it
    if "#Shorts" not in title and "#Shorts" not in description:
        title = f"{title} #Shorts"
    
    # Video metadata
    body = {
        "snippet": {
            "title": title[:100],  # YouTube title limit
            "description": description[:5000],  # YouTube description limit
            "tags": tags[:500] if tags else [],  # Tag limit
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }
    
    # Create media upload object
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024  # 1MB chunks
    )
    
    # Execute upload
    try:
        print("⬆️ Starting upload...")
        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"   📊 Upload progress: {progress}%")
        
        video_id = response.get('id')
        print(f"✅ Upload complete!")
        print(f"🎬 Video ID: {video_id}")
        print(f"🔗 URL: https://youtube.com/shorts/{video_id}")
        
        return {
            'video_id': video_id,
            'url': f"https://youtube.com/shorts/{video_id}",
            'title': title,
            'uploaded_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


def get_rendered_videos(videos_dir="videos_output"):
    """Find videos that are ready to upload."""
    if not os.path.exists(videos_dir):
        return []
    
    videos = []
    for filename in os.listdir(videos_dir):
        if filename.endswith('.mp4'):
            filepath = os.path.join(videos_dir, filename)
            videos.append(filepath)
    
    return videos


def get_script_for_video(video_path, scripts_dir="scripts_output"):
    """Find the script data that matches a video."""
    if not os.path.exists(scripts_dir):
        return None
    
    # Look through scripts to find one marked as rendered with this video
    for filename in os.listdir(scripts_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(scripts_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if data.get('video_path') == video_path:
                    return (filepath, data)
                if data.get('status') == 'rendered':
                    # Check if video filename matches
                    if os.path.basename(video_path) in str(data.get('video_path', '')):
                        return (filepath, data)
            except Exception:
                continue
    
    # Fallback: return any rendered script
    for filename in os.listdir(scripts_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(scripts_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                if data.get('status') == 'rendered':
                    return (filepath, data)
            except Exception:
                continue
    
    return None


def update_script_status(filepath, new_status, upload_info=None):
    """Update script status after upload."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    data['status'] = new_status
    data['uploaded_at'] = datetime.now().isoformat()
    if upload_info:
        data['youtube'] = upload_info
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    print("=" * 60)
    print("📺 ASTRO SHORTS ENGINE - YouTube Uploader")
    print("=" * 60)
    print()
    
    if not GOOGLE_API_AVAILABLE:
        print("❌ Google API libraries not installed")
        print("   Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        exit(1)
    
    # Get authenticated YouTube service
    service = get_authenticated_service()
    if not service:
        print("❌ Failed to authenticate with YouTube")
        exit(1)
    
    # Find rendered videos
    videos = get_rendered_videos()
    print(f"📹 Found {len(videos)} rendered videos")
    
    if not videos:
        print("✨ No videos to upload")
        return
    
    # Upload the first video
    video_path = videos[0]
    print()
    print(f"🎬 Selected for upload: {os.path.basename(video_path)}")
    print("-" * 60)
    
    # Get script data for metadata
    script_result = get_script_for_video(video_path)
    
    if script_result:
        script_path, script_data = script_result
        idea = script_data.get('idea', {})
        
        title = idea.get('title', 'Astrophysics Short')
        hashtags = idea.get('hashtags', ['#Space', '#Astrophysics', '#Science'])
        topic = idea.get('topic', 'Space Facts')
        hook = idea.get('hook', '')
        payoff = idea.get('payoff', '')
        
        # Build description
        description = f"""{hook}

{payoff}

{' '.join(hashtags)}

#Shorts #Space #Astrophysics #Science #SpaceFacts
"""
        
        # Convert hashtags to tags (without #)
        tags = [tag.replace('#', '') for tag in hashtags]
        tags.extend(['Shorts', 'Space', 'Astrophysics', 'Science', 'SpaceFacts', 'Astronomy'])
        
    else:
        print("⚠️ No script data found, using defaults")
        title = "Astrophysics Facts #Shorts"
        description = "Amazing facts about space! #Shorts #Space #Astrophysics"
        tags = ['Shorts', 'Space', 'Astrophysics', 'Science']
        script_path = None
    
    print(f"📝 Title: {title}")
    print(f"🏷️ Tags: {', '.join(tags[:5])}...")
    print()
    
    # Upload!
    result = upload_video(
        service,
        video_path,
        title,
        description,
        tags,
        privacy="public"  # Change to "unlisted" or "private" for testing
    )
    
    if result:
        # Update script status
        if script_path:
            update_script_status(script_path, 'uploaded', result)
        
        print()
        print("=" * 60)
        print("🎉 VIDEO UPLOADED SUCCESSFULLY!")
        print("=" * 60)
        print(f"🔗 Watch it: {result['url']}")
        print("=" * 60)
    else:
        print("❌ Upload failed")
        exit(1)


if __name__ == "__main__":
    main()
