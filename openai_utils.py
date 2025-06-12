
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from langdetect import detect
from database_utils import get_recent_searches, get_verified_accounts_by_query
from youtube_utils import youtube_search_channels
from mastodon_utils import mastodon_search_accounts

load_dotenv()
client = OpenAI()

def classify_links_with_ai(links):
    prompt = (
        "아래의 URL 리스트를 각각 유튜브, 트위터, 인스타그램, 마스토돈, 블루스카이, 홈페이지, 기타 등으로 분류해줘. "
        "각 항목은 반드시 platform, url 필드를 포함한 JSON 리스트로 반환해. "
        "예시: [{\"platform\": \"twitter\", \"url\": \"...\"}, ...]\n\n"
        "URL 리스트:\n" + "\n".join(links)
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user", "content": prompt}],
        max_tokens=500,
        temperature=0
    )
    # JSON 파싱 로직 추가 필요
    return response.choices[0].message.content

def get_db_recommendations(description, limit=5):
    """
    최근 검색 이력 + 검증된 실존 계정(verified_accounts) + 유튜브 API 검색 결과에서 추천 후보 추출
    """
    recent = get_recent_searches(query=description, limit=limit)
    verified = get_verified_accounts_by_query(description, limit=limit)
    youtube_results = youtube_search_channels(description, limit=limit)
    mastodon_results = mastodon_search_accounts(description, limit=limit)
    seen = set()
    merged = []
    for item in recent + verified + youtube_results + mastodon_results:
        url = item.get('url')
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append({
            "platform": item.get("platform", ""),
            "account_name": item.get("account_name") or item.get("name", ""),
            "url": url,
            "description": item.get("summary", "") or item.get("description", "")
        })
        if len(merged) >= limit:
            break
    return merged

def recommend_artist_with_db(description, db_results):
    """
    OpenAI에 사용자 설명과 DB 추천 후보(실존 계정/채널/게시물 정보)를 함께 전달하여 추천 결과 생성
    """
    db_info = ""
    for item in db_results:
        db_info += (
            f"- 플랫폼: {item.get('platform','')}\n"
            f"  이름: {item.get('account_name','')}\n"
            f"  링크: {item.get('url','')}\n"
            f"  설명: {item.get('description','')}\n"
        )
    prompt = (
        f"아래는 사용자가 입력한 아티스트/채널/계정에 대한 설명 또는 키워드야:\n"
        f"{description}\n\n"
        f"아래는 실제로 존재하는 유튜브/트위터/인스타그램/마스토돈/블루스카이의 계정·채널·게시물 정보야:\n"
        f"{db_info}\n"
        f"네가 학습한 정보, 웹의 정보, 내가 알려준 실존 계정 정보를 참고해서 "
        f"사용자의 입력에 가장 적합한 유튜브, 인스타그램, 트위터, 마스토돈 계정/채널/게시물 5개 이내로 추천해줘. "
        "각 추천 결과는 반드시 JSON 리스트로 반환해줘. "
        "각 항목은 반드시 platform, account_name, url, description(한국어 간단소개) 필드를 포함해야 해. "
        "예시: "
        "[{\"platform\": \"youtube\", \"account_name\": \"채널명\", \"url\": \"https://youtube.com/...\", \"description\": \"설명\"}, ...] "
        "만약 추천할 수 없다면 빈 리스트([])로 반환해."
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user", "content": prompt}],
        max_tokens=500,
        temperature=0.7,
    )
    ai_text = response.choices[0].message.content

    # JSON 리스트 추출
    match = re.search(r'\[.*\]', ai_text, re.DOTALL)
    if match:
        try:
            ai_db_results = json.loads(match.group(0))
        except Exception:
            ai_db_results = []
    else:
        ai_db_results = []

    return {
        "ai_result": ai_text,
        "db_results": ai_db_results
    }

def suggest(description, limit=5):
    """
    설명(키워드)을 받아 DB(실존 계정+검색 이력)와 OpenAI를 활용해 추천 결과 반환
    """
    db_results = get_db_recommendations(description, limit=limit)
    ai_result = recommend_artist_with_db(description, db_results)
    return {
        "ai_result": ai_result,
        "db_results": db_results
    }

def is_foreign_language(text, target_lang='ko'):
    """
    텍스트가 target_lang(기본:한국어)이 아니면 True 반환
    """
    try:
        lang = detect(text)
        return lang != target_lang
    except Exception:
        # 감지 실패 시 번역하지 않음
        return False

def translate_to_korean(text):
    """
    텍스트를 자연스러운 한국어로 번역 (OpenAI GPT 이용)
    """
    prompt = f"다음 내용을 한국어로 번역해줘:\n{text}"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def summarize_text(text):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "다음 텍스트를 요약한 결과를 한국어로 전달해 주세요."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

def extract_sns_links(description):

    if not description:
        return []
    # 1. 모든 URL 추출 (http/https)
    urls = re.findall(r'https?://[^\s"\'<>]+', description)
    if not urls:
        return []
    # 2. AI 분류 요청
    try:
        ai_json = classify_links_with_ai(urls)
        links = json.loads(ai_json)
        # 필수 필드만 추출, id는 각 플랫폼별로 url에서 파생
        for link in links:
            if link["platform"] == "twitter":
                link["id"] = link["url"].rstrip('/').split('/')[-1]
            elif link["platform"] == "instagram":
                link["id"] = link["url"].rstrip('/').split('/')[-1]
            elif link["platform"] == "mastodon":
                # 마스토돈은 https://instance/@username 형태
                m = re.search(r'https?://([^/]+)/@([A-Za-z0-9_]+)', link["url"])
                if m:
                    link["id"] = f"{m.group(2)}@{m.group(1)}"
                else:
                    link["id"] = ""
            elif link["platform"] == "youtube":
                # 채널/영상/플레이리스트 등 다양한 형태가 있으므로 url 전체를 id로 사용
                link["id"] = link["url"].rstrip('/').split('/')[-1]
                link["account_name"] = "" 
            else:
                link["id"] = ""
        return links
    except Exception:
        for link in links:
            if link["platform"] == "twitter":
                username = link["url"].rstrip('/').split('/')[-1]
                link["id"] = username
                link["account_name"] = username
            elif link["platform"] == "instagram":
                username = link["url"].rstrip('/').split('/')[-1]
                link["id"] = username
                link["account_name"] = username
            elif link["platform"] == "mastodon":
                m = re.search(r'https?://([^/]+)/@([A-Za-z0-9_]+)', link["url"])
                if m:
                    username = m.group(2)
                    instance = m.group(1)
                    link["id"] = f"{username}@{instance}"
                    link["account_name"] = username
                else  :
                    link["id"] = ""
                    link["account_name"] = ""
            elif link["platform"] == "youtube":
                username = link["url"].rstrip('/').split('/')[-1]
                link["id"] = username
                link["account_name"] = username
            else:
                link["id"] = ""
                link["account_name"] = ""
        return links