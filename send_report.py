import os
import requests
import json
from datetime import date, timedelta, datetime

# -----------------------------------------------------------------
# (A) 모니터링할 국가 및 도시 목록
# -----------------------------------------------------------------
CITIES = {
    'IQ': 'Iraq', 'TR': 'Turkey', 'PK': 'Pakistan', 'EG': 'Egypt', 'RU': 'Russia', 
    'ID': 'Indonesia', 'SA': 'Saudi Arabia', 'UZ': 'Uzbekistan', 'US': 'United States',
    'VN': 'Vietnam', 'DE': 'Germany', 'HK': 'Hong Kong'
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
                outage_info += f"  - 🌐 **인터넷 이상 감지:** {description} (시작일: {start_date})\n"
        return outage_info if outage_info else "  - 최근 72시간 내 보고된 인터넷 이상 징후 없음."
    except Exception as e:
        return f"  - 인터넷 상태 조회 중 에러 발생: {e}"

def get_weather_info(country_code):
    """WeatherAPI.com API로 날씨 특보와 대기 질을 한 번에 확인합니다."""
    try:
        api_key = os.environ.get("WEATHERAPI_API_KEY")
        if not api_key: return "  - (날씨 API 키 없음)", ""
        city = CITIES.get(country_code)
        if not city: return "  - (도시 정보 없음)", ""
        url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={city}&days=1&aqi=yes&alerts=yes"
        response = requests.get(url).json()

        alerts = response.get('alerts', {}).get('alert', [])
        alert_info = ""
        if not alerts:
            alert_info = f"  - {city} 기준, 현재 발령된 기상 특보 없음."
        else:
            for alert in alerts:
                event = alert.get('event', '기상 특보')
                alert_info += f"  - 🚨 **{city}에 '{event}' 특보 발령!**\n"

        aqi_data = response.get('current', {}).get('air_quality', {})
        air_quality_info = "  - 대기 질 정보 없음."
        if aqi_data:
            us_epa_index = aqi_data.get('us-epa-index')
            aqi_status = {1: "좋음", 2: "보통", 3: "민감군 주의", 4: "나쁨", 5: "매우 나쁨", 6: "위험"}
            air_quality_info = f"  - 대기 질(AQI): {us_epa_index} ({aqi_status.get(us_epa_index, '알 수 없음')})"
        return alert_info, air_quality_info
    except Exception as e:
        error_message = f"  - 날씨/대기 질 조회 에러: {e}"
        return error_message, ""

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
                holiday_info += f"  - 🔔 **오늘! '{h['name']}'** 공휴일입니다.\n"
            elif holiday_date == tomorrow:
                holiday_info += f"  - 🔔 **내일! '{h['name']}'** 공휴일입니다.\n"
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
                earthquake_info += f"  - ⚠️ **규모 {mag} 지진 발생:** {place}\n"
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
# (D) 최종 보고서 조합 함수
# -----------------------------------------------------------------
def get_report_content():
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_parts = [f"## 🚨 글로벌 종합 모니터링 리포트 ({today_str})"]
    for code, name in CITIES.items():
        report_parts.append(f"\n---\n### > {name} ({code})")
        weather_alert, air_quality = get_weather_info(code)
        report_parts.append(f"**- 인터넷 상태:**\n{check_cloudflare_outages(code)}")
        report_parts.append(f"**- 날씨/대기 질:**\n{weather_alert.strip()}\n{air_quality}")
        report_parts.append(f"**- 공휴일:**\n{check_for_holidays(code)}")
        report_parts.append(f"**- 지진 (규모 4.5+):**\n{check_for_earthquakes(code, name)}")
        report_parts.append(f"**- 관련 뉴스 헤드라인:**\n{get_comprehensive_news(code, name)}")
    return "\n".join(report_parts)

# -----------------------------------------------------------------
# (E) Slack 전송 함수 (분할 전송 기능으로 업그레이드됨)
# -----------------------------------------------------------------
def send_to_slack(message):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("🚫 에러: SLACK_WEBHOOK_URL Secret이 설정되지 않았습니다.")
        exit(1)

    # Slack의 메시지 길이 제한 (4000자) 보다 약간 여유있게 3500자로 설정
    limit = 3500
    lines = message.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 < limit:
            current_chunk += line + "\n"
        else:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
    
    chunks.append(current_chunk)

    for i, chunk in enumerate(chunks):
        if not chunk.strip(): continue

        part_info = f" (Part {i+1}/{len(chunks)})"
        # 첫 번째 메시지에만 제목을 붙이고, 나머지는 이어지는 내용임을 표시
        if i > 0:
            chunk = f"...(이전 메시지에서 이어짐){part_info}\n\n" + chunk

        payload = {"text": chunk}
        headers = {'Content-Type': 'application/json'}
        
        try:
            print(f"--> {i+1}/{len(chunks)}번째 메시지 전송 중...")
            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            print(f"--> {i+1}번째 메시지 전송 성공!")
        except requests.exceptions.RequestException as e:
            print(f"❌ {i+1}번째 메시지 전송 실패: {e}")
            exit(1)
    
    print("✅ 모든 Slack 메시지 전송 완료!")

# -----------------------------------------------------------------
# (F) 메인 실행 부분
# -----------------------------------------------------------------
if __name__ == "__main__":
    report_message = get_report_content()
    print(report_message)
    # 로컬 테스트 시 아래 줄의 주석을 풀고 .env 파일에 키를 설정하여 테스트
    # send_to_slack(report_message)