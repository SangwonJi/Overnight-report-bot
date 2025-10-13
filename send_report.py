import os
import requests
import json
from datetime import date, timedelta, datetime, timezone

# .env 파일을 읽어와 환경 변수로 설정합니다. (로컬 테스트용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# (A) 모니터링할 국가, 도시, 대륙 목록
CITIES = { 'IQ': 'Iraq', 'TR': 'Turkey', 'PK': 'Pakistan', 'EG': 'Egypt', 'RU': 'Russia', 'ID': 'Indonesia', 'SA': 'Saudi Arabia', 'UZ': 'Uzbekistan', 'US': 'United States', 'VN': 'Vietnam', 'DE': 'Germany', 'HK': 'Hong Kong' }
COUNTRY_DETAILS = { 'IQ': {'name_ko': '이라크', 'flag': '🇮🇶'}, 'TR': {'name_ko': '터키', 'flag': '🇹🇷'}, 'PK': {'name_ko': '파키스탄', 'flag': '🇵🇰'}, 'EG': {'name_ko': '이집트', 'flag': '🇪🇬'}, 'RU': {'name_ko': '러시아', 'flag': '🇷🇺'}, 'ID': {'name_ko': '인도네시아', 'flag': '🇮🇩'}, 'SA': {'name_ko': '사우디아라비아', 'flag': '🇸🇦'}, 'UZ': {'name_ko': '우즈베키스탄', 'flag': '🇺🇿'}, 'US': {'name_ko': '미국', 'flag': '🇺🇸'}, 'VN': {'name_ko': '베트남', 'flag': '🇻🇳'}, 'DE': {'name_ko': '독일', 'flag': '🇩🇪'}, 'HK': {'name_ko': '홍콩', 'flag': '🇭🇰'} }
CONTINENTS = ["Middle East", "Europe", "Asia", "North America"]

# (B) GNews에서 검색할 키워드 목록
NEWS_KEYWORDS = [ "protest", "accident", "incident", "disaster", "unrest", "riot", "war", "conflict", "attack", "military", "clash", "rebellion", "uprising", "flood", "earthquake" ]
INTERNET_KEYWORDS = ["internet outage", "blackout", "power outage", "submarine cable", "network failure", "isp down"]
IGNORE_PHRASES = [ "관련 뉴스 없음", "주요 지진 없음", "예정된 공휴일 없음" ]

# (C) [최종 수정] Gemini API를 requests로 직접 호출하는 번역 함수
def call_gemini_api(prompt):
    """Gemini API를 직접 호출하여 결과를 반환하는 통합 함수."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None, "(API 키 없음)"

    # 올바른 v1beta 엔드포인트 사용
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        response_json = response.json()
        
        candidates = response_json.get('candidates', [])
        if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
            return candidates[0]['content']['parts'][0].get('text', '').strip(), None
        else:
            return None, f"API 응답 구조 오류"
            
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            if e.response.status_code == 429:
                return None, "API 한도 초과"
            return None, f"API 요청 실패: {e.response.status_code}"
        return None, f"API 연결 실패"
    except Exception as e:
        return None, f"알 수 없는 에러: {e}"

def translate_text_with_gemini(text_to_translate, context="weather alert"):
    if context == "news":
        prompt = f"""Translate the following news headline into Korean. Do not add any explanation, romanization, or markdown formatting. Input: '{text_to_translate}'"""
    else:
        prompt = f"""Translate the following single weather alert term into a single, official Korean equivalent. Do not add any explanation, romanization, or markdown formatting. For example, if the input is "Thunderstorm gale", the output should be just "뇌우 강풍". Input: '{text_to_translate}'"""

    result, error = call_gemini_api(prompt)
    if error:
        return f"{text_to_translate} (번역 에러)"
    return result.replace("*", "") if result else f"{text_to_translate} (번역 결과 없음)"

# (D) 데이터 수집 함수들
def check_internet_news(country_code, country_name):
    try:
        api_key = os.environ.get("GNEWS_API_KEY")
        if not api_key: return "(API 키 없음)"
        query_keywords = " OR ".join(f'"{k}"' for k in INTERNET_KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country={country_code.lower()}&max=2&token={api_key}"
        response = requests.get(url, timeout=10).json()
        articles = response.get('articles', [])
        if not articles: return "관련 뉴스 없음"
        news_info = ""
        for article in articles:
            title = article.get('title', '')
            article_url = article.get('url', '')
            translated_title = translate_text_with_gemini(title, context="news")
            news_info += f"🌐 <{article_url}|{translated_title}>\n"
        return news_info
    except Exception as e:
        return f"수집 중 에러: {e}"

def get_weather_info(country_code):
    try:
        api_key = os.environ.get("WEATHERAPI_API_KEY")
        if not api_key: return "(API 키 없음)"
        city = CITIES.get(country_code)
        if not city: return "(도시 정보 없음)"
        url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={city}&days=1&aqi=no&alerts=yes"
        response = requests.get(url, timeout=10).json()
        alerts = response.get('alerts', {}).get('alert', [])
        if not alerts: return f"{city} 기준 특보 없음"
        alert_info = ""
        unique_alerts = {alert.get('event') for alert in alerts}
        for event in unique_alerts:
            translated_event = translate_text_with_gemini(event)
            alert_info += f"🚨 '{translated_event}' 특보 발령!\n"
        return alert_info.strip()
    except Exception: return "조회 에러"

def check_for_holidays(country_code):
    try:
        api_key = os.environ.get("CALENDARIFIC_API_KEY")
        if not api_key: return "(API 키 없음)"
        VALID_HOLIDAY_TYPES = ["National holiday", "Public holiday"]
        today = date.today()
        url = f"https://calendarific.com/api/v2/holidays?api_key={api_key}&country={country_code}&year={today.year}"
        response = requests.get(url, timeout=10).json()
        holidays = response.get('response', {}).get('holidays', [])
        tomorrow = today + timedelta(days=1)
        holiday_info = ""
        for h in holidays:
            if any(valid_type in h['type'] for valid_type in VALID_HOLIDAY_TYPES):
                holiday_date = datetime.fromisoformat(h['date']['iso']).date()
                if holiday_date == today:
                    holiday_info += f"🎉 *오늘! '{h['name']}'*\n"
                elif holiday_date == tomorrow:
                    holiday_info += f"🎉 *내일! '{h['name']}'*\n"
        return holiday_info if holiday_info else "예정된 공휴일 없음"
    except Exception: return "조회 에러"

def check_for_earthquakes(country_code, country_name):
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        response = requests.get(url, timeout=10).json()
        features = response.get('features', [])
        earthquake_info = ""
        kst = timezone(timedelta(hours=9))
        for eq in features:
            mag = eq.get('properties', {}).get('mag')
            if mag is not None and mag >= 6.0:
                place = eq.get('properties', {}).get('place', 'N/A')
                if country_name.lower() in place.lower() or f" {country_code.upper()}" in place.upper():
                    time_utc = datetime.fromtimestamp(eq['properties']['time'] / 1000, tz=timezone.utc)
                    time_kst = time_utc.astimezone(kst).strftime('%Y-%m-%d %H:%M KST')
                    earthquake_info += f"⚠️ *규모 {mag} ({time_kst}):* {place}\n"
        return earthquake_info if earthquake_info else "주요 지진 없음"
    except Exception: return "조회 에러"

def get_comprehensive_news(country_code, country_name):
    try:
        api_key = os.environ.get("GNEWS_API_KEY")
        if not api_key: return "(API 키 없음)"
        query_keywords = " OR ".join(f'"{k}"' for k in NEWS_KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country={country_code.lower()}&max=3&token={api_key}"
        response = requests.get(url, timeout=10).json()
        articles = response.get('articles', [])
        if not articles: return "관련 뉴스 없음"
        news_info = ""
        for article in articles:
            title = article.get('title', '')
            article_url = article.get('url', '')
            translated_title = translate_text_with_gemini(title, context="news")
            news_info += f"• <{article_url}|{translated_title}>\n"
        return news_info
    except Exception:
        return "수집 중 에러"

def get_continental_news(continent_name):
    try:
        api_key = os.environ.get("GNEWS_API_KEY")
        if not api_key: return "(API 키 없음)"
        continental_keywords = ["protest", "disaster", "war", "conflict", "internet outage"]
        query_keywords = " OR ".join(f'"{k}"' for k in continental_keywords)
        query = f'"{continent_name}" AND ({query_keywords})'
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=3&token={api_key}"
        response = requests.get(url, timeout=10).json()
        articles = response.get('articles', [])
        if not articles: return "관련 뉴스 없음"
        news_info = ""
        for article in articles:
            title = article.get('title', '')
            article_url = article.get('url', '')
            translated_title = translate_text_with_gemini(title, context="news")
            news_info += f"• <{article_url}|{translated_title}>\n"
        return news_info
    except Exception:
        return "수집 중 에러"

def get_summary_from_gemini(report_text):
    prompt = f"""You are an analyst summarizing overnight global events for a mobile game manager. Based on the following raw report, please create a concise summary in Korean with a maximum of 3 bullet points.
    Please use a hyphen (-) for bullet points, not an asterisk (*).
    Focus only on the most critical issues that could impact game traffic. If there are no significant events, simply state that.

    Raw Report: --- {report_text} --- Summary:"""
    
    result, error = call_gemini_api(prompt)
    if error:
        return f"* (요약 생성 중 에러: {error})"
    return result if result else "* (요약 생성 결과 없음)"

# (E) 보고서 데이터를 '딕셔너리'로 생성하는 함수
def get_report_data(country_code, country_name):
    report_data = {
        "인터넷 상태": check_internet_news(country_code, country_name),
        "날씨 특보": get_weather_info(country_code),
        "공휴일": check_for_holidays(country_code),
        "지진 (규모 6.0+)": check_for_earthquakes(country_code, country_name),
        "기타 주요 뉴스": get_comprehensive_news(country_code, country_name)
    }
    return report_data

# (F) Slack Block Kit을 사용하여 메시지를 보내는 함수
def send_to_slack(blocks):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url: return False
    payload = {"blocks": blocks}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print(f"  --> 메시지 전송 성공!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 메시지 전송 실패: {e}")
        return False

# (G) 특이사항을 판단하는 헬퍼 함수
def is_content_noteworthy(content):
    if not content or not content.strip():
        return False
    clean_content = content.strip()
    if clean_content in IGNORE_PHRASES:
        return False
    if "특보 없음" in clean_content:
        return False
    if "에러" in clean_content or "실패" in clean_content:
        return False
    return True

# (H) 메인 실행 부분
print("리포트 생성을 시작합니다...")
all_reports_data = []
for code, name in CITIES.items():
    print(f"--- {name} ({code}) 데이터 수집 중 ---")
    data = get_report_data(code, name)
    all_reports_data.append({'code': code, 'name': name, 'data': data})

# 요약을 위한 전체 텍스트 생성
full_report_text_for_summary = ""
for report in all_reports_data:
    if any(is_content_noteworthy(content) for content in report['data'].values()):
        details = COUNTRY_DETAILS.get(report['code'], {})
        name_ko = details.get('name_ko', report['name'])
        flag = details.get('flag', '🌐')
        report_section = [f"*{flag} {name_ko} ({report['code']})*"]
        for title, content in report['data'].items():
            if content:
                report_section.append(f"*{title}:*\n{content}")
        full_report_text_for_summary += "\n".join(report_section) + "\n\n"

print("\nGemini API로 요약 생성 중...")
summary = get_summary_from_gemini(full_report_text_for_summary)

today_str = datetime.now().strftime("%Y-%m-%d")
summary_blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": f"🚨 글로벌 종합 모니터링 리포트 ({today_str})", "emoji": True}},
    {"type": "section", "text": {"type": "mrkdwn", "text": f"*주요 이슈 요약:*\n{summary}"}}
]
print("\nSlack으로 요약 리포트를 전송합니다...")
send_to_slack(summary_blocks)

print("\n대륙별 뉴스를 전송합니다...")
continental_news_parts = []
for continent in CONTINENTS:
    news = get_continental_news(continent)
    if news and news != "관련 뉴스 없음" and "(API 키 없음)" not in news:
        continental_news_parts.append(f"*{continent}:*\n{news}")

if continental_news_parts:
    continental_blocks = [
        {"type": "divider"},
        {"type": "header", "text": {"type": "plain_text", "text": "🗺️ 대륙별 주요 뉴스 요약", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n\n".join(continental_news_parts)}}
    ]
    send_to_slack(continental_blocks)

print("\n특이사항 국가 상세 리포트를 전송합니다...")
noteworthy_reports_found = False
for report in all_reports_data:
    has_noteworthy_issue = any(is_content_noteworthy(content) for content in report['data'].values())
    
    if has_noteworthy_issue:
        if not noteworthy_reports_found:
            send_to_slack([{"type": "header", "text": {"type": "plain_text", "text": "📍 국가별 상세 리포트", "emoji": True}}])
            noteworthy_reports_found = True

        details = COUNTRY_DETAILS.get(report['code'], {})
        name_ko = details.get('name_ko', report['name'])
        flag = details.get('flag', '🌐')
        
        country_blocks = [
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{flag} {name_ko} ({report['code']})*"}}
        ]
        
        for title, content in report['data'].items():
            if is_content_noteworthy(content):
                country_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}:*\n{content}"}})
        
        if len(country_blocks) > 2:
            send_to_slack(country_blocks)

if not noteworthy_reports_found:
    send_to_slack([{"type": "section", "text": {"type": "mrkdwn", "text": "✅ 모든 모니터링 국가에서 특이사항이 발견되지 않았습니다."}}])

print("\n✅ 모든 작업 완료!")