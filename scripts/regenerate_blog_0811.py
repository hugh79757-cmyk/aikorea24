#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""어제(2026-08-11) 브리핑 중 실패한 블로그 초안 재생성 — 무료 체인 적용"""
import sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from blog_draft_generator import (
    generate_draft, save_draft, next_file_number,
    process_thumbnail, _add_image_to_frontmatter,
    log, query_d1, load_env, send_telegram,
)

load_env()

# 실패한 기사 ID (22시 로그에서 확인)
TARGET_IDS = [44735, 44679, 44712]
DATE_STR = '2026-08-11'

def main():
    sql = f'''
        SELECT n.id, n.title, n.description, n.source, n.category, n.link
        FROM news n
        WHERE n.id IN ({','.join(str(i) for i in TARGET_IDS)})
    '''
    rows = query_d1(sql)
    print(f'대상 기사: {len(rows)}건')
    if not rows:
        print('대상 없음')
        return

    file_num = next_file_number(DATE_STR)
    created = []
    for art in rows:
        title = art.get('title', '')
        link = art.get('link', '')
        print(f"\n=== [{art.get('id')}] {title[:60]} ===")
        try:
            gpt_output = generate_draft(title, [art], 'A')
            if not gpt_output:
                print(f'  ❌ 생성 실패')
                continue
            filepath, seo_title = save_draft(gpt_output, title, file_num, DATE_STR, articles=[art])
            created.append(filepath)
            file_num += 1
            print(f'  ✅ 저장: {os.path.basename(filepath)}')

            # 썸네일
            try:
                slug = os.path.basename(filepath).replace('.md', '').lower()
                thumb_rel = process_thumbnail(link, slug, title=title, description=art.get('description', ''))
                if thumb_rel:
                    _add_image_to_frontmatter(filepath, thumb_rel)
                    print(f'  🖼️ 썸네일: {thumb_rel}')
            except Exception as e:
                print(f'  ⚠️ 썸네일 실패: {e}')
        except Exception as e:
            print(f'  ❌ 예외: {e}')

    print(f'\n완료: {len(created)}건 생성')
    if created:
        send_telegram(f'🔄 [재생성] 8/11 블로그 초안 {len(created)}건 생성됨 (무료 체인)')

if __name__ == '__main__':
    main()
