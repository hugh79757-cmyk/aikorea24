#!/usr/bin/env python3
"""Migrate existing posted articles to Vectorize index.

Usage:
  cd scripts/threads && python3 migrate_to_vectorize.py [--batch 20] [--dry-run]

Reads posted_article_meta from posted.json, embeds each article, and upserts
to Cloudflare Vectorize index 'aikorea24-dedup'.
"""
import os, sys, json, time, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pipeline.infra.vectorize_client import embed_article, upsert_vectors, get_index_stats
from db_reader import load_posted

def main():
    parser = argparse.ArgumentParser(description='Migrate posted articles to Vectorize')
    parser.add_argument('--batch', type=int, default=20, help='Batch size for upsert (default: 20)')
    parser.add_argument('--dry-run', action='store_true', help='Print stats without writing')
    args = parser.parse_args()

    posted = load_posted()
    meta = posted.get('posted_article_meta', {})
    print(f'📁 posted_article_meta: {len(meta)} articles')

    if not meta:
        print('⚠️ No articles to migrate')
        return

    # Build article-like dicts from meta
    articles = []
    for aid, m in meta.items():
        articles.append({
            'id': aid,
            'title': m.get('title', ''),
            'original_title': m.get('original_title', ''),
            'description': m.get('description', ''),
        })

    if args.dry_run:
        print(f'[DRY RUN] Would embed and upsert {len(articles)} articles in batches of {args.batch}')
        stats = get_index_stats()
        print(f'  Current Vectorize index: {stats}')
        return

    # Process in batches
    total = len(articles)
    success = 0
    failed = 0
    for i in range(0, total, args.batch):
        batch = articles[i:i+args.batch]
        vectors = []
        for a in batch:
            vec = embed_article(a)
            if vec:
                vectors.append(vec)
            else:
                failed += 1
                print(f'  ⚠️ Embed failed: article {a["id"]}')

        if vectors:
            ok = upsert_vectors(vectors)
            if ok:
                success += len(vectors)
            else:
                failed += len(vectors)
            print(f'  📦 Batch {i//args.batch + 1}: {len(vectors)} vectors upserted')

        # Rate limit: brief pause between batches
        if i + args.batch < total:
            time.sleep(0.5)

    print(f'\n✅ Migration complete: {success} success, {failed} failed out of {total}')
    stats = get_index_stats()
    print(f'  Vectorize index stats: {stats}')

if __name__ == '__main__':
    main()
