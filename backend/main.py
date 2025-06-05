from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
import json
import random
import time
from typing import Optional, List, Dict

load_dotenv()

app = FastAPI()

# Configure CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLRequest(BaseModel):
    url: str

# Proxy list with working proxies
PROXY_LIST = [
    {"ip": "197.44.247.35", "port": "3128", "country": "EG"},
    {"ip": "45.140.143.77", "port": "18080", "country": "NL"},
    {"ip": "159.69.57.208", "port": "80", "country": "DE"},
    {"ip": "195.231.69.20", "port": "80", "country": "IT"},
    {"ip": "57.129.81.20", "port": "18080", "country": "DE"},
    {"ip": "185.234.65.66", "port": "1080", "country": "NL"},
    {"ip": "113.181.140.80", "port": "8080", "country": "VN"},
    {"ip": "123.140.160.12", "port": "5031", "country": "KR"},
    {"ip": "123.140.146.3", "port": "5031", "country": "KR"},
    {"ip": "139.59.34.20", "port": "8080", "country": "IN"},
    {"ip": "123.140.146.2", "port": "5031", "country": "KR"},
    {"ip": "123.140.146.57", "port": "5031", "country": "KR"},
    {"ip": "45.67.221.230", "port": "80", "country": "DE"},
    {"ip": "198.49.68.80", "port": "80", "country": "US"},
]

class ProxyManager:
    def __init__(self, proxy_list: List[Dict]):
        self.proxy_list = proxy_list
        self.working_proxies = proxy_list.copy()
        self.failed_proxies = []
        self.current_proxy_index = 0
        
    def get_proxy_dict(self, proxy_info: Dict) -> Dict:
        """Convert proxy info to requests-compatible format"""
        proxy_url = f"http://{proxy_info['ip']}:{proxy_info['port']}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def get_next_proxy(self) -> Optional[Dict]:
        """Get next working proxy, cycling through the list"""
        if not self.working_proxies:
            # If no working proxies, reset the list and try again
            print("No working proxies found, resetting proxy list...")
            self.working_proxies = self.proxy_list.copy()
            self.failed_proxies = []
            
        if not self.working_proxies:
            return None
            
        # Randomly select a proxy to avoid patterns
        proxy_info = random.choice(self.working_proxies)
        return self.get_proxy_dict(proxy_info)
    
    def mark_proxy_failed(self, proxy_dict: Dict):
        """Mark a proxy as failed and remove from working list"""
        proxy_url = proxy_dict.get('http', '')
        for proxy_info in self.working_proxies:
            if f"{proxy_info['ip']}:{proxy_info['port']}" in proxy_url:
                print(f"Marking proxy as failed: {proxy_info['ip']}:{proxy_info['port']}")
                self.working_proxies.remove(proxy_info)
                self.failed_proxies.append(proxy_info)
                break

# Initialize proxy manager
proxy_manager = ProxyManager(PROXY_LIST)

def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats"""
    try:
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path[1:]
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if "v=" in url:
                return parse_qs(parsed.query).get("v", [None])[0]
            elif "/watch" in parsed.path:
                return parse_qs(parsed.query).get("v", [None])[0]
        return None
    except Exception as e:
        print(f"Error extracting video ID: {e}")
        return None

def make_request_with_proxy(url: str, max_retries: int = 3) -> Optional[requests.Response]:
    """Make HTTP request using proxy rotation"""
    for attempt in range(max_retries):
        proxy_dict = proxy_manager.get_next_proxy()
        
        if not proxy_dict:
            print("No proxies available, trying direct connection...")
            try:
                response = requests.get(url, timeout=10)
                return response
            except Exception as e:
                print(f"Direct connection failed: {e}")
                return None
        
        try:
            print(f"Attempt {attempt + 1}: Using proxy {proxy_dict['http']}")
            response = requests.get(
                url, 
                proxies=proxy_dict, 
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Proxy request successful")
                return response
            else:
                print(f"Proxy returned status {response.status_code}")
                proxy_manager.mark_proxy_failed(proxy_dict)
                
        except Exception as e:
            print(f"Proxy request failed: {e}")
            proxy_manager.mark_proxy_failed(proxy_dict)
            continue
    
    return None

def get_transcript(video_url: str) -> str:
    """Get transcript from YouTube video with simplified approach"""
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
            available_transcripts = []
            try:
                for transcript in transcript_list_obj:
                    print(f"  - Language: {transcript.language}, Code: {transcript.language_code}, Generated: {transcript.is_generated}")
                    available_transcripts.append(transcript)
            except Exception as list_debug_error:
                print(f"Error listing transcripts: {list_debug_error}")
            
            # Find English transcript
            english_transcript = None
            
            # First try manually created English
            try:
                english_transcript = transcript_list_obj.find_manually_created_transcript(['en'])
                print("Found manually created English transcript")
            except Exception as manual_error:
                print(f"No manual English transcript: {manual_error}")
                try:
                    # Then auto-generated English
                    english_transcript = transcript_list_obj.find_generated_transcript(['en'])
                    print("Found auto-generated English transcript")
                except Exception as auto_error:
                    print(f"No auto-generated English transcript: {auto_error}")
                    # Finally any English variant
                    for transcript in available_transcripts:
                        if transcript.language_code.startswith('en'):
                            english_transcript = transcript
                            print(f"Found English transcript: {transcript.language_code}")
                            break
            
            if english_transcript:
                print(f"Fetching transcript data...")
                try:
                    fetched_data = english_transcript.fetch()
                    
                    print(f"Fetched data type: {type(fetched_data)}")
                    if hasattr(fetched_data, '__len__'):
                        print(f"Fetched data length: {len(fetched_data)}")
                    
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
                        
                except Exception as fetch_error:
                    print(f"Error fetching transcript data: {fetch_error}")
            else:
                print("❌ No English transcript found")
                
        except Exception as list_error:
            print(f"List method failed: {list_error}")
            import traceback
            traceback.print_exc()
        
        # If we get here, no method worked
        print("All transcript methods failed")
        return ""

    except (TranscriptsDisabled) as e:
        print(f"Transcripts disabled for this video: {e}")
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
        
        # Truncate text if too long
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        payload = {
            "model": "deepseek/deepseek-chat:free",
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
        
        # Try direct connection first, then with proxy if needed
        try:
            print("Trying direct connection for OpenRouter API...")
            response = requests.post(
                api_url, 
                json=payload, 
                headers=headers, 
                timeout=60
            )
            
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
            
        except Exception as direct_error:
            print(f"Direct API call failed: {direct_error}")
            
            # Try with proxy as backup
            proxy_dict = proxy_manager.get_next_proxy()
            if proxy_dict:
                try:
                    print(f"Trying with proxy: {proxy_dict['http']}")
                    response = requests.post(
                        api_url, 
                        json=payload, 
                        headers=headers, 
                        timeout=60,
                        proxies=proxy_dict
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'choices' in data and len(data['choices']) > 0:
                        summary = data['choices'][0]['message']['content']
                        print(f"Summary generated successfully via proxy")
                        return summary
                        
                except Exception as proxy_error:
                    print(f"Proxy API call failed: {proxy_error}")
                    proxy_manager.mark_proxy_failed(proxy_dict)
            
            # If both direct and proxy fail, return error
            raise direct_error
        
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
        
        # Get transcript with proxy support
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
        
        return {
            "summary": summary, 
            "transcript_length": len(transcript),
            "proxies_status": {
                "working": len(proxy_manager.working_proxies),
                "failed": len(proxy_manager.failed_proxies)
            }
        }
        
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
    return {
        "status": "ok", 
        "message": "YouTube TL;DR API is running",
        "proxies_status": {
            "working": len(proxy_manager.working_proxies),
            "failed": len(proxy_manager.failed_proxies),
            "total": len(PROXY_LIST)
        }
    }

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "YouTube TL;DR API", 
        "endpoints": ["/summarize", "/health"],
        "version": "2.0"
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting YouTube TL;DR API server with proxy support...")
    print(f"Loaded {len(PROXY_LIST)} proxies")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)