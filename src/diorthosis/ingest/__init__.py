from .alto import ingest_alto
from .borndigital import ingest_pdf
from .hocr import ingest_hocr
from .pagexml import ingest_pagexml

__all__ = ["ingest_alto", "ingest_hocr", "ingest_pagexml", "ingest_pdf"]
