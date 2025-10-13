import os
import requests
import json
from datetime import date, timedelta, datetime, timezone
import google.generativeai as genai

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
IGNORE_PHRASES = [ "관련 뉴스 없음", "주요 지진 없음", "예정된 공휴일 없음", "보고된 주요 인터넷 이벤트 없음", "보고된 트래픽 이상 징후 없음" ]

# (C) Gemini API를 이용한 자동 번역 함수
def translate_text_with_gemini(text_to_translate, context="weather alert"):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return f"{text_to_translate} (번역 실패: API 키 없음)"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        if context == "news":
            prompt = f"""Translate the following news headline into Korean. Do not add any explanation, romanization, or markdown formatting. Input: '{text_to_translate}'"""
        else:
            prompt = f"""Translate the following single weather alert term into a single, official Korean equivalent. Do not add any explanation, romanization, or markdown formatting. For example, if the input is "Thunderstorm gale", the output should be just "뇌우 강풍". Input: '{text_to_translate}'"""

        response = model.generate_content(prompt)
        return response.text.strip().replace("*", "")
    except Exception as e:
        if "429" in str(e): return f"(번역 한도 초과)"
        return f"{text_to_translate} (번역 에러)"

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
        return f"인터넷 뉴스 수집 중 에러: {e}"

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
    """규모 6.0 이상의 지진만 필터링하여 표시합니다."""
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
    except Exception as e:
        return f"뉴스 수집 중 에러 발생: {e}"

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
    except Exception as e:
        return f"대륙별 뉴스 수집 중 에러: {e}"

def get_summary_from_gemini(report_text):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return "* (요약/번역 기능 비활성화: Gemini API 키 없음)"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""You are an analyst summarizing overnight global events for a mobile game manager. Based on the following raw report, please create a concise summary in Korean with a maximum of 3 bullet points.
        Please use a hyphen (-) for bullet points, not an asterisk (*).
        Focus only on the most critical issues that could impact game traffic. If there are no significant events, simply state that.

        Raw Report: --- {report_text} --- Summary:"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        if "429" in str(e): return "* (요약 생성 실패: API 일일 사용량을 초과했습니다.)"
        return f"* (요약 생성 중 에러 발생: {e})"

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
    if "에러" in clean_content:
        return False
    return True

# (H) 메인 실행 부분
print("리포트 생성을 시작합니다...")
all_reports_data = []
for code, name in CITIES.items():
    print(f"--- {name} ({code}) 데이터 수집 중 ---")
    data = get_report_data(code, name)
    all_reports_data.append({'code': code, 'name': name, 'data': data