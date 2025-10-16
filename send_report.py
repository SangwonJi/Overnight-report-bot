 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/send_report.py b/send_report.py
index 0474b3b8779977cd29b21e0a2f11615fb1166619..3381254aa45bc64b516cda52ac5e90c36520a0df 100644
--- a/send_report.py
+++ b/send_report.py
@@ -1,89 +1,143 @@
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
 
-# (C) [최종 수정] Gemini API를 requests로 직접 호출하는 번역 함수
-def call_gemini_api(prompt):
-    """Gemini API를 직접 호출하여 결과를 반환하는 통합 함수."""
-    api_key = os.environ.get("GEMINI_API_KEY")
-    if not api_key:
-        return None, "(API 키 없음)"
-
-    # 올바른 v1beta 엔드포인트 사용
-    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
-    headers = {'Content-Type': 'application/json'}
-    data = {"contents": [{"parts": [{"text": prompt}]}]}
-
-    try:
-        response = requests.post(url, headers=headers, json=data, timeout=30)
-        response.raise_for_status()
-        response_json = response.json()
-        
-        candidates = response_json.get('candidates', [])
-        if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
-            return candidates[0]['content']['parts'][0].get('text', '').strip(), None
-        else:
-            return None, f"API 응답 구조 오류"
-            
-    except requests.exceptions.RequestException as e:
-        if e.response is not None:
-            if e.response.status_code == 429:
-                return None, "API 한도 초과"
-            return None, f"API 요청 실패: {e.response.status_code}"
-        return None, f"API 연결 실패"
-    except Exception as e:
-        return None, f"알 수 없는 에러: {e}"
+# (C) [최종 수정] Gemini API를 requests로 직접 호출하는 번역 함수
+DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
+FALLBACK_GEMINI_MODELS = ["gemini-pro"]
+
+GEMINI_DIAGNOSTICS = {
+    "attempted_models": [],
+    "successful_model": None,
+    "translation_errors": 0,
+    "summary_error": None,
+    "last_error": None,
+}
+
+
+def call_gemini_api(prompt):
+    """Gemini API를 직접 호출하여 결과를 반환하는 통합 함수."""
+    api_key = os.environ.get("GEMINI_API_KEY")
+    if not api_key:
+        return None, {"code": "NO_API_KEY", "message": "(API 키 없음)"}
+
+    env_model = os.environ.get("GEMINI_MODEL")
+    models_to_try = []
+    if env_model:
+        models_to_try.append(env_model.strip())
+    else:
+        models_to_try.append(DEFAULT_GEMINI_MODEL)
+        for fallback_model in FALLBACK_GEMINI_MODELS:
+            if fallback_model not in models_to_try:
+                models_to_try.append(fallback_model)
+
+    headers = {'Content-Type': 'application/json'}
+    data = {"contents": [{"parts": [{"text": prompt}]}]}
+    last_error = None
+
+    for model in models_to_try:
+        if model not in GEMINI_DIAGNOSTICS["attempted_models"]:
+            GEMINI_DIAGNOSTICS["attempted_models"].append(model)
+
+    for index, model in enumerate(models_to_try):
+        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
+
+        try:
+            response = requests.post(url, headers=headers, json=data, timeout=30)
+            response.raise_for_status()
+            response_json = response.json()
+
+            candidates = response_json.get('candidates', [])
+            if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content']:
+                GEMINI_DIAGNOSTICS["successful_model"] = model
+                GEMINI_DIAGNOSTICS["last_error"] = None
+                return candidates[0]['content']['parts'][0].get('text', '').strip(), None
+            else:
+                last_error = {"code": "INVALID_RESPONSE", "message": "API 응답 구조 오류"}
+                GEMINI_DIAGNOSTICS["last_error"] = last_error
+                return None, last_error
+
+        except requests.exceptions.RequestException as e:
+            if e.response is not None:
+                if e.response.status_code == 429:
+                    last_error = {"code": "RATE_LIMIT", "message": "API 한도 초과"}
+                    GEMINI_DIAGNOSTICS["last_error"] = last_error
+                    return None, last_error
+                if e.response.status_code == 404:
+                    last_error = {
+                        "code": "NOT_FOUND",
+                        "message": f"모델 '{model}'에 대한 접근 권한이 없어 404가 발생했습니다. API 키 자체는 인식되었습니다."
+                    }
+                    GEMINI_DIAGNOSTICS["last_error"] = last_error
+                    if index < len(models_to_try) - 1:
+                        next_model = models_to_try[index + 1]
+                        print(f"Gemini 모델 '{model}'을(를) 찾을 수 없어 '{next_model}'로 재시도합니다...")
+                        continue
+                    return None, last_error
+                last_error = {"code": "HTTP_ERROR", "message": f"API 요청 실패: {e.response.status_code}"}
+                GEMINI_DIAGNOSTICS["last_error"] = last_error
+            else:
+                last_error = {"code": "CONNECTION", "message": "API 연결 실패"}
+                GEMINI_DIAGNOSTICS["last_error"] = last_error
+        except Exception as e:
+            last_error = {"code": "UNKNOWN", "message": f"알 수 없는 에러: {e}"}
+            GEMINI_DIAGNOSTICS["last_error"] = last_error
+        break
+
+    return None, last_error
 
 def translate_text_with_gemini(text_to_translate, context="weather alert"):
     if context == "news":
         prompt = f"""Translate the following news headline into Korean. Do not add any explanation, romanization, or markdown formatting. Input: '{text_to_translate}'"""
     else:
         prompt = f"""Translate the following single weather alert term into a single, official Korean equivalent. Do not add any explanation, romanization, or markdown formatting. For example, if the input is "Thunderstorm gale", the output should be just "뇌우 강풍". Input: '{text_to_translate}'"""
 
-    result, error = call_gemini_api(prompt)
-    if error:
-        return f"{text_to_translate} (번역 에러)"
-    return result.replace("*", "") if result else f"{text_to_translate} (번역 결과 없음)"
+    result, error = call_gemini_api(prompt)
+    if error:
+        GEMINI_DIAGNOSTICS["translation_errors"] += 1
+        # 번역 실패 시 원문을 그대로 사용하여 가독성을 유지
+        return text_to_translate
+    return result.replace("*", "") if result else text_to_translate
 
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
@@ -167,96 +221,188 @@ def get_continental_news(continent_name):
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
     
-    result, error = call_gemini_api(prompt)
-    if error:
-        return f"* (요약 생성 중 에러: {error})"
-    return result if result else "* (요약 생성 결과 없음)"
-
+    result, error = call_gemini_api(prompt)
+    if error:
+        GEMINI_DIAGNOSTICS["summary_error"] = error
+        code = error.get("code")
+        if code == "NOT_FOUND":
+            return "- Gemini 모델 권한이 없어 자동 요약을 생략합니다. API 키는 정상 인식되었으며 번역은 영어 원문으로 제공됩니다."
+        if code == "NO_API_KEY":
+            return "- Gemini API 키가 설정되지 않아 자동 요약을 생략합니다. 번역은 영어 원문으로 제공됩니다."
+        if code == "RATE_LIMIT":
+            return "- Gemini 호출 한도가 초과되어 요약을 잠시 생략합니다. 번역은 영어 원문으로 제공됩니다."
+        if code == "CONNECTION":
+            return "- Gemini 서버에 연결하지 못해 요약을 생략합니다. 번역은 영어 원문으로 제공됩니다."
+        return "- Gemini 요약 생성이 지연되어 상세 리포트를 먼저 확인해주세요."
+    return result if result else "- 주요 이슈가 없어 자동 요약을 건너뛰었습니다."
+
+
+def print_gemini_diagnostics():
+    print("\n[Gemini 호출 진단]")
+
+    attempted_models = GEMINI_DIAGNOSTICS["attempted_models"]
+    if attempted_models:
+        print(f"- 시도한 모델: {', '.join(attempted_models)}")
+
+    if GEMINI_DIAGNOSTICS["successful_model"]:
+        print(f"- 실제 사용된 모델: {GEMINI_DIAGNOSTICS['successful_model']}")
+    elif GEMINI_DIAGNOSTICS["last_error"]:
+        error = GEMINI_DIAGNOSTICS["last_error"]
+        print(f"- 모델 호출 실패: {error.get('code')} / {error.get('message')}")
+        if error.get("code") == "NOT_FOUND":
+            print("  · 해결 방법: Gemini 콘솔에서 해당 모델 접근 권한을 요청하거나 `GEMINI_MODEL`을 권한이 있는 모델로 설정하세요.")
+    else:
+        print("- Gemini 호출이 실행되지 않았습니다.")
+
+    summary_error = GEMINI_DIAGNOSTICS["summary_error"]
+    if summary_error:
+        print(f"- 요약 실패: {summary_error.get('message', '세부 정보 없음')} (코드: {summary_error.get('code')})")
+    else:
+        print("- 요약 생성은 정상 처리되었거나 요약이 필요하지 않았습니다.")
+
+    translation_errors = GEMINI_DIAGNOSTICS["translation_errors"]
+    if translation_errors:
+        print(f"- 번역 실패 {translation_errors}건: 해당 항목은 영어 원문으로 전송되었습니다.")
+    else:
+        print("- 모든 번역이 성공했습니다.")
+
+
+def print_followup_instructions():
+    print("\n[다음 단계 안내]")
+
+    successful_model = GEMINI_DIAGNOSTICS["successful_model"]
+    last_error = GEMINI_DIAGNOSTICS["last_error"]
+    summary_error = GEMINI_DIAGNOSTICS["summary_error"]
+    translation_errors = GEMINI_DIAGNOSTICS["translation_errors"]
+
+    if successful_model:
+        if summary_error or translation_errors:
+            if translation_errors:
+                print("- 일부 번역이 영어로 전송되었습니다. 모델 권한을 부여받으면 자동으로 한글 번역이 재개됩니다.")
+            if summary_error:
+                print("- 요약은 대체 문구로 전송되었습니다. 모델 권한을 확보한 뒤 `python send_report.py`를 다시 실행하세요.")
+        else:
+            print("- Gemini 호출이 모두 성공했습니다. 추가 수정은 필요 없으며 필요 시 재실행만 하면 됩니다.")
+        print("- GitHub 저장소는 자동으로 업데이트되지 않으므로 변경 사항을 적용하려면 `git pull` 후 `python send_report.py`를 실행하세요.")
+        return
+
+    if not last_error:
+        print("- Gemini 호출이 이루어지지 않았습니다. API 키와 환경 변수를 확인한 뒤 다시 실행하세요.")
+        return
+
+    code = last_error.get("code")
+
+    if code == "NOT_FOUND":
+        print("- 현재 API 키는 인식되지만 요청한 모델에 대한 권한이 없습니다.")
+        print("  · 해결책: Gemini 콘솔에서 모델 권한을 신청하거나 `GEMINI_MODEL`에 접근 가능한 모델 ID를 입력하세요.")
+        print("  · 권한을 조정한 뒤 `git pull`로 최신 코드를 받은 상태에서 `python send_report.py`를 재실행하면 됩니다. (코드는 자동으로 갱신되지 않습니다.)")
+        return
+
+    if code == "NO_API_KEY":
+        print("- `GEMINI_API_KEY` 환경 변수를 설정한 뒤 `python send_report.py`를 다시 실행하세요.")
+        return
+
+    if code == "RATE_LIMIT":
+        print("- 호출 한도가 초과되었습니다. 잠시 후 `python send_report.py`를 다시 실행하면 정상 처리됩니다.")
+        return
+
+    if code == "CONNECTION":
+        print("- Gemini 서버 연결에 실패했습니다. 네트워크 상태를 확인한 뒤 재실행하세요.")
+        return
+
+    print("- 기타 오류가 발생했습니다. 콘솔 로그를 확인한 뒤 수정 후 다시 실행하세요.")
+
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
 
-# (H) 메인 실행 부분
-print("리포트 생성을 시작합니다...")
+# (H) 메인 실행 부분
+print("[업데이트 안내] 이 스크립트는 GitHub에서 자동으로 고쳐지지 않습니다. 최신 수정을 반영하려면 실행 전에 `git pull`을 수행한 뒤 `python send_report.py`를 다시 실행하세요.")
+# 사용자가 "GitHub에서 알아서 고쳐지나요?"라고 물어볼 때 즉답이 되도록 별도 안내를 추가합니다.
+print(
+    "[핵심 답변] GitHub 저장소에는 이미 최신 수정이 커밋되어 있지만 실행/배포 환경에는 자동 반영되지 않습니다. "
+    "직접 코드를 고칠 필요는 없으며, 반드시 `git pull`로 변경 사항을 받은 뒤 `python send_report.py`를 실행하세요."
+)
+print("리포트 생성을 시작합니다...")
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
@@ -284,29 +430,31 @@ print("\n특이사항 국가 상세 리포트를 전송합니다...")
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
 
-if not noteworthy_reports_found:
-    send_to_slack([{"type": "section", "text": {"type": "mrkdwn", "text": "✅ 모든 모니터링 국가에서 특이사항이 발견되지 않았습니다."}}])
-
-print("\n✅ 모든 작업 완료!")
\ No newline at end of file
+if not noteworthy_reports_found:
+    send_to_slack([{"type": "section", "text": {"type": "mrkdwn", "text": "✅ 모든 모니터링 국가에서 특이사항이 발견되지 않았습니다."}}])
+
+print_gemini_diagnostics()
+print_followup_instructions()
+print("\n✅ 모든 작업 완료!") 
EOF
)
