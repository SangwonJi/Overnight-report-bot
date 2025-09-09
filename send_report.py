import os
import requests
import json
from datetime import date, timedelta, datetime

# .env 파일을 읽어와 환경 변수로 설정합니다. (로컬 테스트용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # GitHub Actions 환경에서는 이 라이브러리가 없어도 괜찮습니다.

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

# -----------------------------------------------------------------
# (B) NewsAPI에서 검색할 사건사고 키워드 목록
# -----------------------------------------------------------------
KEYWORDS = [
    "protest", "accident", "incident", "disaster", "unrest", "riot", "war", 
    "conflict", "attack", "military", "clash", "rebellion", "uprising",
    "internet outage", "power outage", "flood", "earthquake"
]

# -----------------------------------------------------------------
# (C) 데이터 수집 함수들
# -----------------------------------------------------------------

def check_cloudflare_outages(country_code):
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
            alert_info += f"🚨 *'{event}' 특보 발령!*\n"
        return alert_info.strip()
    except Exception: return "조회 에러"

def check_for_holidays(country_code):
    try:
        api_key = os.environ.get("CALENDARIFIC_API_KEY")
        if not api_key: return "(API 키 없음)"
        today = date.today()
        url = f"https://calendarific.com/api/v2/holidays?api_key={api_key}&country={country_code}&year={today.year}&month={today.month}"
        response = requests.get(url).json()
        holidays = response.get('response', {}).get('holidays', [])
        tomorrow = today + timedelta(days=1)
        holiday_info = ""
        for h in holidays:
            holiday_date = datetime.fromisoformat(h['date']['iso']).date()
            if holiday_date == today:
                holiday_info += f"🔔 *오늘! '{h['name']}'*\n"
            elif holiday_date == tomorrow:
                holiday_info += f"🔔 *내일! '{h['name']}'*\n"
        return holiday_info if holiday_info else "예정된 공휴일 없음"
    except Exception: return "조회 에러"

def check_for_earthquakes(country_code, country_name):
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        response = requests.get(url).json()
        features = response.get('features', [])
        earthquake_info = ""
        for eq in features:
            place = eq['properties']['place']
            if country_name.lower() in place.lower() or f" {country_code.upper()}" in place.upper():
                mag = eq['properties']['mag']
                earthquake_info += f"⚠️ *규모 {mag}:* {place}\n"
        return earthquake_info if earthquake_info else "주요 지진 없음"
    except Exception: return "조회 에러"

def get_comprehensive_news(country_code, country_name):
    try:
        api_key = os.environ.get("NEWSAPI_API_KEY")
        if not api_key: return "(API 키 없음)"
        query_keywords = " OR ".join(KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        url = f"https://newsapi.org/v2/everything?q={query}&from={yesterday}&language=en&sortBy=relevancy&pageSize=3&apiKey={api_key}"
        response = requests.get(url).json()
        if response.get("status") != "ok": return f"API 에러: {response.get('message')}"
        articles = response.get('articles', [])
        if not articles: return "관련 뉴스 없음"
        news_info = ""
        for article in articles:
            news_info += f"• {article.get('title', '')}\n"
        return news_info
    except Exception: return "조회 에러"

# -----------------------------------------------------------------
# (D) 보고서 데이터를 '딕셔너리'로 생성하는 함수
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
# (E) [수정됨] Slack Block Kit을 사용하여 메시지를 보내는 함수
# -----------------------------------------------------------------
def send_to_slack(country_code, country_name, report_data, is_first_message=False):
    """데이터 딕셔너리를 받아 Block Kit으로 변환 후 Slack 메시지를 전송합니다."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url: return False

    details = COUNTRY_DETAILS.get(country_code, {})
    name_ko = details.get('name_ko', country_name)
    flag = details.get('flag', '🌐')
    
    blocks = []
    
    # 첫 메시지에만 전체 리포트 제목 추가
    if is_first_message:
        today_str = datetime.now().strftime("%Y-%m-%d")
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": f"🚨 글로벌 종합 모니터링 리포트 ({today_str})", "emoji": True}})
        blocks.append({"type": "divider"})
    
    # 국가별 헤더 추가
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{flag} {name_ko} ({country_code})*"}})
    
    # [수정됨] 각 섹션을 별도의 블록으로 만들어 공백 추가
    for title, content in report_data.items():
        if content and not content.startswith("(API 키 없음)"): # 내용이 있는 경우에만 블록 추가
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}:*\n{content}"
                }
            })

    # 마지막에 구분선 추가
    blocks.append({"type": "divider"})

    payload = {"blocks": blocks}
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print(f"  --> {country_name} 메시지 전송 성공!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ {country_name} 메시지 전송 실패: {e}")
        return False

# -----------------------------------------------------------------
# (F) 메인 실행 부분
# -----------------------------------------------------------------
print("리포트 생성을 시작합니다...")

is_first = True
for code, name in CITIES.items():
    print(f"\n--- {name} ({code}) 데이터 수집 및 전송 ---")
    
    data = get_report_data(code, name)
    send_to_slack(code, name, data, is_first_message=is_first)
    is_first = False

print("\n✅ 모든 국가 리포트 전송 완료!")