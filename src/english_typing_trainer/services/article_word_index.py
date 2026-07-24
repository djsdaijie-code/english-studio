from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import ArticleRepository
from english_typing_trainer.services.sentence_segmentation import SentenceSegmentationService
from english_typing_trainer.services.word_normalization import WordNormalizationService


WORD_PATTERN=re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*")
JUNK_PATTERN=re.compile(r"(?:https?://|www\.)\S+|\b\S+@\S+\b",re.IGNORECASE)


@dataclass(frozen=True,slots=True)
class ArticleWordOccurrence:
    normalized_word:str; source_word:str; source_sentence:str; start_offset:int; end_offset:int; occurrence_index:int


class ArticleWordIndexService:
    version="word-v1"
    def __init__(self,database:DatabaseManager,normalization:WordNormalizationService) -> None:
        self.database=database; self.articles=ArticleRepository(database.connect); self.normalization=normalization; self.sentences=SentenceSegmentationService()

    def extract(self,text:str) -> list[ArticleWordOccurrence]:
        junk=[match.span() for match in JUNK_PATTERN.finditer(text)]
        sentence_ranges=[(item.start_offset,item.end_offset,item.normalized_text) for item in self.sentences.split(text)]
        result=[]
        for match in WORD_PATTERN.finditer(text):
            if any(start<=match.start()<end for start,end in junk): continue
            normalized=self.normalization.normalize(match.group())
            if not normalized: continue
            sentence=next((value for start,end,value in sentence_ranges if start<=match.start()<end),"")
            result.append(ArticleWordOccurrence(normalized,match.group(),sentence,match.start(),match.end(),len(result)))
        return result

    def ensure(self,article_id:int) -> int:
        row=self.database.connect().execute("SELECT COUNT(*) FROM article_word_occurrences WHERE article_id=?",(article_id,)).fetchone()
        if row and row[0]>0:return int(row[0])
        return self.rebuild(article_id)

    def rebuild(self,article_id:int) -> int:
        article=self.articles.get_article(article_id,include_deleted=True)
        if not article:raise ValueError("未找到文章。")
        occurrences=self.extract(article.full_text)
        with self.database.transaction() as connection:
            self.replace_in_transaction(connection, article_id, occurrences)
        return len(occurrences)

    def replace_in_transaction(self, connection, article_id: int, occurrences: list[ArticleWordOccurrence]) -> None:
        stamp=datetime.now().isoformat(timespec="seconds")
        connection.execute("DELETE FROM article_word_occurrences WHERE article_id=?",(article_id,))
        connection.executemany("""INSERT INTO article_word_occurrences(article_id,normalized_word,source_word,source_sentence,start_offset,end_offset,occurrence_index,extraction_version,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",[(article_id,o.normalized_word,o.source_word,o.source_sentence,o.start_offset,o.end_offset,o.occurrence_index,self.version,stamp) for o in occurrences])

    def list_words(self,article_id:int|None=None,*,search:str="",sort:str="first",hide_mastered:bool=False):
        where="WHERE 1=1"; params=[]
        if article_id is not None:where+=" AND o.article_id=?";params.append(article_id)
        if search.strip():where+=" AND o.normalized_word LIKE ?";params.append(f"%{search.strip().lower()}%")
        if hide_mastered:where+=" AND COALESCE(s.status,'')!='mastered'"
        order="normalized_word" if sort=="alpha" else "occurrence_count DESC" if sort=="frequency" else "first_occurrence_offset"
        return self.database.connect().execute(f"""SELECT o.normalized_word,MIN(o.source_word) display_word,COUNT(*) occurrence_count,
            MIN(o.start_offset) first_occurrence_offset,MIN(o.source_sentence) source_sentence,
            COUNT(DISTINCT o.article_id) article_count,e.id vocabulary_entry_id,COALESCE(s.status,'') status
            FROM article_word_occurrences o LEFT JOIN vocabulary_entries e ON e.normalized_word=o.normalized_word
            LEFT JOIN vocabulary_learning_state s ON s.vocabulary_entry_id=e.id {where}
            GROUP BY o.normalized_word ORDER BY {order}""",params).fetchall()
