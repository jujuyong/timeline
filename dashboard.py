# dashboard.py
import streamlit as st
from database_utils import get_recent_searches
from pymongo import MongoClient

st.title("SNS 추천 서비스 관리자/분석 대시보드")

# 최근 검색 내역
st.header("최근 검색 내역")
searches = get_recent_searches(limit=20)
for s in searches:
    st.write(f"{s['platform']} | {s['account_name']} | {s['url']}")
    st.caption(s.get('summary','') or s.get('description',''))

# 인기 추천 계정 (좋아요 순)
#st.header("사용자 피드백 기반 인기 계정")
#top_accounts = get_top_liked_accounts(limit=10)
#for acc in top_accounts:
#    st.write(f"{acc['account_name']} ({acc['_id']}) - 좋아요 {acc['count']}회")

# 피드백 통계 시각화
client = MongoClient("mongodb://localhost:27017")
db = client['sns_platform']
feedback_stats = db.feedback.aggregate([
    {"$group": {"_id": "$feedback_type", "count": {"$sum": 1}}}
])
feedback_stats = list(feedback_stats)
if feedback_stats:
    st.header("피드백 통계")
    st.bar_chart({x['_id']: x['count'] for x in feedback_stats})