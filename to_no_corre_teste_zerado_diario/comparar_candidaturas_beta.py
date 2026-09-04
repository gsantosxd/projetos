import os, sqlite3
from collections import Counter
from pathlib import Path

here=Path(__file__).resolve().parent
beta_root=Path(os.environ["LOCALAPPDATA"])/"ToNoCorre"/"Beta1"
backups=sorted((beta_root/"backups").glob("vagas_*.db"))
beta=backups[-1] if backups else beta_root/"vagas.db"
def connect(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row;return db
cur=connect(here/"vagas.db");old=connect(beta)
current=cur.execute("select * from vagas").fetchall()
applied=old.execute("select * from vagas where status='Candidatado'").fetchall()
urls={r["url"]:r for r in current}
discard=dict(cur.execute("select url,motivo_descarte from descartadas"))
print("ATUAL STATUS",Counter(r["status"] for r in current))
print("ATUAL DECISAO",Counter((r["decisao"] or "") for r in current if r["status"]=='Nova'))
print("ATUAL FAIXAS",Counter("70+" if (r["score"] or 0)>=70 else "50-69" if (r["score"] or 0)>=50 else "<50" for r in current if r["status"]=='Nova'))
print("CANDIDATURAS BETA",len(applied))
found=[r for r in applied if r["url"] in urls]
missing=[r for r in applied if r["url"] not in urls]
print("RECUPERADAS",len(found),"AUSENTES",len(missing))
print("RECUPERADAS STATUS",Counter(urls[r["url"]]["status"] for r in found))
print("RECUPERADAS FAIXAS",Counter("70+" if (urls[r["url"]]["score"] or 0)>=70 else "50-69" if (urls[r["url"]]["score"] or 0)>=50 else "<50" for r in found))
print("AUSENTES FONTES",Counter(r["fonte"] for r in missing))
print("AUSENTES DESTINO",Counter(discard.get(r["url"],"não coletada") for r in missing))
for r in missing:print("AUSENTE",r["titulo"],"|",r["empresa"],"|",r["fonte"],"|",discard.get(r["url"],"não coletada"))

print("\nBANCOS COM CANDIDATURAS")
candidates=list((Path(os.environ["LOCALAPPDATA"])/"ToNoCorre").rglob("*.db"))
candidates+=list(here.parent.glob("to_no_corre_beta*/**/*.db"))
for path in candidates:
    try:
        db=connect(path)
        count=db.execute("select count(1) from vagas where status='Candidatado'").fetchone()[0]
        total=db.execute("select count(1) from vagas").fetchone()[0]
        if count:print(path,"candidaturas",count,"total",total)
    except Exception:pass
