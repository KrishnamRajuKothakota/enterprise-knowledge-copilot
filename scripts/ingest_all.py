"""One-command ingestion of all data sources."""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

from src.ekc.ingestion.pipeline import DocumentIngestionPipeline

pipeline = DocumentIngestionPipeline()
total = 0

sources = [
    ('data/raw/SriniInfotech_SOPs_Volume1_SOP001-015.pdf',  'it-ops'),
    ('data/raw/SriniInfotech_SOPs_Volume2_SOP016-030.pdf',  'it-ops'),
    ('data/raw/SriniInfotech_IT_Support_Tickets_300.csv',   'support'),
    ('data/raw/synthetic_jira_tickets_400.csv',             'devops'),
    ('data/raw/SriniInfotech_Hackathon_ConceptNote.pptx',   'general'),
    ('data/raw/dataset-tickets-multi-lang3-4k.csv',         'support'),
]
dirs = [
    ('data/raw/k8s',    'kubernetes'),
    ('data/raw/docker', 'docker'),
]

for path, ns in sources:
    if os.path.exists(path):
        r = pipeline.ingest_file(path, namespace=ns)
        print(f'{path}: {r.chunks_created} chunks')
        total += r.chunks_created
    else:
        print(f'SKIP (not found): {path}')

for d, ns in dirs:
    if os.path.exists(d):
        r = pipeline.ingest_directory(d, namespace=ns)
        print(f'{d}: {r.chunks_created} chunks')
        total += r.chunks_created
    else:
        print(f'SKIP (not found): {d}')

print(f'\nTotal chunks ingested: {total}')
