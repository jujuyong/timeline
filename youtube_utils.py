from pytube import YouTube
import os
import requests
import yt_dlp
import whisper
import tempfile
import tempfile
from googleapiclient.discovery import build
import re
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'




def extract_channel_id(channel_url):
    # /channel/UCxxxxx
    match = re.search(r"/channel/([A-Za-z0-9_\-]+)", channel_url)
    if match:
        return match.group(1)
    # /user/xxx
    match = re.search(r"/user/([^/?]+)", channel_url)
    if match:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
        resp = youtube.channels().list(forUsername=match.group(1), part="id").execute()
        items = resp.get("items")
        if items:
            return items[0]["id"]
        else:
            raise Exception("유효하지 않은 유저 채널입니다.")
    # /c/xxx 또는 /@xxx 등
    match = re.search(r"/c/([^/?]+)", channel_url) or re.search(r"/@([^/?]+)", channel_url)
    if match:
        query = match.group(1)
    else:
        query = channel_url.rstrip('/').split('/')[-1]
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_resp = youtube.search().list(
        q=query, type="channel", part="snippet", maxResults=1
    ).execute()
    items = search_resp.get("items")
    if items:
        return items[0]["snippet"]["channelId"]
    else:
        raise Exception("채널 ID 추출 실패: URL을 확인하세요.")

def get_video_id_list(channel_url, max_per_type=30):
    channel_id = extract_channel_id(channel_url)
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    # 1. 채널 기본 정보 조회 (채널명, 설명)
    channel_resp = youtube.channels().list(
        id=channel_id,
        part="snippet"
    ).execute()
    items = channel_resp.get("items", [])
    if items:
        channel_title = items[0]["snippet"].get("title", "")
        channel_description = items[0]["snippet"].get("description", "")
    else:
        channel_title = ""
        channel_description = ""

    # 2. 영상 검색 (최신순)
    videos = []
    next_page_token = None
    while len(videos) < 50:
        search_response = youtube.search().list(
            channelId=channel_id,
            part='id,snippet',
            order='date',
            maxResults=50,
            type='video',
            pageToken=next_page_token
        ).execute()
        for item in search_response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            publish_date = item['snippet']['publishedAt']
            videos.append({
                'id': video_id,
                'title': title,
                'publish_date': publish_date,
                'video_url': f"https://www.youtube.com/watch?v={video_id}"
            })
        next_page_token = search_response.get('nextPageToken')
        if not next_page_token:
            break

    # 3. 영상 타입 분류
    type_map = {"쇼츠": [], "라이브": [], "일반": []}
    for i in range(0, len(videos), 50):
        ids = ','.join([v['id'] for v in videos[i:i+50]])
        video_response = youtube.videos().list(
            part='snippet,contentDetails,liveStreamingDetails',
            id=ids
        ).execute()
        for item in video_response['items']:
            vid = item['id']
            title = item['snippet']['title']
            publish_date = item['snippet']['publishedAt']
            video_url = f"https://www.youtube.com/watch?v={vid}"
            is_shorts = '/shorts/' in video_url or '#shorts' in title.lower()
            is_live = item.get('liveStreamingDetails') is not None
            if is_live:
                video_type = "라이브"
            elif is_shorts:
                video_type = "쇼츠"
            else:
                video_type = "일반"
            type_map[video_type].append({
                "id": vid,
                "title": title,
                "publish_date": publish_date,
                "type": video_type,
            })

    # 4. 각 타입별 최신순 5개씩만 반환
    result = []
    for t in ["라이브", "쇼츠", "일반"]:
        sorted_videos = sorted(type_map[t], key=lambda x: x.get('publish_date', ''), reverse=True)
        result.extend(sorted_videos[:max_per_type])

    # 5. 채널명/설명 추가
    for v in result:
        v["channel_title"] = channel_title
        v["channel_description"] = channel_description

    return result

def youtube_search_channels(query, limit=30):
    youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))
    search_response = youtube.search().list(
        q=query,
        type="channel",
        part="snippet",
        maxResults=limit
    ).execute()
    results = []
    for item in search_response.get("items", []):
        snippet = item["snippet"]
        channel_id = item["id"]["channelId"]
        results.append({
            "platform": "youtube",
            "account_name": snippet.get("channelTitle", ""),
            "url": f"https://www.youtube.com/channel/{channel_id}",
            "description": snippet.get("description", "")
        })
    return results

def get_video_details(video_ids):
    from openai_utils import extract_sns_links
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    results = []
    for video_id in video_ids:
        response = youtube.videos().list(
            part="snippet,contentDetails,liveStreamingDetails",
            id=video_id
        ).execute()
        items = response.get("items", [])
        if not items:
            continue
        item = items[0]
        title = item["snippet"].get("title", "")
        publish_date = item["snippet"].get("publishedAt", "")
        description = item["snippet"].get("description", "")
        thumbnails = item["snippet"].get("thumbnails", {})
        thumbnail_url = thumbnails.get("high", {}).get("url", "")
        is_live = item.get("liveStreamingDetails") is not None
        is_shorts = '/shorts/' in f"https://www.youtube.com/watch?v={video_id}" or '#shorts' in title.lower()
        sns_links = extract_sns_links(description)
        results.append({
            "id": video_id,
            "title": title,
            "thumbnail_url": thumbnail_url,
            "publish_date": publish_date,
            "is_live": is_live,
            "is_shorts": is_shorts,
            "description": description,
            "sns_links": sns_links
        })
    return results

def get_youtube_comments(video_id, max_results=50):
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    comments = []
    next_page_token = None

    while len(comments) < max_results:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(100, max_results - len(comments)),
            pageToken=next_page_token,
            textFormat="plainText"
        ).execute()
        for item in response['items']:
            text = item['snippet']['topLevelComment']['snippet'].get('textDisplay', '')
            comments.append(text)
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return comments[:max_results]


def download_audio_from_youtube(
    video_url,
    lang_priority=('ko', 'en', 'a.ko', 'a.en'),
    whisper_model='base'
):
    print("download_audio_from_youtube (yt-dlp) called with:", video_url)
    # 1. yt-dlp로 자막 추출 시도
    try:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitlesformat': 'srt',
            'subtitleslangs': list(lang_priority),
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subtitles = info.get('subtitles') or info.get('automatic_captions')
            if subtitles:
                for lang in lang_priority:
                    if lang in subtitles:
                        sub_url = subtitles[lang][0]['url']
                        srt = requests.get(sub_url).text
                        # SRT에서 텍스트만 추출
                        text_lines = []
                        for line in srt.split('\n'):
                            if line.strip().isdigit() or '-->' in line or not line.strip():
                                continue
                            text_lines.append(line.strip())
                        text = '\n'.join(text_lines)
                        print("Caption extracted and returned.")
                        return text, 'caption'
    except Exception as e:
        print("yt-dlp subtitle extraction failed:", e)

    # 2. 자막이 없으면 오디오 다운로드 & Whisper
    audio_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            audio_path = f.name
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_path,
            'quiet': True,
            'noplaylist': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        model = whisper.load_model(whisper_model)
        result = model.transcribe(audio_path)
        text = result['text']
        print("Whisper transcript returned.")
        return text, 'whisper'
    except Exception as e:
        print("download_audio_from_youtube (yt-dlp) error:", e)
        raise
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)