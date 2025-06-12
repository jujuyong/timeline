import snscrape.modules.twitter as sntwitter
import time
import random
import os

# 쿠키 파일 경로를 환경 변수로 지정
os.environ["SNSCRAPE_TWITTER_COOKIEFILE"] = "twitter_cookies.txt"

def get_recent_tweets(username, start=0, count=10):
    tweets = []
    try:
        scraper = sntwitter.TwitterUserScraper(username)
        for i, tweet in enumerate(scraper.get_items()):
            if i < start:
                continue
            if len(tweets) >= count:
                break
            tweets.append({
                "date": tweet.date.strftime('%Y-%m-%d %H:%M:%S'),
                "content": tweet.content,
                "tweet_id": tweet.id,
                "url": tweet.url,
                "reply_count": tweet.replyCount,
                "retweet_count": tweet.retweetCount,
                "like_count": tweet.likeCount,
                "quote_count": tweet.quoteCount,
            })
            # ★ 요청 간 랜덤 딜레이 추가 (0.8~2.5초 사이)
            time.sleep(random.uniform(0.8, 2.5))
    except Exception as e:
        print(f"❌ 트윗 수집 중 오류: {e}")
    return tweets

def get_tweet_replies(username, tweet_id, max_count=20):
    query = f'to:{username} conversation_id:{tweet_id}'
    replies = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= max_count:
            break
        replies.append(tweet.content)
    return replies

def get_quote_tweets(tweet_id, max_count=20):
    # 트윗의 URL을 포함하는 트윗을 검색 (많은 인용 트윗이 이 형식)
    tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
    query = f'"{tweet_url}"'
    quote_tweets = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= max_count:
            break
        # 실제 인용(Quote) 트윗인지 추가 필터링 가능 (옵션)
        quote_tweets.append({
            "date": tweet.date.strftime('%Y-%m-%d %H:%M:%S'),
            "content": tweet.content,
            "tweet_id": tweet.id,
            "url": tweet.url,
            "username": tweet.user.username
        })
    return quote_tweets
