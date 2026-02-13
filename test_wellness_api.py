import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()
SERVICE_KEY = os.getenv("DATA_GO_KR_KEY")

if not SERVICE_KEY:
    print("DATA_GO_KR_KEY가 .env에 없습니다.")
    exit()

print(f"API 키 로드 완료 (앞 10자: {SERVICE_KEY[:10]}...)")

BASE_URL = "http://apis.data.go.kr/B551011/WellnessTursmService"

common_params = {
    "serviceKey": SERVICE_KEY,
    "MobileOS": "ETC",
    "MobileApp": "TestApp",
    "_type": "json",
    "numOfRows": 5,
    "pageNo": 1,
    "langDivCd": "KOR",
}


def parse_items(data):
    body = data.get("response", {}).get("body", {})
    items = body.get("items", {}).get("item", [])
    total = body.get("totalCount", 0)
    if isinstance(items, dict):
        items = [items]
    return items, total


def test_area_based_list():
    print("\n" + "=" * 60)
    print("테스트 1: 지역기반 웰니스 관광정보 조회")
    print("=" * 60)
    url = f"{BASE_URL}/areaBasedList"
    resp = requests.get(url, params={**common_params})
    print(f"HTTP Status: {resp.status_code}")

    data = resp.json()
    items, total = parse_items(data)
    print(f"총 건수: {total}")

    for i, item in enumerate(items, 1):
        print(f"\n  [{i}] {item.get('title')}")
        print(f"      주소: {item.get('baseAddr')} {item.get('detailAddr', '')}")
        print(f"      우편번호: {item.get('zipCd')}")
        print(f"      contentId: {item.get('contentId')}")
        print(f"      contentTypeId: {item.get('contentTypeId')}")
        print(f"      웰니스테마: {item.get('wellnessThemaCd')}")
        print(f"      좌표: ({item.get('mapX')}, {item.get('mapY')})")
        print(f"      전화: {item.get('tel')}")
        if item.get('thumbImage'):
            print(f"      썸네일: {item.get('thumbImage')}")

    return items[0] if items else None


def test_search_keyword(keyword):
    print("\n" + "=" * 60)
    print(f"테스트 2: 키워드 검색 - '{keyword}'")
    print("=" * 60)
    url = f"{BASE_URL}/searchKeyword"
    params = {**common_params, "keyword": keyword}
    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    data = resp.json()
    items, total = parse_items(data)
    print(f"총 건수: {total}")

    for i, item in enumerate(items, 1):
        print(f"\n  [{i}] {item.get('title')}")
        print(f"      주소: {item.get('baseAddr')}")
        print(f"      contentId: {item.get('contentId')}")
        print(f"      웰니스테마: {item.get('wellnessThemaCd')}")

    return items[0] if items else None


def test_detail_common(content_id):
    print("\n" + "=" * 60)
    print(f"테스트 3: 공통정보 조회 - contentId: {content_id}")
    print("=" * 60)
    url = f"{BASE_URL}/detailCommon"
    params = {**common_params, "contentId": content_id}
    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    data = resp.json()
    items, _ = parse_items(data)
    if not items:
        print(f"응답: {data}")
        return

    item = items[0]
    print(f"\n  제목: {item.get('title')}")
    print(f"  주소: {item.get('baseAddr')} {item.get('detailAddr', '')}")
    print(f"  전화: {item.get('tel')}")
    print(f"  좌표: ({item.get('mapX')}, {item.get('mapY')})")
    print(f"  웰니스테마: {item.get('wellnessThemaCd')}")

    overview = item.get("overview", "")
    if overview:
        overview_clean = re.sub(r"<[^>]+>", "", overview)
        print(f"  개요: {overview_clean[:300]}")

    # 모든 필드 출력
    print(f"\n  === 전체 필드 ===")
    for k, v in item.items():
        if v:
            val = str(v)[:200]
            print(f"  {k}: {val}")


def test_detail_intro(content_id, content_type_id):
    print("\n" + "=" * 60)
    print(f"테스트 4: 소개정보 조회 - contentId: {content_id}")
    print("=" * 60)
    url = f"{BASE_URL}/detailIntro"
    params = {**common_params, "contentId": content_id, "contentTypeId": content_type_id}
    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    data = resp.json()
    items, _ = parse_items(data)
    if not items:
        print(f"응답: {data}")
        return

    item = items[0]
    print(f"\n  === 소개 상세 ===")
    for k, v in item.items():
        if v:
            print(f"  {k}: {v}")


def test_detail_image(content_id):
    print("\n" + "=" * 60)
    print(f"테스트 5: 이미지정보 조회 - contentId: {content_id}")
    print("=" * 60)
    url = f"{BASE_URL}/detailImage"
    params = {**common_params, "contentId": content_id, "imageYN": "Y", "subImageYN": "Y"}
    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    data = resp.json()
    items, _ = parse_items(data)
    if not items:
        print(f"응답: {data}")
        return

    print(f"이미지 수: {len(items)}")
    for i, item in enumerate(items, 1):
        print(f"\n  [{i}] {item.get('imgname', 'N/A')}")
        print(f"      원본: {item.get('originimgurl', item.get('orgImage', 'N/A'))}")
        print(f"      썸네일: {item.get('smallimageurl', item.get('thumbImage', 'N/A'))}")


if __name__ == "__main__":
    print("=== 웰니스관광정보 API 테스트 시작 ===\n")

    # 테스트 1: 전체 목록
    first_item = test_area_based_list()

    # 테스트 2: 키워드 검색
    search_result = test_search_keyword("스파")

    # 상세 조회
    target = first_item or search_result
    if target:
        cid = target.get("contentId")
        ctid = target.get("contentTypeId")
        print(f"\n>>> 상세 조회 대상: contentId={cid}, contentTypeId={ctid}")

        test_detail_common(cid)
        if ctid:
            test_detail_intro(cid, ctid)
        test_detail_image(cid)

    print("\n=== 테스트 완료 ===")
