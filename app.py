from flask import Flask, request, jsonify, render_template, make_response
from youtube_utils import get_video_id_list, get_video_details, download_audio_from_youtube
from tweet_utils import get_recent_tweets, get_quote_tweets, get_tweet_replies
from mastodon_utils import get_recent_toots, get_toot_replies, get_quote_toot
from bluesky_utils import get_recent_skys, get_sky_replies, get_quote_sky
from insta_utils import get_recent_posts, get_post_comments
from openai_utils import summarize_text, is_foreign_language, translate_to_korean, suggest, extract_sns_links
from database_utils import save_search_history
from yt_dlp import YoutubeDL
import json

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/recommend_artist", methods=["POST"])
def api_recommend_artist():
    data = request.json
    description = data.get("description", "")
    if not description:
        return jsonify({"error": "description is required"}), 400
    try:
        result = suggest(description)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/translate_if_needed', methods=['POST'])
def api_translate_if_needed():
    data = request.json
    texts = data.get('texts')
    if texts and isinstance(texts, list):
        translated = []
        need_translate = []
        for text in texts:
            if not text:
                translated.append('')
                need_translate.append(False)
                continue
            try:
                is_foreign = is_foreign_language(text)
            except Exception:
                is_foreign = False
            if not is_foreign:
                translated.append('')
                need_translate.append(False)
            else:
                try:
                    translated_text = translate_to_korean(text)
                except Exception:
                    translated_text = ''
                translated.append(translated_text)
                need_translate.append(True)
        return jsonify({'translated': translated, 'need_translate': need_translate})
    # 기존 단일 텍스트 처리
    text = data.get('text', '')
    if not text:
        return jsonify({'translated': '', 'need_translate': False})
    try:
        is_foreign = is_foreign_language(text)
    except Exception:
        is_foreign = False
    if not is_foreign:
        return jsonify({'translated': '', 'need_translate': False})
    else:
        try:
            translated = translate_to_korean(text)
        except Exception:
            translated = ''
        return jsonify({'translated': translated, 'need_translate': True})

@app.route("/api/video_ids")
def api_video_ids():
    channel_url = request.args.get("channel_url")
    if not channel_url:
        return jsonify({"error": "url parameter is required"}), 400
    try:
        video_list = get_video_id_list(channel_url)
        channel_title = video_list[0].get("channel_title", channel_url) if video_list else channel_url
        description = video_list[0].get("channel_description", "") if video_list else ""
        summary = summarize_text(description) if description else ""
        # DB 저장
        save_search_history(
            query=channel_url,
            platform="youtube",
            account_name=channel_title,
            url=channel_url,
            success=bool(video_list),
            description=description,
            summary=summary
        )
        resp = make_response(jsonify(video_list))
        return update_recent_artists_cookie(resp, channel_url, channel_title)
    except Exception as e:
        save_search_history(
            query=channel_url,
            platform="youtube",
            account_name="",
            url=channel_url,
            success=False,
            description="",
            summary=""
        )
        return jsonify({"error": str(e)}), 500

@app.route("/api/video_details", methods=["POST"])
def api_video_details():
    ids = request.json.get("video_ids", [])
    details = get_video_details(ids)
    # SNS 링크도 같이 포함해서 반환
    for d in details:
        d["sns_links"] = extract_sns_links(d.get("description", ""))
    return jsonify(details)

@app.route("/timeline", methods=["POST"])
def generate_timeline():
    data = request.json
    channel_url = data.get("channel_url")
    if not channel_url:
        return jsonify({"error": "channel_url is required"}), 400

    video_id_list = get_video_id_list(channel_url)
    ids = [v["id"] for v in video_id_list[:5]]
    details = get_video_details(ids)

    timeline = []
    for video in details:
        timeline.append({
            "video_url": f"https://www.youtube.com/watch?v={video['id']}",
            "title": video.get("title", ""),
            "thumbnail_url": video.get("thumbnail_url", ""),
            "publish_date": video.get("publish_date", ""),
            "is_live": video.get("is_live", False),
            "summary": None,
            "sns_links": video.get("sns_links", [])
        })

    return jsonify({"timeline": timeline})

@app.route("/api/recent_tweets")
def api_recent_tweets():
    username = request.args.get("username")
    try:
        start = int(request.args.get("start", 0))
        count = int(request.args.get("count", 10))
    except ValueError:
        return jsonify({"error": "start, count는 정수여야 합니다."}), 400

    if not username:
        return jsonify({"error": "username parameter is required"}), 400

    try:
        tweets = get_recent_tweets(username, start, count)
        display_name = tweets[0].get("display_name", username) if tweets else username

        description = tweets[0].get("description", "") if tweets else ""
        summary = summarize_text(description) if description else ""
        save_search_history(
            query=username,
            platform="twitter",
            account_name=display_name,
            url=f"https://twitter.com/{username}",
            success=bool(tweets),
            description=description,
            summary=summary
        )

        resp = make_response(jsonify(tweets))
        return update_recent_artists_cookie(resp, f"twitter:{username}", display_name)
    except Exception as e:
        save_search_history(
            query=username,
            platform="twitter",
            account_name="",
            url=f"https://twitter.com/{username}",
            success=False,
            description="",
            summary=""
        )
        return jsonify({"error": str(e)}), 500

@app.route("/api/recent_bluesky_skys")
def api_recent_bluesky_skys():
    username = request.args.get("username")
    try:
        start = int(request.args.get("start", 0))
        count = int(request.args.get("count", 10))
    except ValueError:
        return jsonify({"error": "start, count는 정수여야 합니다."}), 400

    if not username:
        return jsonify({"error": "username parameter is required"}), 400

    try:
        skys = get_recent_skys(username, start, count)
        display_name = skys[0].get("author", username) if skys else username

        description = skys[0].get("content", "") if skys else ""
        summary = summarize_text(description) if description else ""
        save_search_history(
            query=username,
            platform="bluesky",
            account_name=display_name,
            url=f"https://bsky.app/profile/{username}",
            success=bool(skys),
            description=description,
            summary=summary
        )

        resp = make_response(jsonify(skys))
        return update_recent_artists_cookie(resp, f"bluesky:{username}", display_name)
    except Exception as e:
        save_search_history(
            query=username,
            platform="bluesky",
            account_name="",
            url=f"https://bsky.app/profile/{username}",
            success=False,
            description="",
            summary=""
        )
        return jsonify({"error": str(e)}), 500

@app.route('/api/recent_instagram_posts')
def api_recent_instagram_posts():
    username = request.args.get("username")
    start = int(request.args.get("start", 0))
    count = int(request.args.get("count", 10))
    posts = get_recent_posts(username, start, count)
    display_name = posts[0].get("full_name", username) if posts else username

    description = posts[0].get("biography", "") if posts else ""
    summary = summarize_text(description) if description else ""
    save_search_history(
        query=username,
        platform="instagram",
        account_name=display_name,
        url=f"https://instagram.com/{username}",
        success=bool(posts),
        description=description,
        summary=summary
    )

    resp = make_response(jsonify(posts))
    return update_recent_artists_cookie(resp, f"instagram:{username}", display_name)

@app.route("/api/recent_mastodon_toots")
def api_recent_mastodon_toots():
    username = request.args.get("username")
    user_id = request.args.get("user_id")
    instance = request.args.get("instance", "https://mastodon.social")
    try:
        start = int(request.args.get("start", 0))
        count = int(request.args.get("count", 10))
    except ValueError:
        return jsonify({"error": "start, count는 정수여야 합니다."}), 400

    if not username and not user_id:
        return jsonify({"error": "username 또는 user_id parameter가 필요합니다."}), 400

    try:
        toots = get_recent_toots(username, instance, start, count, user_id)
        display_name = username if username else user_id

        description = toots[0].get("note", "") if toots else ""
        summary = summarize_text(description) if description else ""
        save_search_history(
            query=username or user_id,
            platform="mastodon",
            account_name=display_name,
            url=f"{instance}/@{username or user_id}",
            success=bool(toots),
            description=description,
            summary=summary
        )

        resp = make_response(jsonify(toots))
        return update_recent_artists_cookie(resp, f"mastodon:{instance}/@{username}", display_name)
    except Exception as e:
        save_search_history(
            query=username or user_id,
            platform="mastodon",
            account_name="",
            url=f"{instance}/@{username or user_id}",
            success=False,
            description="",
            summary=""
        )
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/bluesky_sky_reactions")
def api_bluesky_sky_reactions():
    post_id = request.args.get("post_id")
    if not post_id:
        return jsonify({"error": "post_id가 필요합니다."}), 400

    try:
        replies = get_sky_replies(post_id, max_count=20)
        quotes = get_quote_sky(post_id, max_count=20)
        all_reactions = [r["content"] for r in replies] + [str(q.get("repost_count", "")) for q in quotes]
        if not all_reactions:
            return jsonify({"summary": "댓글/인용이 없습니다.", "replies": replies, "quotes": quotes})
        reaction_text = "\n".join(all_reactions)
        summary = summarize_text(f"다음은 한 블루스카이 게시물에 대한 댓글과 인용(리포스트) 수입니다. 전체 반응을 한국어로 요약해줘:\n{reaction_text}")

        save_search_history(
            query=post_id,
            platform="bluesky",
            account_name="",  # 필요시 계정명 추가
            url=f"https://bsky.app/profile//post/{post_id.split('/')[-1]}",
            success=True,
            description="블루스카이 게시물 반응 요약",
            summary=summary
        )

        return jsonify({"summary": summary, "replies": replies, "quotes": quotes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/tweet_reactions")
def api_tweet_reactions():
    username = request.args.get("username")
    tweet_id = request.args.get("tweet_id")
    if not username or not tweet_id:
        return jsonify({"error": "username과 tweet_id가 필요합니다."}), 400

    try:
        replies = get_tweet_replies(username, tweet_id, max_count=20)
        quotes = get_quote_tweets(tweet_id, max_count=20)
        all_reactions = replies + [q["content"] for q in quotes]
        if not all_reactions:
            return jsonify({"summary": "댓글/인용이 없습니다.", "replies": [], "quotes": []})
        reaction_text = "\n".join(all_reactions)
        summary = summarize_text(f"다음은 한 트윗에 대한 댓글과 인용 트윗들입니다. 전체 반응을 한국어로 요약해줘:\n{reaction_text}")

        save_search_history(
            query=username,
            platform="twitter",
            account_name=username,
            url=f"https://twitter.com/{username}/status/{tweet_id}",
            success=True,
            description="트윗 반응 요약",
            summary=summary
        )

        return jsonify({"summary": summary, "replies": replies, "quotes": quotes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/mastodon_toot_reactions")
def api_mastodon_toot_reactions():
    status_id = request.args.get("status_id")
    instance = request.args.get("instance", "https://mastodon.social")
    if not status_id:
        return jsonify({"error": "status_id가 필요합니다."}), 400

    try:
        replies = get_toot_replies(status_id, instance)
        quotes = get_quote_toot(status_id, instance)
        all_reactions = [r["content"] for r in replies] + [q["content"] for q in quotes]
        if not all_reactions:
            return jsonify({"summary": "댓글/인용이 없습니다.", "replies": replies, "quotes": quotes})
        reaction_text = "\n".join(all_reactions)
        summary = summarize_text(f"다음은 한 마스토돈 툿에 대한 댓글과 인용(언급) 툿들입니다. 전체 반응을 한국어로 요약해줘:\n{reaction_text}")

        save_search_history(
            query=status_id,
            platform="mastodon",
            account_name="",  # 필요시 계정명 추가
            url=f"{instance}/@{status_id}",
            success=True,
            description="마스토돈 툿 반응 요약",
            summary=summary
        )

        return jsonify({"summary": summary, "replies": replies, "quotes": quotes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/instagram_post_reactions')
def api_instagram_post_reactions():
    post_id = request.args.get("post_id")
    shortcode = request.args.get("shortcode")
    if not shortcode:
        return jsonify({"error": "shortcode is required"}), 400
    comments = get_post_comments("", shortcode)
    if not comments:
        return jsonify({"summary": "댓글 없음", "comments": []})
    reaction_text = "\n".join(comments)
    summary = summarize_text(f"다음은 인스타그램 게시물의 댓글들입니다. 전체 반응을 한국어로 요약해줘:\n{reaction_text}")
    save_search_history(
        query=shortcode,
        platform="instagram",
        account_name="",  # 필요시 계정명 추가
        url=f"https://instagram.com/p/{shortcode}",
        success=True,
        description="인스타그램 게시물 반응 요약",
        summary=summary
    )
    return jsonify({"summary": summary, "comments": comments})

@app.route("/summary", methods=["POST"])
def summarize_single_video():
    data = request.json
    print("summary POST data:", data)
    video_url = data.get("video_url")
    title = data.get("title")
    thumbnail_url = data.get("thumbnail_url")
    publish_date = data.get("publish_date")
    description = data.get("description", "")
    mode = data.get("mode", "audio")  # 기본값은 audio

    print(f"video_url: {video_url}, title: {title}, mode: {mode}")
    print(f"thumbnail_url: {thumbnail_url}, publish_date: {publish_date}")
    print(f"description: {description[:100]}")  # 너무 길면 앞 100자만

    if not video_url:
        print("video_url is missing")
        return jsonify({"error": "video_url is required"}), 400
    if mode == "description" and not description:
        try:
            print("Trying to extract description with YoutubeDL...")
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                description = info.get("description", "")
                print("Extracted description:", description[:100])
        except Exception as e:
            print("YoutubeDL description extraction failed:", e)
            return jsonify({"error": "description 추출 실패: " + str(e)}), 500

    try:
        if mode == "description":
            if not description:
                print("description is missing after YoutubeDL extraction")
                return jsonify({"error": "description is missing"}), 400
            print("Summarizing description...")
            summary = summarize_text(description)
            print("Summary result:", summary[:100])
        else:
            print("Downloading audio and transcribing...")
            transcript, source = download_audio_from_youtube(video_url)
            print("Transcript:", transcript[:100])
            summary = summarize_text(transcript)
            print("Summary result:", summary[:100])
            return jsonify({
                "summary": summary,
                "source": source
            })

        print("Saving search history...")
        save_search_history(
            query=video_url,
            platform="youtube",
            account_name=title,
            url=video_url,
            success=True,
            description=description,
            summary=summary
        )

        print("Returning summary response")
        return jsonify({
            "video_url": video_url,
            "title": title,
            "thumbnail_url": thumbnail_url,
            "publish_date": publish_date,
            "summary": summary,
            "description": description,
            "mode": mode
        })

    except Exception as e:
        print("summarize_single_video error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/save_search_history", methods=["POST"])
def api_save_search_history():
    data = request.json
    save_search_history(
        query=data.get("query"),
        platform=data.get("platform"),
        account_name=data.get("account_name"),
        url=data.get("url"),
        success=data.get("success", True),
        description=data.get("description", ""),
        summary=data.get("summary", "")
    )
    return jsonify({"result": "ok"})

@app.route("/api/recent_artists")
def api_recent_artists():
    recent = request.cookies.get("recent_artists")
    try:
        recent_list = json.loads(recent) if recent else []
    except Exception:
        recent_list = []
    return jsonify(recent_list)

def update_recent_artists_cookie(resp, artist_id, display_name):
    recent = request.cookies.get("recent_artists")
    recent_list = json.loads(recent) if recent else []
    # 중복 제거
    recent_list = [item for item in recent_list if item["id"] != artist_id]
    recent_list.insert(0, {"id": artist_id, "name": display_name})
    recent_list = recent_list[:10]
    resp.set_cookie("recent_artists", json.dumps(recent_list), max_age=60*60*24*30)
    return resp

if __name__ == "__main__":
    app.run(debug=True)
