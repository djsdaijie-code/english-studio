from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))

from english_typing_trainer.application.context import build_app_context


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--data-dir",type=Path,required=True); args=parser.parse_args()
    context=build_app_context(data_dir=args.data_dir)
    try:
        rows=context.vocabulary_learning_service.list_entries()
        assert rows
        ready=[row for row in rows if row["dictionary_status"] in {"ready","not_found"}]
        assert ready
        contexts=sum((context.vocabulary_learning_service.repository.list_contexts(row["id"]) for row in ready),[])
        assert any(item.ai_status=="ready" and item.contextual_meaning_zh for item in contexts)
        cache_rows=context.database.connect().execute("SELECT file_path,source_type,content_type FROM tts_audio_cache WHERE status='completed'").fetchall()
        assert cache_rows
        assert all((context.paths.audio_cache_dir/row["file_path"]).is_file() for row in cache_rows)
        assert any(row["source_type"]=="dictionary" for row in cache_rows)
        assert any(row["content_type"] in {"word","sentence"} for row in cache_rows)
        print(f"VOCABULARY_OFFLINE_OK entries={len(rows)} contexts={len(contexts)} cached_audio={len(cache_rows)}")
    finally: context.database.close()


if __name__=="__main__": main()
