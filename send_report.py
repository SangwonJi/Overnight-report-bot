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

# (A) 모니터링할 국가 및 도시 목록
CITIES = { 'IQ': 'Iraq', 'TR': 'Turkey', 'PK': 'Pakistan', 'EG': 'Egypt', 'RU': 'Russia', 'ID': 'Indonesia', 'SA': 'Saudi Arabia', 'UZ': 'Uzbekistan', 'US': 'United States', 'VN': 'Vietnam', 'DE': 'Germany', 'HK': 'Hong Kong' }
COUNTRY_DETAILS = { 'IQ': {'name_ko': '이라크', 'flag': '🇮🇶'}, 'TR': {'name_ko': '터키', 'flag': '🇹🇷'}, 'PK': {'name_ko': '파키스탄', 'flag': '🇵🇰'}, 'EG': {'name_ko': '이집트', 'flag': '🇪🇬'}, 'RU': {'name_ko': '러시아', 'flag': '🇷🇺'}, 'ID': {'name_ko': '인도네시아', 'flag': '🇮🇩'}, 'SA': {'name_ko': '사우디아라비아', 'flag': '🇸🇦'}, 'UZ': {'name_ko': '우즈베키스탄', 'flag': '🇺🇿'}, 'US': {'name_ko': '미국', 'flag': '🇺🇸'}, 'VN': {'name_ko': '베트남', 'flag': '🇻🇳'}, 'DE': {'name_ko': '독일', 'flag': '🇩🇪'}, 'HK': {'name_ko': '홍콩', 'flag': '🇭🇰'} }
KEYWORDS = [ "protest", "accident", "incident", "disaster", "unrest", "riot", "war", "conflict", "attack", "military", "clash", "rebellion", "uprising", "internet outage", "power outage", "flood", "earthquake" ]

# (B) Gemini API를 이용한 자동 번역 함수
def translate_text_with_gemini(text_to_translate):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return f"{text_to_translate} (번역 실패: API 키 없음)"
        genai.configure(api_key=api_key)
        # [수정됨] 최신 모델 이름으로 변경
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"Translate the following weather alert text into Korean. Be concise.: '{text_to_translate}'"
        response = model.generate_content(prompt)
        return response.text.strip().replace("*", "")
    except Exception as e:
        return f"{text_to_translate} (번역 에러: {e})"

# (C) 데이터 수집 함수들
def check_cloudflare_outages(country_code):
    try:
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        # [수정됨] limit 파라미터 제거
        url = f"https://api.cloudflare.com/client/v4/radar/events?dateStart={yesterday_str}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response_json = response.json()
        if not response_json.get('success'):
            return "조회 실패 (API 에러)"
        events = response_json.get('result', {}).get('events', [])
        event_info = ""
        for event in events:
            if country_code.upper() in event.get('locations_alpha2', []):
                event_date = event.get('startTime', 'N/A').split("T")[0]
                description = event.get('description', 'No description')
                event_info += f"🌐 *이벤트 감지:* {description} ({event_date})\n"
        return event_info if event_info else "보고된 주요 인터넷 이벤트 없음"
    except requests.exceptions.RequestException as e:
        return f"조회 중 네트워크 에러 발생: {e}"
    except Exception as e:
        return f"조회 중 에러 발생: {e}"

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
        unique_alerts = {alert.get('event') for alert in alerts} # 중복 제거
        for event in unique_alerts:
            translated_event = translate_text_with_gemini(event)
            alert_info += f"🚨 *'{translated_event}' 특보 발령!*\n"
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
            place = eq['properties']['place']
            if country_name.lower() in place.lower() or f" {country_code.upper()}" in place.upper():
                mag = eq['properties']['mag']
                time_utc = datetime.fromtimestamp(eq['properties']['time'] / 1000, tz=timezone.utc)
                time_kst = time_utc.astimezone(kst).strftime('%Y-%m-%d %H:%M KST')
                earthquake_info += f"⚠️ *규모 {mag} ({time_kst}):* {place}\n"
        return earthquake_info if earthquake_info else "주요 지진 없음"
    except Exception: return "조회 에러"

def get_comprehensive_news(country_code, country_name):
    try:
        api_key = os.environ.get("GNEWS_API_KEY")
        if not api_key: return "(API 키 없음)"
        query_keywords = " OR ".join(f'"{k}"' for k in KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country={country_code.lower()}&max=3&token={api_key}"
        response = requests.get(url, timeout=10).json()
        articles = response.get('articles', [])
        if not articles: return "관련 뉴스 없음"
        news_info = ""
        for article in articles:
            news_info += f"• {article.get('title', '')}\n"
        return news_info
    except Exception as e:
        return f"뉴스 수집 중 에러 발생: {e}"

# (D) Gemini API를 이용한 요약 함수
def get_summary_from_gemini(report_text):
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return "* (요약/번역 기능 비활성화: Gemini API 키 없음)"
        genai.configure(api_key=api_key)
        # [수정됨] 최신 모델 이름으로 변경
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""You are an analyst summarizing overnight global events for a mobile game manager. Based on the following raw report, please create a concise summary in Korean with a maximum of 3 bullet points. Focus only on the most critical issues that could impact game traffic. If there are no significant events, simply state that.
        Raw Report: --- {report_text} --- Summary:"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"* (요약 생성 중 에러 발생: {e})"

# (E) 보고서 데이터를 '딕셔너리'로 생성하는 함수
def get_report_data(country_code, country_name):
    report_data = {
        "인터넷 상태": check_cloudflare_outages(country_code),
        "날씨 특보": get_weather_info(country_code),
        "공휴일": check_for_holidays(country_code),
        "지진 (규모 4.5+)": check_for_earthquakes(country_code, country_name),
        "관련 뉴스 헤드라인": get_comprehensive_news(country_code, country_name)
    }
    return report_data

# (F) Slack Block Kit을 사용하여 메시지를 보내는 함수
def send_to_slack(message):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url: return False
    payload = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}]}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print(f"  --> 메시지 전송 성공!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 메시지 전송 실패: {e}")
        return False

# (G) 메인 실행 부분
print("리포트 생성을 시작합니다...")
full_report_details = []
for code, name in CITIES.items():
    print(f"--- {name} ({code}) 데이터 수집 중 ---")
    data = get_report_data(code, name)
    details = COUNTRY_DETAILS.get(code, {})
    name_ko = details.get('name_ko', name)
    flag = details.get('flag', '🌐')
    country_section = [f"*{flag} {name_ko} ({code})*"]
    for title, content in data.items():
        if content: country_section.append(f"*{title}:*\n{content}")
    full_report_details.append("\n".join(country_section))

full_report_text = "\n\n---\n\n".join(full_report_details)
print("\nGemini API로 요약 생성 중...")
summary = get_summary_from_gemini(full_report_text)

today_str = datetime.now().strftime("%Y-%m-%d")
title = f"*🚨 글로벌 종합 모니터링 리포트 ({today_str})*"
summary_section = f"*주요 이슈 요약:*\n{summary}"
print("\nSlack으로 전송을 시작합니다...")
send_to_slack(f"{title}\n{summary_section}")
for detail_part in full_report_details:
    send_to_slack(f"---\n{detail_part}")
print("\n✅ 모든 작업 완료!")