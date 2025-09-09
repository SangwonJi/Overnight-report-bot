import os
import requests
import json
from datetime import date, timedelta, datetime

# .env 파일을 읽어와 환경 변수로 설정합니다. (로컬 테스트용)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("dotenv 라이브러리가 설치되지 않았습니다. 로컬 테스트 시에는 pip install python-dotenv를 실행하세요.")

# -----------------------------------------------------------------
# (A) 모니터링할 국가 및 도시 목록
# -----------------------------------------------------------------
CITIES = {
    'IQ': 'Iraq', 'TR': 'Turkey', 'PK': 'Pakistan', 'EG': 'Egypt', 'RU': 'Russia', 
    'ID': 'Indonesia', 'SA': 'Saudi Arabia', 'UZ': 'Uzbekistan', 'US': 'United States',
    'VN': 'Vietnam', 'DE': 'Germany', 'HK': 'Hong Kong'
}

# [새로 추가됨] 국가별 상세 정보 (한글 이름, 국기)
COUNTRY_DETAILS = {
    'IQ': {'name_ko': '이라크', 'flag': '🇮🇶'},
    'TR': {'name_ko': '터키', 'flag': '🇹🇷'},
    'PK': {'name_ko': '파키스탄', 'flag': '🇵🇰'},
    'EG': {'name_ko': '이집트', 'flag': '🇪🇬'},
    'RU': {'name_ko': '러시아', 'flag': '🇷🇺'},
    'ID': {'name_ko': '인도네시아', 'flag': '🇮🇩'},
    'SA': {'name_ko': '사우디아라비아', 'flag': '🇸🇦'},
    'UZ': {'name_ko': '우즈베키스탄', 'flag': '🇺🇿'},
    'US': {'name_ko': '미국', 'flag': '🇺🇸'},
    'VN': {'name_ko': '베트남', 'flag': '🇻🇳'},
    'DE': {'name_ko': '독일', 'flag': '🇩🇪'},
    'HK': {'name_ko': '홍콩', 'flag': '🇭🇰'}
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
    """Cloudflare Radar API로 인터넷 이상 징후를 확인합니다."""
    try:
        url = "https://api.cloudflare.com/client/v4/radar/annotations/outages?format=json&limit=20"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers).json()
        if not response.get('success'): return "  - 인터넷 상태 정보 조회 실패 (API 에러)"

        outages = response.get('result', {}).get('annotations', [])
        outage_info = ""
        for outage in outages:
            if outage.get('scope', {}).get('alpha2') == country_code.upper():
                start_date = outage.get('startTime', 'N/A').split("T")[0]
                description = outage.get('description', 'No description')
                outage_info += f"  - 🌐 *인터넷 이상 감지:* {description} (시작일: {start_date})\n"
        return outage_info if outage_info else "  - 최근 72시간 내 보고된 인터넷 이상 징후 없음."
    except Exception as e:
        return f"  - 인터넷 상태 조회 중 에러 발생: {e}"

def get_weather_info(country_code):
    """[수정됨] WeatherAPI.com API로 날씨 특보만 확인합니다."""
    try:
        api_key = os.environ.get("WEATHERAPI_API_KEY")
        if not api_key: return "  - (날씨 API 키 없음)"
        city = CITIES.get(country_code)
        if not city: return "  - (도시 정보 없음)"
        
        # [수정됨] aqi=yes 부분을 URL에서 제거
        url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={city}&days=1&aqi=no&alerts=yes"
        response = requests.get(url).json()

        alerts = response.get('alerts', {}).get('alert', [])
        if not alerts:
            return f"  - {city} 기준, 현재 발령된 기상 특보 없음."
        
        alert_info = ""
        for alert in alerts:
            event = alert.get('event', '기상 특보')
            alert_info += f"  - 🚨 *{city}에 '{event}' 특보 발령!*\n"
        return alert_info

    except Exception as e:
        return f"  - 날씨 정보 조회 에러: {e}"

def check_for_holidays(country_code):
    """Calendarific API로 오늘 또는 내일의 공휴일을 확인합니다."""
    try:
        api_key = os.environ.get("CALENDARIFIC_API_KEY")
        if not api_key: return "  - (공휴일 API 키 없음)"
        today = date.today()
        url = f"https://calendarific.com/api/v2/holidays?api_key={api_key}&country={country_code}&year={today.year}&month={today.month}"
        response = requests.get(url).json()
        holidays = response.get('response', {}).get('holidays', [])
        tomorrow = today + timedelta(days=1)
        holiday_info = ""
        for h in holidays:
            holiday_date = datetime.fromisoformat(h['date']['iso']).date()
            if holiday_date == today:
                holiday_info += f"  - 🔔 *오늘! '{h['name']}'* 공휴일입니다.\n"
            elif holiday_date == tomorrow:
                holiday_info += f"  - 🔔 *내일! '{h['name']}'* 공휴일입니다.\n"
        return holiday_info if holiday_info else "  - 예정된 공휴일 없음."
    except Exception as e:
        return f"  - 공휴일 정보 조회 에러: {e}"

def check_for_earthquakes(country_code, country_name):
    """USGS API로 지난 24시간 내 발생한 주요 지진을 확인합니다."""
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        response = requests.get(url).json()
        features = response.get('features', [])
        earthquake_info = ""
        for eq in features:
            place = eq['properties']['place']
            if country_name.lower() in place.lower() or f" {country_code.upper()}" in place.upper():
                mag = eq['properties']['mag']
                earthquake_info += f"  - ⚠️ *규모 {mag} 지진 발생:* {place}\n"
        return earthquake_info if earthquake_info else "  - 주요 지진 없음."
    except Exception as e:
        return f"  - 지진 정보 조회 에러: {e}"

def get_comprehensive_news(country_code, country_name):
    """NewsAPI의 'everything' 엔드포인트를 사용하여 뉴스를 검색합니다."""
    try:
        api_key = os.environ.get("NEWSAPI_API_KEY")
        if not api_key: return "  - (뉴스 API 키 없음)"
        
        query_keywords = " OR ".join(KEYWORDS)
        query = f'"{country_name}" AND ({query_keywords})'
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        
        url = (f"https://newsapi.org/v2/everything?"
               f"q={query}"
               f"&from={yesterday}"
               f"&language=en"
               f"&sortBy=relevancy"
               f"&pageSize=3"
               f"&apiKey={api_key}")
        
        response = requests.get(url).json()
        
        if response.get("status") != "ok": return f"  - 뉴스 API 에러: {response.get('message')}"
        
        articles = response.get('articles', [])
        if not articles: return "  - 관련된 주요 사건사고 뉴스가 없습니다."
        
        news_info = ""
        for article in articles:
            news_info += f"  - {article.get('title', '')}\n"
        return news_info
    except Exception as e:
        return f"  - 뉴스 수집 중 에러 발생: {e}"

# -----------------------------------------------------------------
# (D) 최종 보고서 조합 함수 (대기 질 정보 제거됨)
# -----------------------------------------------------------------
def get_report_content(country_code, country_name):
    """지정된 '한 국가'에 대한 종합 리포트를 생성합니다."""
    
    details = COUNTRY_DETAILS.get(country_code, {})
    name_ko = details.get('name_ko', country_name)
    flag = details.get('flag', '🌐')

    report_parts = [
        f"*{flag} {name_ko} ({country_code})*",
        "---",
    ]
    
    # [수정됨] 대기 질 정보(air_quality)를 받지 않음
    weather_alert = get_weather_info(country_code)
    
    report_parts.append(f"*- 인터넷 상태:*\n{check_cloudflare_outages(country_code)}")
    # [수정됨] 날씨 특보만 표시
    report_parts.append(f"*- 날씨 특보:*\n{weather_alert.strip()}")
    report_parts.append(f"*- 공휴일:*\n{check_for_holidays(country_code)}")
    report_parts.append(f"*- 지진 (규모 4.5+):*\n{check_for_earthquakes(country_code, country_name)}")
    report_parts.append(f"*- 관련 뉴스 헤드라인:*\n{get_comprehensive_news(country_code, country_name)}")
    
    return "\n".join(report_parts)

# -----------------------------------------------------------------
# (E) Slack 전송 함수
# -----------------------------------------------------------------
def send_to_slack(message, is_first_message=False):
    """Slack으로 단일 메시지를 전송합니다."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("🚫 에러: SLACK_WEBHOOK_URL Secret이 설정되지 않았습니다.")
        return False

    if is_first_message:
        today_str = datetime.now().strftime("%Y-%m-%d")
        title = f"*🚨 글로벌 종합 모니터링 리포트 ({today_str})*"
        message = f"{title}\n\n{message}"

    payload = {
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": message}}]
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        print(f"  - Status Code: {response.status_code}")
        print(f"  - Response Body: {response.text}")
        response.raise_for_status()
        print("  --> 메시지 전송 성공!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 메시지 전송 실패: {e}")
        return False

# -----------------------------------------------------------------
# (F) 메인 실행 부분
# -----------------------------------------------------------------
print("리포트 생성을 시작합니다...")

is_first = True
for code, name in CITIES.items():
    print(f"\n--- {name} ({code}) 리포트 생성 및 전송 ---")
    
    report_message = get_report_content(code, name)
    
    send_to_slack(report_message, is_first_message=is_first)
    is_first = False

print("\n✅ 모든 국가 리포트 전송 완료!")