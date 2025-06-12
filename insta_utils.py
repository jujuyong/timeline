from itertools import islice
import instaloader
from instaloader.exceptions import ProfileNotExistsException

def get_recent_posts(username, start=0, count=10):
    """
    인스타그램 공개 계정에서 최근 게시물을 가져옵니다.
    """
    L = instaloader.Instaloader(download_pictures=False, download_videos=False, quiet=True)
    posts = []

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        for post in islice(profile.get_posts(), start, start + count):
            posts.append({
                "post_id": post.mediaid,
                "shortcode": post.shortcode,
                "image_url": post.url,
                "caption": post.caption or "",
                "date": post.date_utc.strftime('%Y-%m-%d %H:%M:%S'),
                "likes": post.likes,
                "comments": post.comments,
                "post_url": f"https://www.instagram.com/p/{post.shortcode}/"
            })
    except ProfileNotExistsException:
        print(f"❌ 계정이 존재하지 않습니다: {username}")
    except Exception as e:
        print(f"⚠️ 게시물 수집 중 오류 발생: {e}")

    return posts


def get_post_comments(username, shortcode, max_count=20):
    """
    특정 게시물(단축코드)의 댓글을 최대 max_count개 가져옵니다.
    :param username: 인스타그램 사용자명
    :param shortcode: 게시물의 인스타그램 단축코드 (예: 'CiF2fV7l...')
    :param max_count: 최대 가져올 댓글 수
    :return: 댓글 리스트 (텍스트만)
    """
    L = instaloader.Instaloader(download_pictures=False, download_videos=False, quiet=True)
    comments = []
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        for i, comment in enumerate(post.get_comments()):
            if i >= max_count:
                break
            comments.append(comment.text)
    except Exception as e:
        print(f"Error fetching comments: {e}")
    return comments
