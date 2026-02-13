import os
import requests
from dotenv import load_dotenv

load_dotenv()
SERVICE_KEY = os.getenv("DATA_GO_KR_KEY")

if not SERVICE_KEY:
    print("DATA_GO_KR_KEY가 .env에 없습니다.")
    exit()

print(f"API 키 로드 완료 (앞 10자: {SERVICE_KEY[:10]}...)\n")

common_params = {
    "serviceKey": SERVICE_KEY,
    "MobileOS": "ETC",
    "MobileApp": "TestApp",
    "_type": "json",
    "numOfRows": 3,
    "pageNo": 1,
}

# 가능한 Base URL + 오퍼레이션 조합을 모두 시도
base_urls = [
    "https://apis.data.go.kr/B551011/WellnessTursmService",
    "http://apis.data.go.kr/B551011/WellnessTursmService",
    "https://apis.data.go.kr/B551011/WellnessTursmService1",
    "http://apis.data.go.kr/B551011/WellnessTursmService1",
    "https://apis.data.go.kr/B551011/WellnessTursmService2",
    "http://apis.data.go.kr/B551011/WellnessTursmService2",
]

operations = [
    "/areaBasedList",
    "/areaBasedList1",
    "/areaBasedList2",
    "/searchKeyword",
    "/searchKeyword1",
    "/searchKeyword2",
]

print("=" * 70)
print("모든 Base URL + 오퍼레이션 조합 테스트")
print("=" * 70)

found = False
for base in base_urls:
    for op in operations:
        url = f"{base}{op}"
        params = {**common_params}
        if "searchKeyword" in op:
            params["keyword"] = "스파"
        try:
            resp = requests.get(url, params=params, timeout=10)
            status = resp.status_code
            body = resp.text[:150]

            if status == 200 and "resultCode" in body:
                print(f"\n  ✅ 성공! {url}")
                print(f"     Status: {status}")
                print(f"     응답: {body[:300]}")
                found = True
            elif status == 200:
                print(f"\n  ⚠️  200 but 의심: {url}")
                print(f"     응답: {body[:200]}")
            else:
                print(f"  ❌ {status} - {url}  ({body[:60]})")
        except Exception as e:
            print(f"  ❌ 에러 - {url}  ({e})")

if not found:
    print("\n" + "=" * 70)
    print("어떤 조합도 성공하지 못했습니다.")
    print("확인사항:")
    print("  1. 공공데이터포털에서 '한국관광공사_웰니스관광정보' API를")
    print("     별도로 활용신청 하셨는지 확인해주세요.")
    print("     https://www.data.go.kr/data/15144030/openapi.do")
    print("  2. 마이페이지 > 오픈API > 활용신청 현황에서")
    print("     웰니스관광정보가 '승인' 상태인지 확인해주세요.")
    print("  3. 인증키가 웰니스 API용으로 발급된 것인지 확인해주세요.")
    print("=" * 70)
else:
    print("\n\n=== 위에서 성공한 URL로 테스트 코드를 업데이트하세요! ===")
