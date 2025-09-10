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

# -----------------------------------------------------------------
# (A) 모니터링할 국가 및 도시 목록
# -----------------------------------------------------------------
CITIES = {
    'IQ': 'Iraq', 'TR': 'Turkey', 'PK': 'Pakistan', 'EG': 'Egypt', 'RU': 'Russia', 
    'ID': 'Indonesia', 'SA': 'Saudi Arabia', 'UZ': 'Uzbekistan', 'US': 'United States',
    'VN': 'Vietnam', 'DE': 'Germany', 'HK': 'Hong Kong'
}
COUNTRY_DETAILS = {
    'IQ': {'name_ko': '이라크', 'flag': '🇮🇶'}, 'TR': {'name_ko': '터키', 'flag': '🇹🇷'},
    'PK': {'name_ko': '파키스탄', 'flag': '🇵🇰'}, 'EG': {'name_ko': '이집트', 'flag': '🇪🇬'},
    'RU': {'name_ko': '러시아', 'flag': '🇷🇺'}, 'ID': {'name_ko': '인도네시아', 'flag': '🇮🇩'},
    'SA': {'name_ko': '사우디아라비아', 'flag': '🇸🇦'}, 'UZ': {'name_ko': '우즈베키스탄', 'flag': '🇺🇿'},
    'US': {'name_ko': '미국', 'flag': '🇺🇸'}, 'VN': {'name_ko': '베트남', 'flag': '🇻🇳'},
    'DE': {'name_ko': '독일', 'flag': '🇩🇪'}, 'HK': {'name_ko': '홍콩', 'flag': '🇭🇰'}
}
KEYWORDS = [
    "protest", "accident", "incident", "disaster", "unrest", "riot", "war", 
    "conflict", "attack", "military", "clash", "rebellion", "uprising",
    "internet outage", "power outage", "flood", "earthquake"
]

# -----------------------------------------------------------------
# (B) [새로 추가] Gemini API를 이용한 자동 번역 함수
# -----------------------------------------------------------------
def translate_text_with_gemini(text_to_translate):
    """Gemini API를 이용해 주어진 텍스트를 한국어로 번역합니다."""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return f"{text_to_translate} (번역 실패: API 키 없음)"
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"Translate the following text into Korean: '{text_to_translate}'"
        response = model.generate_content(prompt)
        
        return response.text.strip()
    except Exception:
        return f"{text_to_translate} (번역 중 에러 발생)"

# -----------------------------------------------------------------
# (C) 데이터 수집 함수들 (업그레이드됨)
# -----------------------------------------------------------------

def check_cloudflare_outages(country_code):
    # (이전과 동일)
    try:
        url = "https://api.cloudflare.com/client/v4/radar/annotations/outages?format=json&limit=20"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers).json()
        if not response.get('success'): return "조회 실패 (API 에러)"
        outages = response.get('result', {}).get('annotations', [])
        outage_info = ""
        for outage in outages:
            if outage.get('scope', {}).get('alpha2') == country_code.upper():
                start_date = outage.get('startTime', 'N/A').split("T")[0]
                description = outage.get('description', 'No description')
                outage_info += f"🌐 *이상 감지:* {description} ({start_date})\n"
        return outage_info if outage_info else "보고된 이상 징후 없음"
    except Exception: return "조회 중 에러 발생"

def get_weather_info(country_code):
    """[업그레이드됨] 날씨 특보를 확인하고, 외국어는 한국어로 번역합니다."""
    try:
        api_key = os.environ.get("WEATHERAPI_API_KEY")
        if not api_key: return "(API 키 없음)"
        city = CITIES.get(country_code)
        if not city: return "(도시 정보 없음)"
        
        url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={city}&days=1&aqi=no&alerts=yes"
        response = requests.get(url).json()
        alerts = response.get('alerts', {}).get('alert', [])

        if not alerts: return f"{city} 기준 특보 없음"
        
        alert_info = ""
        for alert in alerts:
            event = alert.get('event', '기상 특보')
            # 영어 알파벳이 포함되어 있는지 확인하여 외국어 여부 판단 (간단한 방식)
            is_foreign = any(c.isalpha() for c in event)
            if is_foreign:
                translated_event = translate_text_with_gemini(event)
                alert_info += f"🚨 *'{translated_event}' 특보 발령!*\n"
            else: # 한글이나 기타 비-알파벳 문자는 그대로 표시
                alert_info += f"🚨 *'{event}' 특보 발령!*\n"
        return alert_info.strip()

    except Exception: return "조회 에러"

def check_for_holidays(country_code):
    """[업그레이드됨] 'National holiday' 같은 실제 공휴일만 필터링합니다."""
    try:
        api_key = os.environ.get("CALENDARIFIC_API_KEY")
        if not api_key: return "(API 키 없음)"
        
        # 'National holiday', 'Public holiday' 등 실제 쉬는 날을 나타내는 타입 목록
        VALID_HOLIDAY_TYPES = ["National holiday", "Public holiday", "Bank holiday"]

        today = date.today()
        url = f"https://calendarific.com/api/v2/holidays?api_key={api_key}&country={country_code}&year={today.year}" # 1년치 데이터를 한번에
        response = requests.get(url).json()
        holidays = response.get('response', {}).get('holidays', [])
        tomorrow = today + timedelta(days=1)
        holiday_info = ""

        for h in holidays:
            # 실제 공휴일 타입인지 확인
            if any(valid_type in h['type'] for valid_type in VALID_HOLIDAY_TYPES):
                holiday_date = datetime.fromisoformat(h['date']['iso']).date()
                if holiday_date == today:
                    holiday_info += f"🌍 *오늘! '{h['name']}'* (공휴일)\n"
                elif holiday_date == tomorrow:
                    holiday_info += f"🌍 *내일! '{h['name']}'* (공휴일)\n"
        
        return holiday_info if holiday_info else "예정된 공휴일 없음"
    except Exception: return "조회 에러"

def check_for_earthquakes(country_code, country_name):
    """[업그레이드됨] 지진 발생 시점을 한국 시간(KST)으로 표시합니다."""
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        response = requests.get(url).json()
        features = response.get('features', [])
        earthquake_info = ""
        
        # KST = UTC+9
        kst = timezone(timedelta(hours=9))

        for eq in features:
            place = eq['properties']['place']
            if country_name.lower() in place.lower() or f" {country_code.upper()}" in place.upper():
                mag = eq['properties']['mag']
                # 유닉스 타임스탬프(밀리초)를 datetime 객체로 변환 후 KST로 변경
                time_utc = datetime.fromtimestamp(eq['properties']['time'] / 1000, tz=timezone.utc)
                time_kst = time_utc.astimezone(kst).strftime('%Y-%m-%d %H:%M KST')
                earthquake_info += f"⚠️ *규모 {mag} ({time_kst}):* {place}\n"
        
        return earthquake_info if earthquake_info else "주요 지진 없음"
    except Exception: return "조회 에러"

def get_comprehensive_news(country_code, country_name):
    """GNews API를 사용하여 Google 뉴스 헤드라인을 검색합니다."""
    try:
        api_key = os.environ.get("GNEWS_API_KEY")
        if not api_key: return "(API 키 없음)"
        
        query_keywords = " OR ".join(f'"{k}"' for k in KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        
        url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country={country_code.lower()}&max=3&token={api_key}"
        
        response = requests.get(url).json()
        articles = response.get('articles', [])
        
        if not articles: return "관련 뉴스 없음"
        
        news_info = ""
        for article in articles:
            news_info += f"• {article.get('title', '')}\n"
        return news_info
    except Exception as e:
        return f"뉴스 수집 중 에러 발생: {e}"

# -----------------------------------------------------------------
# (D) Gemini API를 이용한 요약 함수
# -----------------------------------------------------------------
def get_summary_from_gemini(report_text):
    """Gemini API를 이용해 전체 리포트 내용을 핵심 요약합니다."""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key: return "* (요약 기능 비활성화: Gemini API 키 없음)"
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        prompt = f"""You are an analyst summarizing overnight global events for a mobile game manager. Based on the following raw report, please create a concise summary in Korean with a maximum of 3 bullet points. Focus only on the most critical issues that could impact game traffic. If there are no significant events, simply state that.

        Raw Report:
        ---
        {report_text}
        ---
        Summary:"""

        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"* (요약 생성 중 에러 발생: {e})"

# -----------------------------------------------------------------
# (E) 보고서 데이터를 '딕셔너리'로 생성하는 함수
# -----------------------------------------------------------------
def get_report_data(country_code, country_name):
    """지정된 '한 국가'에 대한 데이터를 수집하여 딕셔너리로 반환합니다."""
    report_data = {
        "인터넷 상태": check_cloudflare_outages(country_code),
        "날씨 특보": get_weather_info(country_code),
        "공휴일": check_for_holidays(country_code),
        "지진 (규모 4.5+)": check_for_earthquakes(country_code, country_name),
        "관련 뉴스 헤드라인": get_comprehensive_news(country_code, country_name)
    }
    return report_data

# -----------------------------------------------------------------
# (F) Slack Block Kit을 사용하여 메시지를 보내는 함수
# -----------------------------------------------------------------
def send_to_slack(message, is_first_message=False):
    """Slack으로 단일 메시지를 전송합니다."""
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

# -----------------------------------------------------------------
# (G) 메인 실행 부분
# -----------------------------------------------------------------
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
        if content:
            country_section.append(f"*{title}:*\n{content}")
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