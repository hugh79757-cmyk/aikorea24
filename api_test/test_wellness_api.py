import os
import requests
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()
SERVICE_KEY = os.getenv("DATA_GO_KR_KEY")

if not SERVICE_KEY:
    print("❌ DATA_GO_KR_KEY가 .env에 없습니다. 확인해주세요.")
    exit()

print(f"✅ API 키 로드 완료 (앞 10자: {SERVICE_KEY[:10]}...)")

BASE_URL = "https://apis.data.go.kr/B551011/WellnessTursmService"

# 공통 파라미터
common_params = {
    "serviceKey": SERVICE_KEY,
    "MobileOS": "ETC",
    "MobileApp": "TestApp",
    "_type": "json",
    "numOfRows": 5,
    "pageNo": 1,
}


def test_area_based_list():
    """테스트 1: 지역기반 웰니스 관광정보 조회"""
    print("\n" + "=" * 60)
    print("📌 테스트 1: 지역기반 웰니스 관광정보 조회 (areaBasedList1)")
    print("=" * 60)

    url = f"{BASE_URL}/areaBasedList1"
    params = {**common_params}

    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code == 200:
        try:
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            print(f"resultCode: {header.get('resultCode')}")
            print(f"resultMsg: {header.get('resultMsg')}")

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            total = data.get("response", {}).get("body", {}).get("totalCount", 0)
            print(f"총 건수: {total}")

            for i, item in enumerate(items, 1):
                print(f"\n  [{i}] {item.get('title', 'N/A')}")
                print(f"      주소: {item.get('addr1', 'N/A')} {item.get('addr2', '')}")
                print(f"      contentId: {item.get('contentid')}")
                print(f"      contenttypeid: {item.get('contenttypeid')}")
                print(f"      좌표: ({item.get('mapx')}, {item.get('mapy')})")
                if item.get("firstimage"):
                    print(f"      이미지: {item.get('firstimage')}")

            return items[0] if items else None
        except Exception as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 본문: {resp.text[:500]}")
    else:
        print(f"응답 본문: {resp.text[:500]}")
    return None


def test_search_keyword(keyword="스파"):
    """테스트 2: 키워드 검색 조회"""
    print("\n" + "=" * 60)
    print(f"📌 테스트 2: 키워드 검색 조회 (searchKeyword1) - '{keyword}'")
    print("=" * 60)

    url = f"{BASE_URL}/searchKeyword1"
    params = {**common_params, "keyword": keyword}

    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code == 200:
        try:
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            print(f"resultCode: {header.get('resultCode')}")
            print(f"resultMsg: {header.get('resultMsg')}")

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            total = data.get("response", {}).get("body", {}).get("totalCount", 0)
            print(f"총 건수: {total}")

            for i, item in enumerate(items, 1):
                print(f"\n  [{i}] {item.get('title', 'N/A')}")
                print(f"      주소: {item.get('addr1', 'N/A')}")
                print(f"      contentId: {item.get('contentid')}")

            return items[0] if items else None
        except Exception as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 본문: {resp.text[:500]}")
    else:
        print(f"응답 본문: {resp.text[:500]}")
    return None


def test_detail_common(content_id):
    """테스트 3: 공통정보 조회"""
    print("\n" + "=" * 60)
    print(f"📌 테스트 3: 공통정보 조회 (detailCommon1) - contentId: {content_id}")
    print("=" * 60)

    url = f"{BASE_URL}/detailCommon1"
    params = {**common_params, "contentId": content_id}

    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code == 200:
        try:
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            print(f"resultCode: {header.get('resultCode')}")
            print(f"resultMsg: {header.get('resultMsg')}")

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            for item in items:
                print(f"\n  제목: {item.get('title', 'N/A')}")
                print(f"  주소: {item.get('addr1', 'N/A')} {item.get('addr2', '')}")
                print(f"  전화: {item.get('tel', 'N/A')}")
                print(f"  좌표: ({item.get('mapx')}, {item.get('mapy')})")
                print(f"  홈페이지: {item.get('homepage', 'N/A')}")
                overview = item.get("overview", "")
                if overview:
                    # HTML 태그 간단 제거
                    import re
                    overview_clean = re.sub(r"<[^>]+>", "", overview)
                    print(f"  개요: {overview_clean[:200]}...")
        except Exception as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 본문: {resp.text[:500]}")
    else:
        print(f"응답 본문: {resp.text[:500]}")


def test_detail_intro(content_id, content_type_id):
    """테스트 4: 소개정보 조회"""
    print("\n" + "=" * 60)
    print(f"📌 테스트 4: 소개정보 조회 (detailIntro1) - contentId: {content_id}")
    print("=" * 60)

    url = f"{BASE_URL}/detailIntro1"
    params = {
        **common_params,
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }

    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code == 200:
        try:
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            print(f"resultCode: {header.get('resultCode')}")
            print(f"resultMsg: {header.get('resultMsg')}")

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            for item in items:
                print(f"\n  === 소개 상세정보 ===")
                for key, value in item.items():
                    if value and value != "":
                        print(f"  {key}: {value}")
        except Exception as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 본문: {resp.text[:500]}")
    else:
        print(f"응답 본문: {resp.text[:500]}")


def test_detail_image(content_id):
    """테스트 5: 이미지정보 조회"""
    print("\n" + "=" * 60)
    print(f"📌 테스트 5: 이미지정보 조회 (detailImage1) - contentId: {content_id}")
    print("=" * 60)

    url = f"{BASE_URL}/detailImage1"
    params = {
        **common_params,
        "contentId": content_id,
        "imageYN": "Y",
        "subImageYN": "Y",
    }

    resp = requests.get(url, params=params)
    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code == 200:
        try:
            data = resp.json()
            header = data.get("response", {}).get("header", {})
            print(f"resultCode: {header.get('resultCode')}")
            print(f"resultMsg: {header.get('resultMsg')}")

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            print(f"이미지 수: {len(items)}")
            for i, item in enumerate(items, 1):
                print(f"\n  [{i}] {item.get('imgname', 'N/A')}")
                print(f"      원본: {item.get('originimgurl', 'N/A')}")
        except Exception as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 본문: {resp.text[:500]}")
    else:
        print(f"응답 본문: {resp.text[:500]}")


# =============================================
# 메인 실행
# =============================================
if __name__ == "__main__":
    print("🏥 한국관광공사 웰니스관광정보 API 테스트 시작")
    print(f"Base URL: {BASE_URL}")

    # 테스트 1: 지역기반 전체 목록 조회
    first_item = test_area_based_list()

    # 테스트 2: 키워드 검색
    search_result = test_search_keyword("힐링")

    # 테스트 2-2: 다른 키워드도 시도
    if not search_result:
        search_result = test_search_keyword("명상")
    if not search_result:
        search_result = test_search_keyword("뷰티")

    # 첫 번째 결과의 contentId로 상세 정보 조회
    target = first_item or search_result
    if target:
        content_id = target.get("contentid")
        content_type_id = target.get("contenttypeid")
        print(f"\n🎯 상세 조회 대상: contentId={content_id}, typeId={content_type_id}")

        # 테스트 3: 공통정보
        test_detail_common(content_id)

        # 테스트 4: 소개정보
        if content_type_id:
            test_detail_intro(content_id, content_type_id)

        # 테스트 5: 이미지정보
        test_detail_image(content_id)
    else:
        print("\n⚠️ 조회 결과가 없어 상세 테스트를 건너뜁니다.")

    print("\n" + "=" * 60)
    print("✅ 테스트 완료!")
    print("=" * 60)
