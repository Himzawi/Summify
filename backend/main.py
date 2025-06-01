from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
import json

load_dotenv()

app = FastAPI()

# Configure CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Changed from localhost only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLRequest(BaseModel):
    url: str

def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats"""
    try:
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path[1:]
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if "v=" in url:
                return parse_qs(parsed.query).get("v", [None])[0]
            # Handle /watch?v= format
            elif "/watch" in parsed.path:
                return parse_qs(parsed.query).get("v", [None])[0]
        return None
    except Exception as e:
        print(f"Error extracting video ID: {e}")
        return None

def get_transcript(video_url: str) -> str:
    """Get transcript from YouTube video with multiple fallback methods"""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        print(f"Fetching transcript for video ID: {video_id}")
        
        # Method 1: Direct transcript fetch (most reliable)
        try:
            print("Trying direct transcript fetch...")
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id, 
                languages=['en', 'en-US', 'en-GB', 'en-CA', 'en-AU']
            )
            
            if transcript_list:
                full_text = " ".join([entry['text'] for entry in transcript_list])
                print(f"✅ Direct method successful - transcript length: {len(full_text)} characters")
                return full_text
                
        except Exception as direct_error:
            print(f"Direct method failed: {direct_error}")
        
        # Method 2: List transcripts and find English
        try:
            print("Trying transcript list method...")
            transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Debug: Print available transcripts
            print("Available transcripts:")
            for transcript in transcript_list_obj:
                print(f"  - Language: {transcript.language}, Code: {transcript.language_code}, Generated: {transcript.is_generated}")
            
            # Try to find English transcript
            english_transcript = None
            
            # First try manually created English
            try:
                english_transcript = transcript_list_obj.find_manually_created_transcript(['en'])
                print("Found manually created English transcript")
            except:
                try:
                    # Then auto-generated English
                    english_transcript = transcript_list_obj.find_generated_transcript(['en'])
                    print("Found auto-generated English transcript")
                except:
                    # Finally any English variant
                    for transcript in transcript_list_obj:
                        if transcript.language_code.startswith('en'):
                            english_transcript = transcript
                            print(f"Found English transcript: {transcript.language_code}")
                            break
            
            if english_transcript:
                print(f"Fetching transcript data...")
                fetched_data = english_transcript.fetch()
                
                print(f"Fetched data type: {type(fetched_data)}")
                print(f"Fetched data length: {len(fetched_data) if hasattr(fetched_data, '__len__') else 'N/A'}")
                
                # Debug: Print first few entries
                if hasattr(fetched_data, '__iter__'):
                    for i, entry in enumerate(fetched_data):
                        if i < 3:  # Print first 3 entries
                            print(f"Entry {i}: {type(entry)} - {entry}")
                        else:
                            break
                
                # Extract text from transcript entries
                full_text = ""
                if isinstance(fetched_data, list):
                    for entry in fetched_data:
                        if isinstance(entry, dict) and 'text' in entry:
                            full_text += entry['text'] + " "
                        elif hasattr(entry, 'text'):
                            full_text += str(entry.text) + " "
                        else:
                            print(f"Unhandled entry type: {type(entry)} - {entry}")
                
                if full_text.strip():
                    print(f"✅ List method successful - transcript length: {len(full_text)} characters")
                    return full_text.strip()
                else:
                    print("❌ No text extracted from transcript entries")
            else:
                print("❌ No English transcript found")
                
        except Exception as list_error:
            print(f"List method failed: {list_error}")
            import traceback
            traceback.print_exc()
        
        # If we get here, no method worked
        raise NoTranscriptFound("No English transcript could be retrieved")

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"No English captions found: {e}")
        return ""
    except Exception as e:
        print(f"Transcript fetch error: {e}")
        import traceback
        traceback.print_exc()
        return ""

def generate_summary(text: str) -> str:
    """Generate summary using OpenRouter API"""
    try:
        if not text.strip():
            return "No transcript content to summarize"
        
        # Check if API key exists
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return "API key not configured. Please set OPENROUTER_API_KEY in your .env file"
            
        print("\nGenerating summary...")
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "YouTube TL;DR"
        }
        
        # Truncate text if too long (keep first 4000 chars to stay within limits)
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        payload = {
            "model": "deepseek/deepseek-chat:free",  # Updated model name
            "messages": [
                {
                    "role": "system", 
                    "content": "You're a helpful YouTube video summarizer. Provide a concise 3-paragraph summary in a casual, friendly tone. Focus on the main points and key takeaways."
                },
                {
                    "role": "user", 
                    "content": f"Please summarize this YouTube video transcript:\n\n{text}"
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 401:
            return "Invalid API key. Please check your OPENROUTER_API_KEY"
        elif response.status_code == 429:
            return "Rate limit exceeded. Please try again later"
        
        response.raise_for_status()
        
        data = response.json()
        if 'choices' not in data or len(data['choices']) == 0:
            return "No summary generated by the AI model"
            
        summary = data['choices'][0]['message']['content']
        print(f"Summary generated successfully")
        return summary
        
    except requests.exceptions.Timeout:
        return "Request timed out. Please try again"
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return f"Network error: Unable to generate summary"
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return f"Summary generation failed: {str(e)}"

@app.post("/summarize")
async def summarize_video(request: URLRequest):
    """Main endpoint to summarize YouTube videos"""
    try:
        print(f"Received URL: {request.url}")
        
        # Validate YouTube URL
        if not any(domain in request.url.lower() for domain in ["youtube.com", "youtu.be"]):
            raise HTTPException(status_code=400, detail="Please provide a valid YouTube URL")
        
        # Get transcript
        transcript = get_transcript(request.url)
        if not transcript:
            raise HTTPException(
                status_code=404,
                detail="No English captions/transcript found for this video. The video might not have captions available."
            )
        
        # Generate summary
        summary = generate_summary(transcript)
        
        if "API key not configured" in summary:
            raise HTTPException(status_code=500, detail=summary)
        
        return {"summary": summary, "transcript_length": len(transcript)}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "YouTube TL;DR API is running"}

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "YouTube TL;DR API", "endpoints": ["/summarize", "/health"]}

if __name__ == "__main__":
    import uvicorn
    print("Starting YouTube TL;DR API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)