# -----------------------------------------------------------------
# [새로 추가] 특이사항을 판단하는 헬퍼 함수
# -----------------------------------------------------------------
def is_content_noteworthy(content):
    """주어진 내용이 특이사항에 해당하는지 판단합니다."""
    if not content or not content.strip():
        return False
    
    clean_content = content.strip()
    
    # 무시할 기본 메시지 목록에 포함되는지 확인
    if clean_content in IGNORE_PHRASES:
        return False
    
    # '특보 없음' 문구가 포함되는지 확인
    if "특보 없음" in clean_content:
        return False
        
    # 위 모든 검사를 통과하면 특이사항으로 간주
    return True

# -----------------------------------------------------------------
# (G) 메인 실행 부분 (특이사항 필터링 로직 개선됨)
# -----------------------------------------------------------------
print("리포트 생성을 시작합니다...")
all_reports_data = []
for code, name in CITIES.items():
    print(f"--- {name} ({code}) 데이터 수집 중 ---")
    data = get_report_data(code, name)
    all_reports_data.append({'code': code, 'name': name, 'data': data})

# 요약을 위한 전체 텍스트 생성
full_report_text_for_summary = ""
for report in all_reports_data:
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

# Slack으로 요약 리포트 전송
today_str = datetime.now().strftime("%Y-%m-%d")
summary_blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": f"🚨 글로벌 종합 모니터링 리포트 ({today_str})", "emoji": True}},
    {"type": "section", "text": {"type": "mrkdwn", "text": f"*주요 이슈 요약:*\n{summary}"}}
]
print("\nSlack으로 요약 리포트를 전송합니다...")
send_to_slack(summary_blocks)

# 대륙별 뉴스 리포트 생성 및 전송
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

# [수정됨] 특이사항이 있는 국가만 상세 리포트 전송
print("\n특이사항 국가 상세 리포트를 전송합니다...")
noteworthy_reports_found = False
for report in all_reports_data:
    # 헬퍼 함수를 사용하여 특이사항이 있는지 여부를 판단
    has_noteworthy_issue = any(is_content_noteworthy(content) for content in report['data'].values())
    
    if has_noteworthy_issue:
        # 상세 리포트 섹션 헤더를 한 번만 보냄
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
            if content and content.strip():
                country_blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{title}:*\n{content}"}})
        
        if len(country_blocks) > 2:
            send_to_slack(country_blocks)

# 모든 국가에 특이사항이 없었을 경우, 별도 메시지 전송
if not noteworthy_reports_found:
    send_to_slack([{"type": "section", "text": {"type": "mrkdwn", "text": "✅ 모든 국가에서 특이사항이 발견되지 않았습니다."}}])

print("\n✅ 모든 작업 완료!")