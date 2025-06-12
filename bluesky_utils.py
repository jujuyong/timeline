from atproto import Client,  exceptions
import os
import json

client = Client()

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")  # 예: 'yourid.bsky.social'
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")  # 앱 비밀번호

def get_bluesky_client():
    try:
        client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        print(f"loginsuccessed")
    except exceptions.AtProtocolError as e:
        print(f'Login failed: {e}')
    return client

def bluesky_search_accounts(query, limit=5):
    client = get_bluesky_client()
    resp = client.com.atproto.identity.search_actors({'term': query, 'limit': limit})
    if hasattr(resp, "json"):
        resp = resp.json()
    # resp가 dict가 아니고 str이면 json.loads 시도
    if not isinstance(resp, dict):
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
                print("bluesky_search_accounts: resp was str, converted to dict with json.loads")
            except Exception as e:
                print(f"bluesky_search_accounts: json.loads failed: {e}")
                print(f"bluesky_search_accounts: Bluesky API response is not dict: {resp} (type: {type(resp)})")
                return []
        else:
            print(f"bluesky_search_accounts: Bluesky API response is not dict: {resp} (type: {type(resp)})")
            return []
    actors = resp.get('actors', [])
    results = []
    for user in actors:
        if not isinstance(user, dict):
            continue
        results.append({
            "platform": "bluesky",
            "account_name": user.get("displayName") or user.get("handle"),
            "url": f"https://bsky.app/profile/{user.get('handle')}",
            "description": user.get("description", "")
        })
    return results

def get_recent_skys(username=None, start=0, count=10):
    client = get_bluesky_client()
    print(f"get_recent_skys: username={username}, start={start}, count={count}")
    try:
        resp = client.app.bsky.feed.get_author_feed({'actor': username, 'limit': start+count})
        if hasattr(resp, "json"):
            resp = resp.json()
        # resp가 dict가 아니고 str이면 json.loads 시도
        if not isinstance(resp, dict):
            if isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                    print("resp was str, converted to dict with json.loads")
                except Exception as e:
                    print(f"json.loads failed: {e}")
                    print(f"Bluesky API response is not dict: {resp} (type: {type(resp)})")
                    return []
            else:
                print(f"Bluesky API response is not dict: {resp} (type: {type(resp)})")
                return []
        feed = resp.get('feed', [])
        if not isinstance(feed, list):
            print(f"feed is not a list: {feed} (type: {type(feed)})")
            feed = []
        posts = []
        for i, item in enumerate(feed):
            if not isinstance(item, dict):
                print(f"skip non-dict item at index {i}: {item} (type: {type(item)})")
                continue
            if i < start:
                continue
            if len(posts) >= count:
                break
            post = item.get('post', {})
            if not isinstance(post, dict):
                print(f"skip non-dict post at index {i}: {post} (type: {type(post)})")
                continue
            posts.append({
                "date": post.get('record', {}).get('createdAt', ''),
                "content": post.get('record', {}).get('text', ''),
                "post_id": post.get('uri'),
                "url": f"https://bsky.app/profile/{username}/post/{post.get('uri').split('/')[-1]}",
                "author": post.get('author', {}).get('handle', username)
            })
        return posts
    except Exception as e:
        print("get_recent_skys error:", e)
        raise

def get_sky_replies(post_uri, max_count=20):
    client = get_bluesky_client()
    resp = client.app.bsky.feed.get_post_thread({'uri': post_uri})
    if hasattr(resp, "json"):
        resp = resp.json()
    # str이면 dict로 변환 시도
    if not isinstance(resp, dict):
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
                print("get_sky_replies: resp was str, converted to dict with json.loads")
            except Exception as e:
                print(f"get_sky_replies: json.loads failed: {e}")
                print(f"get_sky_replies: Bluesky API response is not dict: {resp} (type: {type(resp)})")
                return []
        else:
            print(f"get_sky_replies: Bluesky API response is not dict: {resp} (type: {type(resp)})")
            return []
    thread = resp.get('thread', {})
    replies = []
    reply_list = thread.get('replies', [])
    if not isinstance(reply_list, list):
        reply_list = []
    for reply in reply_list[:max_count]:
        if not isinstance(reply, dict):
            continue
        post = reply.get('post', {})
        replies.append({
            "date": post.get('record', {}).get('createdAt', ''),
            "content": post.get('record', {}).get('text', ''),
            "post_id": post.get('uri'),
            "url": f"https://bsky.app/profile/{post.get('author', {}).get('handle', '')}/post/{post.get('uri').split('/')[-1]}",
            "author": post.get('author', {}).get('handle', '')
        })
    return replies

def get_quote_sky(post_uri, max_count=20):
    client = get_bluesky_client()
    resp = client.app.bsky.feed.get_post_thread({'uri': post_uri})
    if hasattr(resp, "json"):
        resp = resp.json()
    # str이면 dict로 변환 시도
    if not isinstance(resp, dict):
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
                print("get_quote_sky: resp was str, converted to dict with json.loads")
            except Exception as e:
                print(f"get_quote_sky: json.loads failed: {e}")
                print(f"get_quote_sky: Bluesky API response is not dict: {resp} (type: {type(resp)})")
                return [{"repost_count": 0}]
        else:
            print(f"get_quote_sky: Bluesky API response is not dict: {resp} (type: {type(resp)})")
            return [{"repost_count": 0}]
    post = resp.get('thread', {}).get('post', {})
    repost_count = post.get('repostCount', 0)
    return [{"repost_count": repost_count}]