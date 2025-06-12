from pymongo import MongoClient
from datetime import datetime

# MongoDB 연결 설정
client = MongoClient("mongodb://localhost:27017")
db = client['sns_platform']

def save_search_history(query,platform,account_name,url,success,description,summary,user_id=None):
    """
    검색 내역(계정/링크/설명/콘텐츠 요약 등) 저장 + 검색 성공 여부, 설명, 요약 포함
    """
    db.search_history.insert_one({
        "user_id": user_id,
        "query": query,
        "platform": platform,
        "account_name": account_name,
        "url": url,
        "success": success,              # 실제 게시물/계정 존재 여부
        "description": description,      # 기본 정보(설명 등)
        "summary": summary,              # AI 요약 등
        "timestamp": datetime.utcnow()
    })

def get_recent_searches(query=None, platform=None, limit=10):
    """
    최근 검색 내역 조회 (검색어/플랫폼별, 최신순)
    """
    q = {}
    if query:
        q["query"] = {"$regex": query, "$options": "i"}
    if platform:
        q["platform"] = platform
    return list(db.search_history.find(q).sort("timestamp", -1).limit(limit))

def save_verified_account(name, url, platform, description):
    """
    실존하는 계정/채널 정보 저장
    """
    db.verified_accounts.update_one(
        {"url": url},
        {"$set": {
            "name": name,
            "platform": platform,
            "description": description,
            "timestamp": datetime.utcnow()
        }},
        upsert=True
    )

def get_verified_accounts_by_query(query, platform=None, limit=10):
    """
    설명/검색어에 맞는 실존 계정/채널 목록 조회
    """
    q = {"$or": [
        {"name": {"$regex": query, "$options": "i"}},
        {"description": {"$regex": query, "$options": "i"}}
    ]}
    if platform:
        q["platform"] = platform
    return list(db.verified_accounts.find(q).sort("timestamp", -1).limit(limit))

def save_raw_content(platform, content_id, title, content, url, author=None):
    db.raw_contents.update_one(
        {"platform": platform, "content_id": content_id},
        {"$set": {
            "title": title,
            "content": content,
            "url": url,
            "author": author,
            "timestamp": datetime.utcnow()
        }},
        upsert=True
    )