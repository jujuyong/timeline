from mastodon import Mastodon
from bs4 import BeautifulSoup
import requests

def html_to_text(html):
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)

def get_mastodon_client(instance_url="https://mastodon.social"):
    return Mastodon(
        api_base_url=instance_url,
        access_token="mpX28vXvWV2qrZ53lrFFhhe_4AIcwiw-Oj60Z1irWF8"
    )

def mastodon_search_accounts(query, limit=5, instance_url="https://mastodon.social"):
    """
    마스토돈 인스턴스에서 계정 검색
    """
    url = f"{instance_url}/api/v2/search"
    params = {
        "q": query,
        "type": "accounts",
        "limit": limit
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        accounts = resp.json().get("accounts", [])
        results = []
        for acc in accounts:
            results.append({
                "platform": "mastodon",
                "account_name": acc.get("display_name") or acc.get("username"),
                "url": acc.get("url"),
                "description": acc.get("note", "")
            })
        return results
    except Exception:
        return []
    
def resolve_user_id(username, instance_url='https://mastodon.social'):
    mastodon = Mastodon(api_base_url=instance_url)
    try:
        # 우선 lookup 시도 (username이 acct 형식이 아니어도 대부분 동작)
        user = mastodon.account_lookup(acct=username)
        print(f"[DEBUG] account_lookup('{username}') result: {user}")
        return user['id']
    except Exception as e:
        print(f"[DEBUG] account_lookup error for '{username}': {e}")
        # fallback: account_search
        try:
            results = mastodon.account_search(username)
            print(f"[DEBUG] account_search('{username}') results: {results}")
            if not results:
                print(f"[DEBUG] No user found for username: {username} on {instance_url}")
                return None
            print(f"[DEBUG] Resolved user_id for '{username}': {results[0]['id']}")
            return results[0]['id']
        except Exception as e2:
            print(f"[DEBUG] account_search error for '{username}': {e2}")
            return None

def get_recent_toots(username=None, instance_url='https://mastodon.social', start=0, count=10, user_id=None):
    try:
        mastodon = get_mastodon_client(instance_url)
        if not user_id:
            user_id = resolve_user_id(username, instance_url)
        if not user_id:
            return []
        statuses = mastodon.account_statuses(user_id, limit=start+count)
        posts = []
        for i, status in enumerate(statuses):
            if i < start:
                continue
            if len(posts) >= count:
                break
            posts.append({
                "date": status['created_at'],
                "content": html_to_text(status['content']),
                "status_id": status['id'],
                "url": status['url'],
                "reply_count": status.get('replies_count', 0),
                "reblog_count": status.get('reblogs_count', 0),
                "favourite_count": status.get('favourites_count', 0),
                "account": status['account']['acct']
            })
        return posts
    except Exception as e:
        print(f"[ERROR] get_recent_toots: {e}")
        return []

def get_toot_replies(status_id, instance_url='https://mastodon.social', max_count=20):

    mastodon = get_mastodon_client(instance_url)
    context = mastodon.status_context(status_id)
    replies = context['descendants']
    reply_list = []
    for reply in replies[:max_count]:
        reply_list.append({
            "date": reply['created_at'],
            "content": html_to_text(reply['content']),
            "status_id": reply['id'],
            "url": reply['url'],
            "account": reply['account']['acct']
        })
    return reply_list

def get_quote_toot(status_id, instance_url='https://mastodon.social', max_count=20):

    mastodon = get_mastodon_client(instance_url)
    # status_id로 status의 URL을 얻음
    status = mastodon.status(status_id)
    status_url = status['url']
    # 해당 URL을 포함하는 공개 게시글 검색
    results = mastodon.search(status_url, resolve=True)
    statuses = results.get('statuses', [])
    quote_list = []
    for s in statuses[:max_count]:
        quote_list.append({
            "date": s['created_at'],
            "content": html_to_text(s['content']),
            "status_id": s['id'],
            "url": s['url'],
            "account": s['account']['acct']
        })
    return quote_list