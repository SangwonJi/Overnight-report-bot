import os
import requests
import json
from datetime import datetime

def get_report_content():
    """
    리포트 내용을 생성하는 함수입니다.
    이곳에 나중에 실제 데이터 수집 로직(웹 스크래핑, API 호출 등)을 추가할 수 있습니다.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # GitHub Actions에서 실행될 때 보일 메시지입니다.
    report = f"""
*🤖 GitHub Actions 자동 리포트 ({today_str})*

이 메시지는 GitHub 서버에서 자동으로 생성되었습니다.
- **상태:** 정상 실행 완료
- **다음 실행:** 내일 오전 9시 (예정)

---
*간밤 주요 이슈 (예시):*
> *1. 이집트 🇪🇬*
> - *이슈:* 현지시간 23:00부터 Vodafone Egypt 인터넷 접속 불안정 관련 소셜 미디어 게시물 급증.
> - *출처:* X(Twitter) API, Downdetector

> *2. 인도네시아 🇮🇩*
> - *이슈:* 자카르타 인근 규모 5.4 지진 발생 (현지시간 02:30).
> - *출처:* Google News API
    """
    return report

def send_to_slack(message):
    """
    GitHub Secrets에 저장된 Webhook URL을 이용해 Slack으로 메시지를 전송합니다.
    """
    # GitHub Actions의 'Secrets'에서 설정한 SLACK_WEBHOOK_URL 값을 가져옵니다.
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    # Secret이 설정되지 않았을 경우를 대비한 에러 처리
    if not webhook_url:
        print("🚫 에러: GitHub Secrets에 SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        # 실패를 알리기 위해 0이 아닌 값으로 프로세스를 종료합니다.
        exit(1)

    payload = {"text": message}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        # HTTP 에러가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()
        print("✅ Slack 메시지 전송 성공!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Slack 메시지 전송 실패: {e}")
        # 실패를 알리기 위해 0이 아닌 값으로 프로세스를 종료합니다.
        exit(1)

if __name__ == "__main__":
    report_message = get_report_content()
    send_to_slack(report_message)