import os, re, json, time, sqlite3, threading, unicodedata, urllib.parse, webbrowser, random, subprocess, sys, logging, socket, glob, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta, timezone
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

APP_TITLE="Tô no Corre"
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,"vagas.db")
PROFILE_PATH=os.path.join(BASE_DIR,"perfil.json")
CV_PATH=os.path.join(BASE_DIR,"curriculo.txt")
CV_FILE_PATH=os.path.join(BASE_DIR,"curriculo_original")
CACHE_PATH=os.path.join(BASE_DIR,"cache_detalhes.json")
HEALTH_PATH=os.path.join(BASE_DIR,"saude_fontes.json")
LOG_PATH=os.path.join(BASE_DIR,"to_no_corre.log")
BACKUP_DIR=os.path.join(BASE_DIR,"backups")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8"
)
LOGGER=logging.getLogger("to_no_corre")

def load_json_file(path,default):
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def save_json_file(path,data):
    try:
        with open(path,"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
    except Exception:
        LOGGER.exception("Não foi possível salvar o arquivo JSON: %s",path)

DETAIL_CACHE=load_json_file(CACHE_PATH,{})
CACHE_LOCK=threading.Lock()

def backup_database():
    """Cria no máximo um backup por dia, antes de qualquer migration."""
    if not os.path.isfile(DB_PATH) or os.path.getsize(DB_PATH)==0:return ""
    os.makedirs(BACKUP_DIR,exist_ok=True)
    today=datetime.now().strftime("%Y%m%d")
    existing=glob.glob(os.path.join(BACKUP_DIR,f"vagas_{today}_*.db"))
    if existing:return existing[-1]
    target=os.path.join(BACKUP_DIR,f"vagas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(DB_PATH,target);return target


UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"

def norm(t):
    t=unicodedata.normalize("NFKD", str(t or ""))
    t="".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",t.lower()).strip()

def clean(t):
    if not t:return ""
    if BeautifulSoup:
        return BeautifulSoup(str(t),"html.parser").get_text(" ",strip=True)
    return re.sub(r"<[^>]+>"," ",str(t))

def compact_json(value):
    if value in (None,"",[],{}):return ""
    if isinstance(value,str):return value
    try:return json.dumps(value,ensure_ascii=False,separators=(",",":"))
    except Exception:return clean(value)

def structured_persistence(job,location_info):
    mode=location_info.get("mode","")
    eligible=1 if mode.startswith("Remoto Brasil") and "confirmado" in mode else 0 if mode.startswith("Remoto sem") else None
    return (
        str(job.get("workplace_type_raw") or job.get("workplace_type") or ""),
        str(job.get("workplace_source") or ""),
        compact_json(job.get("structured_location_json") or job.get("structured_location")),
        compact_json(job.get("applicant_location_requirements")),
        eligible,
        datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

def default_profile():
    """Configuração neutra para a primeira execução, sem dados de desenvolvedor."""
    return {
        "perfil_curriculo_versao":0,
        "areas_curriculo_detectadas":[],"competencias_curriculo_detectadas":[],
        "termos_curriculo_detectados":[],"cursos_curriculo_detectados":[],
        "competencias_perfil":[],"termos_perfil":[],
        "consultas_br":[],"consultas_gupy":[],"consultas_linkedin":[],"consultas_google":[],
        "cidades_presencial":[],"cidades_presencial_hibrido":[],"estado_local":"",
        "aceitar_remoto":True,"buscar_estagios":False,"mostrar_compativeis_fora_regiao":False,
        "idade_maxima_vaga_dias":60,"idade_maxima_dias":60,
        "descartar_vagas_encerradas":True,"descartar_vagas_exclusivas_pcd":True,
        "descartar_superior_completo_obrigatorio":True,"descartar_experiencia_especifica_anos":5,
        "navegador_automacao":"automatico","enriquecimento_inicial_linkedin":0,
        "cache_detalhes_horas":24,"usar_tres_niveis_decisao":True
    }

def load_profile():
    profile=load_json_file(PROFILE_PATH,None)
    if not isinstance(profile,dict):
        profile=default_profile();save_json_file(PROFILE_PATH,profile)
    return profile

def read_cv():
    try:
        with open(CV_PATH,encoding="utf-8") as stream:
            return stream.read()
    except:return ""

def parse_cv_file(path):
    ext=os.path.splitext(path)[1].lower()
    if ext==".pdf":
        try:
            from pypdf import PdfReader
            return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages).strip()
        except Exception as e: raise RuntimeError("Não consegui ler este PDF. Tente outro arquivo.") from e
    if ext==".docx":
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(path).paragraphs).strip()
        except Exception as e: raise RuntimeError("Não consegui ler este DOCX.") from e
    if ext==".txt":
        with open(path,encoding="utf-8",errors="ignore") as stream:
            return stream.read().strip()
    raise RuntimeError("Use um currículo em PDF, DOCX ou TXT.")

def cv_profile_summary(text):
    n=norm(text); areas=[]; skills=[]; education=[]
    rules=[
        ("Jurídico",["direito","juridico","jurídico","peticao","petição","processual","tribunal","pje","eproc"]),
        ("Administrativo",["administrativo","documentacao","documentação","arquivo","planilha","office"]),
        ("Atendimento",["atendimento","cliente","publico","público","suporte"]),
        ("Tecnologia / TI",["analise e desenvolvimento de sistemas","tecnologia da informacao","tecnologia da informação","software","programacao","programação","help desk","service desk"]),
    ]
    for label,terms in rules:
        if any(norm(t) in n for t in terms):areas.append(label)
    skill_rules=[("Atendimento","atendimento"),("Excel","excel"),("Pacote Office","office"),("Suporte","suporte"),
                 ("Processos jurídicos","process"),("Controle de prazos","prazo"),("Contratos","contrat"),
                 ("Sistemas","sistema"),("Inglês","ingles"),("Espanhol","espanhol")]
    for label,term in skill_rules:
        if term in n and label not in skills:skills.append(label)
    if "cursando" in n or "graduando" in n: education.append("Ensino superior em andamento")
    if "ensino medio" in n or "ensino médio" in text.lower(): education.append("Ensino médio")
    stop={"para","com","uma","das","dos","que","por","como","the","and","from","de","da","do",
          "em","no","na","ao","aos","nas","nos","seu","sua","anos","experiencia","profissional",
          "empresa","cargo","atividades","responsavel","formacao","curso","conhecimento"}
    words=re.findall(r"[a-z][a-z0-9+#.-]{2,}",n);counts={}
    for word in words:
        if word not in stop and not word.isdigit():counts[word]=counts.get(word,0)+1
    keywords=[word for word,_count in sorted(counts.items(),key=lambda item:(-item[1],item[0]))[:24]]
    courses=[]
    # Formação deve ser extraída linha a linha. `norm(text)` remove quebras e antes
    # fazia uma linha de certificações virar, incorretamente, nome de curso.
    for raw_line in str(text or "").splitlines():
        line=norm(raw_line)
        match=re.search(r"(?:graduacao|bacharelado|tecnologo|curso superior|cursando)\s+(?:em\s+)?(.{3,70})",line)
        if not match:continue
        course=re.split(r"[.,;|•]|\s+-\s+|\s+(?:na|no|pela|pelo|universidade|faculdade)\s+",match.group(1))[0].strip(" .-")
        course=re.sub(r"\s+\d+[ºo]?\s*(?:periodo|semestre).*$","",course).strip()
        if course and not any(x in course for x in ("ensino medio","certificacoes","cursos livres")) and course not in courses:
            courses.append(course)
    if not courses:
        if re.search(r"\b(?:graduacao|bacharelado|cursando).{0,35}\bdireito\b",n):courses.append("direito")
        if "analise e desenvolvimento de sistemas" in n:courses.append("análise e desenvolvimento de sistemas")
    return {"areas":areas or ["Geral"],"skills":skills[:10],"education":education,
            "keywords":keywords,"courses":courses[:6]}

def adapt_profile_to_cv(p,text):
    prof=cv_profile_summary(text); n=norm(text); queries=[]
    include_internships=bool(p.get("buscar_estagios",False))
    if "Jurídico" in prof["areas"]:
        queries += ["assistente jurídico","auxiliar jurídico","controladoria jurídica","paralegal","legal operations"]
        if include_internships:queries += ["estágio direito","estágio jurídico"]
    if "Tecnologia / TI" in prof["areas"]:
        queries += ["suporte n1","help desk","service desk","assistente de suporte"]
        if include_internships:queries += ["estágio TI","estágio ADS","estágio suporte técnico"]
    if "Administrativo" in prof["areas"]:
        queries += ["assistente administrativo","auxiliar administrativo","assistente de operações","backoffice"]
    if "Atendimento" in prof["areas"]:
        queries += ["atendimento ao cliente","customer support","assistente de atendimento"]
    for course in prof["courses"][:2]:
        if include_internships:queries.append(f"estágio {course}")
        queries += [f"assistente {course}",f"analista júnior {course}"]
    if not queries:
        useful=[word for word in prof["keywords"] if len(word)>=5][:4]
        queries=[f"assistente {word}" for word in useful[:2]]+[f"analista júnior {word}" for word in useful[2:]]
    if not queries:queries=["assistente","auxiliar","atendimento"]
    def valid_query(value):
        value=clean(value).strip()
        nv=norm(value)
        return value if 2<len(value)<=70 and "•" not in value and " periodo" not in nv and " semestre" not in nv else ""
    motors=p.get("motores_busca",{}) if isinstance(p.get("motores_busca",{}),dict) else {}
    legacy=[]
    if "Jurídico" in prof["areas"]:legacy+=motors.get("juridico",[])[:14]+motors.get("estagio_direito",[])[:8]
    if "Tecnologia / TI" in prof["areas"]:legacy+=motors.get("estagio_ads",[])[:10]
    if "Administrativo" in prof["areas"] or "Atendimento" in prof["areas"]:legacy+=motors.get("geral",[])[:14]
    previous=list(p.get("consultas_br",[]))+list(p.get("consultas_gupy",[]))
    combined=[valid_query(x) for x in queries+previous+legacy]
    if not include_internships:combined=[x for x in combined if "estagio" not in norm(x) and "estagiario" not in norm(x)]
    combined=list(dict.fromkeys(x for x in combined if x))
    linkedin=[valid_query(x) for x in list(p.get("consultas_linkedin",[]))+queries+legacy]
    if not include_internships:linkedin=[x for x in linkedin if "estagio" not in norm(x) and "estagiario" not in norm(x)]
    linkedin=list(dict.fromkeys(x for x in linkedin if x))
    p["consultas_br"]=combined[:45]
    p["consultas_gupy"]=combined[:40]
    p["consultas_linkedin"]=linkedin[:35]
    p["areas_curriculo_detectadas"]=prof["areas"]
    p["competencias_curriculo_detectadas"]=prof["skills"]
    p["termos_curriculo_detectados"]=prof["keywords"]
    p["cursos_curriculo_detectados"]=prof["courses"]
    p["perfil_curriculo_versao"]=2
    p["competencias_perfil"]=list(dict.fromkeys(prof["skills"]+prof["keywords"]))[:40]
    p["termos_perfil"]=list(dict.fromkeys(prof["keywords"]+prof["areas"]))[:40]
    return prof

def profile_terms(p):
    return [norm(x) for x in p.get("termos_perfil",p.get("termos_relevancia",[])) if norm(x)]

def profile_skills(p):
    return [norm(x) for x in p.get("competencias_perfil",p.get("competencias",[])) if norm(x)]

def profile_courses(p):
    return [norm(x) for x in p.get("cursos_curriculo_detectados",[]) if norm(x)]

def feedback_tokens(text):
    ignored={"vaga","estagio","assistente","auxiliar","analista","junior","pleno","senior","para","com","de","da","do","em"}
    return [x for x in re.findall(r"[a-z][a-z0-9+#.-]{3,}",norm(text)) if x not in ignored][:8]

def salary_and_benefits(job):
    text=clean((job.get("salario") or "")+" "+(job.get("descricao") or ""))
    # Prefer salary field, then explicit R$ values near salary/remuneration words.
    sal=(job.get("salario") or "").strip()
    if not sal:
        pats=re.findall(r"(?:sal[aá]rio|remunera[cç][aã]o|bolsa)[^\n.;:]{0,45}?(R\$\s*[\d\.]+(?:,\d{2})?(?:\s*(?:a|até|-)\s*R?\$?\s*[\d\.]+(?:,\d{2})?)?)",text,re.I)
        if pats: sal=pats[0].strip()
    benefits=[]
    mapping=[
      ("Vale-refeição",r"\b(?:vale[- ]?refei[cç][aã]o|vr)\b"),("Vale-alimentação",r"\b(?:vale[- ]?alimenta[cç][aã]o|va)\b"),
      ("Vale-transporte",r"\b(?:vale[- ]?transporte|vt)\b"),("Plano de saúde",r"\b(?:plano|assist[eê]ncia|conv[eê]nio)\s+(?:de\s+)?sa[uú]de\b"),
      ("Plano odontológico",r"\b(?:plano|assist[eê]ncia)\s+odontol[oó]gic[oa]\b"),("Seguro de vida",r"\bseguro de vida\b"),
      ("Auxílio home office",r"\b(?:aux[ií]lio|ajuda de custo)[^\n.;]{0,25}home office\b"),("Gympass/Wellhub",r"\b(?:gympass|wellhub)\b"),
      ("TotalPass",r"\btotalpass\b"),("PLR",r"\b(?:plr|participa[cç][aã]o nos lucros)\b"),
      ("Auxílio educação",r"\b(?:aux[ií]lio|bolsa)[^\n.;]{0,20}(?:educa[cç][aã]o|estudo|faculdade|curso)\b"),
      ("Day off",r"\bday off\b")]
    for label,pat in mapping:
        if re.search(pat,text,re.I):benefits.append(label)
    return sal or "Não informado", benefits

def session():
    s=requests.Session()
    s.headers.update({"User-Agent":UA,"Accept-Language":"pt-BR,pt;q=0.9,en;q=0.7"})
    return s

def json_get(url,params=None,timeout=20):
    s=session(); r=s.get(url,params=params,timeout=timeout); r.raise_for_status(); return r.json()

def fetch_gupy(p):
    """Public endpoint used by Gupy's employability portal."""
    out=[]; seen=set()
    base="https://employability-portal.gupy.io/api/v1/jobs"
    for q in p.get("consultas_gupy",p.get("consultas_br",[])):
        for offset in (0,100):
            try:
                d=json_get(base,{"jobName":q,"limit":100,"offset":offset})
            except Exception:
                break
            items=d.get("data") or d.get("results") or d.get("jobs") or []
            if isinstance(items,dict): items=items.get("data",[]) or items.get("results",[])
            if not items: break
            for j in items:
                url=j.get("jobUrl") or j.get("url") or j.get("applyUrl") or ""
                jid=j.get("id") or j.get("jobId")
                if not url and jid:
                    url=f"https://portal.gupy.io/job-search"
                key=url or f"gupy:{jid}:{j.get('name')}"
                if key in seen:continue
                seen.add(key)
                wt_raw=j.get("workplaceType") or j.get("workplaceTypeLabel") or ""
                wt=norm(wt_raw)
                city=j.get("city") or ((j.get("address") or {}).get("city") if isinstance(j.get("address"),dict) else "")
                state=j.get("state") or ((j.get("address") or {}).get("state") if isinstance(j.get("address"),dict) else "")
                loc=", ".join(x for x in [city,state] if x) or j.get("location") or "Brasil"
                item={
                    "titulo":j.get("name") or j.get("title") or "",
                    "empresa":j.get("careerPageName") or j.get("companyName") or j.get("company") or "Não informado",
                    "local":loc,
                    "descricao":clean(j.get("description") or j.get("descriptionHtml") or j.get("requirements") or ""),
                    "url":url,"fonte":"Gupy",
                    "data_publicacao":str(j.get("publishedDate") or j.get("publicationDate") or "")[:10],
                    "salario":str(j.get("salary") or ""),
                    "remote":("remote" in wt or "remot" in wt),
                    "workplace_type":wt,
                    "workplace_type_raw":str(wt_raw),
                    "workplace_source":"structured" if wt else "",
                    "structured_location":j.get("address") or {"city":city,"state":state,"display":loc},
                    "applicant_location_requirements":j.get("applicantLocationRequirements") or "",
                    "source_brazil":True
                }
                if not early_date_allowed(item,p):
                    continue
                if p.get("enriquecer_somente_se_necessario",True) and url and needs_enrichment(item):
                    try:
                        extra=generic_job_from_url(url,"Gupy")
                        item=merge_job_data(item,extra,p)
                    except Exception:
                        pass
                out.append(item)
                if len(out)>=p.get("max_resultados_por_fonte",500):return out
            if len(items)<100:break
    return out

def linkedin_search_html(q,remote=False,location="Brazil"):
    params={"keywords":q,"location":location,"start":0}
    if remote: params["f_WT"]="2"
    url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"+urllib.parse.urlencode(params)
    s=session(); r=s.get(url,timeout=20); r.raise_for_status()
    return r.text

def fetch_linkedin(p):
    out=[];seen=set()
    terms=p.get("consultas_linkedin") or ["assistente jurídico","estágio jurídico",
           "assistente administrativo","atendimento","suporte técnico"]
    cities=p.get("cidades_presencial") or p.get("cidades_presencial_hibrido") or []
    state=(p.get("estado_local") or "").strip()
    local_query=", ".join(x for x in [cities[0] if cities else "Brazil",state,"Brazil"] if x)
    for q in terms:
        for remote,loc in [(True,"Brazil"),(False,local_query)]:
            try: html=linkedin_search_html(q,remote,loc)
            except Exception: continue
            soup=BeautifulSoup(html,"html.parser")
            cards=soup.select("li")
            for card in cards:
                a=card.select_one("a.base-card__full-link") or card.find("a",href=True)
                title=card.select_one(".base-search-card__title")
                company=card.select_one(".base-search-card__subtitle")
                location=card.select_one(".job-search-card__location")
                if not a or not title: continue
                url=(a.get("href") or "").split("?")[0]
                if not url or url in seen:continue
                seen.add(url)
                out.append({
                    "titulo":title.get_text(" ",strip=True),
                    "empresa":company.get_text(" ",strip=True) if company else "Não informado",
                    "local":location.get_text(" ",strip=True) if location else loc,
                    "descricao":"",
                    "url":url,"fonte":"LinkedIn",
                    "data_publicacao":"","salario":"",
                    # O filtro usado na pesquisa do LinkedIn é apenas uma pista de busca.
                    # Ele NÃO prova que o anúncio retornado seja remoto.
                    "remote":False,
                    "workplace_type":"",
                    "search_remote_hint":bool(remote),
                    "source_brazil":True
                })
                if len(out)>=200:return out
            time.sleep(.4)
    # No LinkedIn, a página da vaga é consultada para confirmar a modalidade.
    # Assim um resultado vindo de uma busca "remota" não vira remoto automaticamente.
    enriched=0
    initial_limit=max(0,int(p.get("enriquecimento_inicial_linkedin",0)))
    for j in out:
        if enriched>=initial_limit:break
        try:
            extra=generic_job_from_url(j["url"],"LinkedIn")
            merged=merge_job_data(j,extra,p)
            j.clear();j.update(merged);enriched+=1
        except Exception:
            LOGGER.exception("Falha ao enriquecer vaga do LinkedIn: %s",j.get("url",""))
    return out



def source_rank(name,p=None):
    name=norm(name)
    order=["gupy","linkedin","indeed/google","google","remotive"]
    if p:
        order=[norm(x) for x in p.get("fonte_prioridade",order)]
    for i,x in enumerate(order):
        if x and x in name:return i
    return 99

def field_missing(v):
    return norm(v) in ("","nao informado","não informado","brasil","brazil")

def needs_enrichment(job):
    return (
        field_missing(job.get("empresa")) or
        field_missing(job.get("local")) or
        len((job.get("descricao") or "").strip()) < 120 or
        not job.get("workplace_type")
    )

def merge_job_data(a,b,p):
    ra,rb=source_rank(a.get("fonte",""),p),source_rank(b.get("fonte",""),p)
    primary,other=(a,b) if ra<=rb else (b,a)
    out=dict(primary)

    for k in ("titulo","empresa","local","descricao","data_publicacao","valid_through","salario","workplace_type",
              "workplace_type_raw","workplace_source","structured_location","structured_location_json",
              "applicant_location_requirements"):
        pv=out.get(k)
        ov=other.get(k)
        if (field_missing(pv) or (k=="descricao" and len(str(pv or ""))<len(str(ov or "")))) and ov:
            out[k]=ov

    out["remote"]=bool(primary.get("remote") or other.get("remote"))
    out["source_brazil"]=bool(primary.get("source_brazil") or other.get("source_brazil"))

    fontes=[]
    for obj in (a,b):
        raw=obj.get("fontes_encontradas") or obj.get("fonte") or ""
        for f in str(raw).split(" + "):
            if f and f not in fontes:fontes.append(f)
    out["fontes_encontradas"]=" + ".join(fontes)
    out["fonte"]=primary.get("fonte") or other.get("fonte") or ""
    out["url"]=primary.get("url") or other.get("url") or ""
    return out

def dedupe_multisource(jobs,p):
    by_fp={};ordered=[]
    for j in jobs:
        fp=job_fingerprint(j)
        if not fp:
            j["fontes_encontradas"]=j.get("fonte","")
            ordered.append(j);continue
        if fp in by_fp:
            merged=merge_job_data(by_fp[fp],j,p)
            by_fp[fp].clear();by_fp[fp].update(merged)
        else:
            j["fontes_encontradas"]=j.get("fonte","")
            by_fp[fp]=j;ordered.append(j)
    return ordered

def early_date_allowed(job,p):
    ok,_=vacancy_date_ok(job,p)
    return ok

def generic_job_from_url(url,fonte="Google"):
    ttl=int(load_profile().get("cache_detalhes_horas",24))*3600
    cached=DETAIL_CACHE.get(url)
    if isinstance(cached,dict) and time.time()-cached.get("ts",0)<ttl:
        j=dict(cached.get("job") or {})
        if j:
            j["fonte"]=fonte
            return j

    s=session();original_url=url
    request_url=url
    if norm(fonte)=="linkedin":
        match=re.search(r"(?:currentJobId=|/jobs/view/(?:[^/?]*-)?)(\d{5,})",url)
        if match:
            request_url=f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{match.group(1)}"
    try:
        r=s.get(request_url,timeout=15,allow_redirects=True);r.raise_for_status()
    except Exception:
        if request_url==url:raise
        r=s.get(url,timeout=15,allow_redirects=True);r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    job={}

    # Modalidade explícita exibida no topo de páginas do LinkedIn.
    # Procuramos somente elementos cujo texto seja exatamente o selo da modalidade,
    # evitando confundir benefícios como "auxílio home office" com trabalho remoto.
    explicit_page_workplace=""
    if norm(fonte)=="linkedin":
        try:
            exact=[]
            for el in soup.find_all(["span","li","div"]):
                txt=clean(el.get_text(" ",strip=True))
                nt=norm(txt)
                if nt in ("presencial","on-site","onsite"):
                    exact.append("onsite")
                elif nt in ("hibrido","híbrido","hybrid"):
                    exact.append("hybrid")
                elif nt in ("remoto","remota","remote"):
                    exact.append("remote")
            # Presencial/híbrido têm prioridade se a página contiver termos conflitantes.
            if "onsite" in exact: explicit_page_workplace="onsite"
            elif "hybrid" in exact: explicit_page_workplace="hybrid"
            elif "remote" in exact: explicit_page_workplace="remote"
        except Exception:
            pass

    # 1) JSON-LD JobPosting é a fonte preferida.
    for tag in soup.find_all("script",type="application/ld+json"):
        try:
            d=json.loads(tag.string or "{}")
            candidates=[]
            if isinstance(d,list):candidates=d
            elif isinstance(d,dict):
                candidates=[d]
                if isinstance(d.get("@graph"),list):candidates+=d["@graph"]
            for x in candidates:
                if isinstance(x,dict) and x.get("@type")=="JobPosting":
                    job=x;break
            if job:break
        except Exception:pass

    title=job.get("title") if job else ""
    desc=clean(job.get("description","")) if job else ""
    company=""
    if job and isinstance(job.get("hiringOrganization"),dict):
        company=job["hiringOrganization"].get("name","")

    loc=""
    remote=False
    workplace_type=""
    if job:
        jlt_raw=job.get("jobLocationType") or ""
        jlt=norm(jlt_raw)
        remote=("telecommute" in jlt or "remote" in jlt)
        if remote:workplace_type="remote"
        elif "hybrid" in jlt or "hibrid" in jlt:workplace_type="hybrid"
        elif "onsite" in jlt or "on-site" in jlt or "presencial" in jlt:workplace_type="onsite"

        jl=job.get("jobLocation")
        if isinstance(jl,list):jl=jl[0] if jl else None
        if isinstance(jl,dict):
            addr=jl.get("address") or {}
            if isinstance(addr,dict):
                loc=", ".join(str(addr.get(k,"")) for k in
                    ("addressLocality","addressRegion","addressCountry") if addr.get(k))
        req=job.get("applicantLocationRequirements")
        if req and not loc:loc=clean(req)

    # No LinkedIn, o selo visível de modalidade é mais específico que a pista da busca.
    if explicit_page_workplace:
        workplace_type=explicit_page_workplace
        remote=(explicit_page_workplace=="remote")

    # 2) Fallbacks de metadados/HTML.
    if not title:
        og=soup.find("meta",property="og:title")
        title=(og.get("content","") if og else "") or (soup.title.get_text(" ",strip=True) if soup.title else "")
    if not desc:
        main=soup.find("main") or soup.body
        desc=main.get_text(" ",strip=True)[:12000] if main else ""
    if not company:
        company_meta=soup.find("meta",{"name":"author"})
        company=company_meta.get("content","") if company_meta else "Não informado"

    salary=""
    if job and job.get("baseSalary"):
        salary=clean(json.dumps(job.get("baseSalary"),ensure_ascii=False))

    workplace_source="page_badge" if explicit_page_workplace else "structured" if workplace_type else ""
    result={
        "titulo":title[:220],"empresa":company[:160],"local":loc or "Não informado",
        "descricao":desc,"url":original_url,"fonte":fonte,
        "data_publicacao":str(job.get("datePosted","") if job else "")[:10],
        "valid_through":str(job.get("validThrough","") if job else "")[:25],
        "salario":salary,"remote":remote,"workplace_type":workplace_type,"workplace_source":workplace_source,
        "workplace_type_raw":str(job.get("jobLocationType") or explicit_page_workplace or "") if job else explicit_page_workplace,
        "structured_location_json":compact_json(job.get("jobLocation") if job else ""),
        "applicant_location_requirements":compact_json(job.get("applicantLocationRequirements") if job else ""),
        "source_brazil":False
    }

    # Salva tanto pela URL original quanto pela URL final.
    payload={"ts":time.time(),"job":result}
    with CACHE_LOCK:
        DETAIL_CACHE[url]=payload
        DETAIL_CACHE[r.url]=payload
        # Evita cache crescer indefinidamente.
        if len(DETAIL_CACHE)>1500:
            oldest=sorted(DETAIL_CACHE.items(),key=lambda kv:kv[1].get("ts",0))[:300]
            for k,_ in oldest:DETAIL_CACHE.pop(k,None)
        save_json_file(CACHE_PATH,DETAIL_CACHE)
    return result

def google_urls(query,n=10):
    # Low-volume Google discovery. Google can occasionally throttle automated queries.
    from googlesearch import search
    try:
        return list(search(query,num_results=n,lang="pt",sleep_interval=1.5))
    except TypeError:
        return list(search(query,num=n,stop=n,pause=1.5))

def fetch_google(p,site=None,source_name="Google"):
    out=[];seen=set()
    cv_queries=p.get("consultas_gupy") or p.get("consultas_br") or []
    queries=p.get("consultas_google") or [f'"{q}" vagas Brasil' for q in cv_queries[:6]]
    if not queries:return out
    if site:
        queries=[f"site:{site} "+q for q in queries]
    # Google é complementar: menos URLs, mais qualidade, sem repetir dezenas de sinônimos.
    for q in queries:
        try:urls=google_urls(q,7)
        except Exception:continue
        for u in urls:
            base=u.split("?")[0]
            if base in seen:continue
            seen.add(base)
            try:j=generic_job_from_url(u,source_name)
            except Exception:continue
            if not early_date_allowed(j,p):continue
            out.append(j)
            if len(out)>=60:return out
    return out

def fetch_remotive(p):
    out=[]
    try:
        d=json_get("https://remotive.com/api/remote-jobs",{"search":"Brazil"})
        for j in d.get("jobs",[]):
            out.append({"titulo":j.get("title",""),"empresa":j.get("company_name",""),
             "local":j.get("candidate_required_location",""),"descricao":clean(j.get("description","")),
             "url":j.get("url",""),"fonte":"Remotive","data_publicacao":str(j.get("publication_date",""))[:10],
             "salario":j.get("salary","") or "","remote":True,"workplace_type":"remote",
             "workplace_type_raw":"remote","workplace_source":"source_api",
             "structured_location":{"candidate_required_location":j.get("candidate_required_location","")},
             "applicant_location_requirements":j.get("candidate_required_location",""),"source_brazil":False})
    except Exception:
        LOGGER.exception("Falha ao buscar vagas na Remotive")
    return out


def job_fingerprint(job):
    title=norm(job.get("titulo",""))
    company=norm(job.get("empresa",""))
    loc=norm(job.get("local",""))
    # Remove apenas ruídos de apresentação. Senioridade é preservada para não
    # fundir, por exemplo, uma vaga Júnior com outra Pleno da mesma empresa.
    title=re.sub(r"\b(remoto|remote|hibrido|presencial|home office)\b","",title)
    title=re.sub(r"\s*[-–—|/]\s*$","",title)
    title=re.sub(r"\s+"," ",title).strip()
    company=re.sub(r"\b(s\.?a\.?|ltda\.?|eireli|inc\.?|llc|corp\.?|corporation)\b\.?$","",company).strip(" -.,")
    if company and company not in ("nao informado","confidencial","confidential"):
        return f"{title}|{company}"
    if loc and loc!="nao informado":
        return f"{title}|{loc}"
    return ""

def is_intern(job):
    x=norm(job.get("titulo","")+" "+job.get("descricao",""))
    return any(k in x for k in ["estagio","estagiario","intern ","internship"])

def internship_area_ok(job,p):
    """Confirma estágio usando os cursos e termos derivados do currículo."""
    title=norm(job.get("titulo",""))
    desc=norm(job.get("descricao",""))
    text=title+" "+desc

    courses=profile_courses(p)
    if courses:
        return any(course in text or any(token in text for token in course.split() if len(token)>=5)
                   for course in courses)
    areas=p.get("areas_estagio",{})
    if isinstance(areas,list):
        # Compatibilidade com perfis antigos.
        return any(norm(k) in text for k in areas)

    legal=[norm(x) for x in areas.get("direito",[])]
    legal += [norm(x) for x in p.get("cargos_juridicos_amplos",[])]
    ads=[norm(x) for x in areas.get("ads_ti",[])]

    legal_hit=any(re.search(r"(?<!\w)"+re.escape(x)+r"(?!\w)",text) for x in legal if x)
    ads_hit=any(re.search(r"(?<!\w)"+re.escape(x)+r"(?!\w)",text) for x in ads if x)

    # Evita falsos positivos de "TI/IT" como pedaço de outra palavra:
    # os regex com boundaries acima já reduzem bastante isso.
    return legal_hit or ads_hit


def legal_evidence(job,p):
    title=norm(job.get("titulo",""))
    desc=norm(job.get("descricao",""))
    text=title+" "+desc
    titles=[norm(x) for x in p.get("cargos_juridicos_amplos",[])]

    if any(x and x in title for x in titles):
        return True

    legal_terms=[
        "juridico","juridica","legal operations","legal ops","paralegal",
        "controladoria juridica","contencioso","processual","processo judicial",
        "processos judiciais","prazo processual","prazos processuais","publicacoes",
        "intimacoes","peticoes","recursos","diligencias","protocolo judicial",
        "acompanhamento processual","andamento processual","carteira processual",
        "pje","eproc","esaj","e-saj","projudi","tribunal","foro","comarca",
        "contratos juridicos","departamento juridico","escritorio de advocacia",
        "advocacia","compliance juridico","regulatorio juridico"
    ]
    hits=sum(1 for x in legal_terms if x in text)
    return hits>=2 or any(x in title for x in [
        "jurid","paralegal","legal ops","legal operations","contencioso",
        "processual","controladoria","controller jurid"
    ])


def job_category(job,p):
    if is_intern(job):
        cs=internship_course_status(job,p)
        if cs=="OK_PERFIL":return "Estágio compatível"
        if cs=="REVISAR":return "Estágio — verificar curso"
        return "Estágio fora da área"
    if legal_evidence(job,p):return "Jurídico"
    text=norm((job.get("titulo","") or "")+" "+(job.get("descricao","") or ""))
    if any(x in text for x in ["suporte n1","suporte tecnico","help desk","service desk",
                               "analista de suporte","implantacao","tecnologia da informacao","software"]):
        return "Geral — Tecnologia/Suporte"
    return "Geral"

def relevant_to_profile(job,p):
    title=norm(job.get("titulo",""))
    desc=norm(job.get("descricao",""))
    text=title+" "+desc

    if is_intern(job):
        return internship_area_ok(job,p)

    # Cargos/áreas diretamente compatíveis com o histórico e competências do perfil.
    legal_titles=[norm(x) for x in p.get("cargos_juridicos_amplos",[])]
    if any(x and x in title for x in legal_titles):
        return True

    title_clusters=[
        # administrativo / operações
        ["assistente administrativo","auxiliar administrativo","analista administrativo",
         "assistente operacional","assistente de operacoes","analista de operacoes",
         "backoffice","assistente de backoffice","cadastro","documentacao","contratos",
         "faturamento","assistente financeiro","auxiliar financeiro"],
        # atendimento / CX
        ["atendimento","customer service","customer support","customer experience",
         "customer success","suporte ao cliente","sac","ouvidoria","reclame aqui"],
        # jurídico
        ["assistente juridico","auxiliar juridico","paralegal","legal operations",
         "juridico","compliance"],
        # tecnologia de entrada
        ["suporte n1","suporte tecnico","help desk","service desk",
         "analista de suporte","assistente de suporte"]
    ]
    if any(any(term in title for term in cluster) for cluster in title_clusters):
        return True

    # Para títulos menos óbvios, exige evidência real na descrição.
    skills=profile_skills(p)
    relevant=profile_terms(p)
    skill_hits=sum(1 for x in skills if x and x in desc)
    relevance_hits=sum(1 for x in relevant if x and x in desc)

    # Uma vaga genérica só entra se conversar de verdade com várias competências.
    return skill_hits>=3 or (skill_hits>=2 and relevance_hits>=2)


def location_decision(job,p):
    loc=norm(job.get("local",""))
    title=norm(job.get("titulo",""))
    desc=norm(job.get("descricao",""))
    workplace=norm(job.get("workplace_type",""))

    allowed=[norm(x) for x in p.get("cidades_presencial",p.get("cidades_presencial_hibrido",[]))]
    default_uf=norm(p.get("estado_local","")).upper()
    uf_names={"AC":"acre","AL":"alagoas","AP":"amapa","AM":"amazonas","BA":"bahia","CE":"ceara",
              "DF":"distrito federal","ES":"espirito santo","GO":"goias","MA":"maranhao","MT":"mato grosso",
              "MS":"mato grosso do sul","MG":"minas gerais","PA":"para","PB":"paraiba","PR":"parana",
              "PE":"pernambuco","PI":"piaui","RJ":"rio de janeiro","RN":"rio grande do norte",
              "RS":"rio grande do sul","RO":"rondonia","RR":"roraima","SC":"santa catarina",
              "SP":"sao paulo","SE":"sergipe","TO":"tocantins"}
    location_parts=[part.strip() for part in re.split(r"\s*[,/|]\s*|\s+-\s+",loc) if part.strip()]
    published_city=location_parts[0] if location_parts else ""
    published_region=" ".join(location_parts[1:])
    def allowed_city(entry):
        bits=[part.strip() for part in entry.rsplit("/",1)]
        city=bits[0];uf=(bits[1].upper() if len(bits)==2 else default_uf)
        if published_city!=city:return False
        if not uf:return True
        return bool(re.search(rf"\b{re.escape(uf.lower())}\b",published_region) or
                    re.search(rf"\b{re.escape(uf_names.get(uf,''))}\b",published_region))
    local_allowed=any(city and allowed_city(city) for city in allowed)

    generic_locations={
        "","brasil","brazil","remoto","remota","remote","home office","anywhere",
        "latam","latin america","america latina","worldwide","nao informado","não informado"
    }
    loc_generic=loc in generic_locations

    uf_names=[
        "acre","alagoas","amapa","amazonas","bahia","ceara","distrito federal","espirito santo",
        "goias","maranhao","mato grosso","mato grosso do sul","minas gerais","para","paraiba",
        "parana","pernambuco","piaui","rio de janeiro","rio grande do norte","rio grande do sul",
        "rondonia","roraima","santa catarina","sao paulo","sergipe","tocantins"
    ]
    uf_abbr=r"(?:ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)"
    explicit_br_location=(
        bool(re.search(rf"\b[a-zà-ÿ][a-zà-ÿ .'-]+[,/ -]\s*{uf_abbr}\b",loc))
        or any(re.search(rf"\b{re.escape(state)}\b",loc) for state in uf_names)
    )

    scope_text=loc+" "+desc[:4500]
    remote_scope_allowed=(
        explicit_br_location or local_allowed or
        bool(re.search(r"\b(brasil|brazil|latam|latin america|america latina|worldwide|anywhere)\b",loc)) or
        bool(re.search(
            r"\b(candidat[oa]s? (?:do|de|no|em) brasil|candidates? (?:in|from) brazil|"
            r"work from brazil|trabalh(?:ar|e) (?:do|no|em) brasil|"
            r"(?:open to|available (?:in|for)) (?:brazil|latam|latin america)|"
            r"latam|latin america|america latina|worldwide|work from anywhere|trabalhe de qualquer lugar)\b",
            scope_text))
    )

    def verify(evidence="dados insuficientes",confidence="Baixa"):
        return {"mode":"Verificar modelo","ok":True,"confidence":confidence,"evidence":evidence}

    def confirmed_remote(evidence,confidence):
        if remote_scope_allowed:
            return {"mode":"Remoto Brasil — confirmado","ok":True,"confidence":confidence,"evidence":evidence}
        if loc_generic:
            return verify("remoto confirmado; disponibilidade para o Brasil não informada","Baixa")
        return {"mode":"Remoto sem disponibilidade para o Brasil","ok":False,
                "confidence":confidence,"evidence":evidence+"; localização incompatível"}

    def confirmed_local(kind,evidence,confidence):
        if local_allowed:
            return {"mode":f"{kind} — confirmado","ok":True,"confidence":confidence,"evidence":evidence}
        if not loc or loc_generic:
            return verify(f"{kind.lower()} confirmado; local não informado","Baixa")
        return {"mode":f"{kind} fora da região","ok":False,"confidence":confidence,"evidence":evidence}

    # Evidências estruturadas são soberanas.
    # search_remote_hint e o booleano legado remote são deliberadamente ignorados:
    # eles podem vir apenas do filtro usado na pesquisa e não provam a modalidade da vaga.
    sr=any(x in workplace for x in ["remote","remoto","telecommute"])
    sh=any(x in workplace for x in ["hybrid","hibrid"])
    so=any(x in workplace for x in ["onsite","on-site","presencial"])

    if sum(bool(x) for x in (sr,sh,so))>1:
        return verify("workplace_type conflitante")

    if sh:
        return confirmed_local("Híbrido","workplace_type","Alta")
    if so:
        return confirmed_local("Presencial","workplace_type","Alta")
    if sr:
        return confirmed_remote("workplace_type/localização","Alta")

    # Título e local publicados pela vaga são evidência explícita, mas nunca usamos a consulta.
    tl=title+" "+loc
    explicit_hybrid=bool(re.search(r"\b(hibrid[oa]|hybrid)\b",tl))
    explicit_onsite=bool(re.search(r"\b(presencial|on[- ]?site|onsite)\b",tl))
    explicit_remote=bool(re.search(r"\b(100% remoto|100% remota|fully remote|remote[- ]only|remoto|remota|remote)\b",tl))

    if explicit_hybrid or explicit_onsite:
        if explicit_remote:
            return verify("título/local conflitante")
        if explicit_hybrid:
            return confirmed_local("Híbrido","título/local","Alta")
        return confirmed_local("Presencial","título/local","Alta")

    if explicit_remote:
        return confirmed_remote("título/local","Alta")

    # Descrição: só frases de modalidade, nunca a palavra isolada "home office".
    head=desc[:4500]
    d_hybrid=bool(re.search(
        r"\b(modelo hibrid[oa]|regime hibrid[oa]|modalidade hibrid[oa]|trabalho hibrid[oa]|"
        r"atuacao hibrida|atuação híbrida|[1-5]\s+dias?\s+(?:por semana\s+)?(?:no|em)\s+escritorio)\b",head))
    d_onsite=bool(re.search(
        r"\b(100% presencial|modelo presencial|regime presencial|modalidade presencial|"
        r"trabalho presencial|atuacao presencial|atuação presencial|atuar presencialmente|"
        r"trabalho no local)\b",head))
    d_remote=bool(re.search(
        r"\b(100% remoto|100% remota|totalmente remoto|totalmente remota|fully remote|"
        r"remote[- ]only|modelo (?:de trabalho )?remoto|regime remoto|modalidade remota?|"
        r"trabalho 100% remoto|atuacao 100% remota?|atuação 100% remota?|"
        r"trabalhe de qualquer lugar|work from anywhere|trabalho remoto integral)\b",head))

    # Presencial/híbrido explícitos têm precedência. Contradição não vira remoto.
    if d_hybrid or d_onsite:
        if d_remote:
            return verify("descrição conflitante")
        if d_hybrid:
            return confirmed_local("Híbrido","descrição","Média")
        return confirmed_local("Presencial","descrição","Média")

    if d_remote:
        return confirmed_remote("descrição","Média")

    if not desc.strip():
        if local_allowed:return verify("local compatível informado; descrição e modalidade ausentes")
        if loc_generic:return verify("localização genérica; descrição e modalidade ausentes")
        return verify("local informado; descrição e modalidade ausentes")
    if local_allowed:return verify("local compatível informado; descrição não declara a modalidade","Média")
    if loc_generic:return verify("descrição não declara a modalidade; localização genérica")
    return verify("local informado; descrição não declara a modalidade","Média")

def location_mode(job,p):
    d=location_decision(job,p)
    return d["mode"],d["ok"]

def closed_job_reason(text):
    t=norm(text)
    phrases=[
        "vaga encerrada","vaga finalizada","vaga fechada","processo seletivo encerrado",
        "processo seletivo finalizado","inscricoes encerradas","inscrições encerradas",
        "candidaturas encerradas","nao aceita mais candidaturas","não aceita mais candidaturas",
        "nao estamos mais aceitando candidaturas","não estamos mais aceitando candidaturas",
        "esta vaga nao esta mais disponivel","esta vaga não está mais disponível",
        "vaga indisponivel","vaga indisponível","oportunidade encerrada",
        "job is no longer available","job no longer available","no longer accepting applications",
        "applications are closed","applications closed","position has been filled",
        "this job has expired","job expired","posting has expired"
    ]
    for ph in phrases:
        if norm(ph) in t:return ph
    return ""

def expired_job_reason(job):
    """Aceita somente evidência explícita de encerramento ou data-limite vencida."""
    text=(job.get("titulo","") or "")+" "+(job.get("descricao","") or "")
    reason=closed_job_reason(text)
    if reason:return reason
    raw=str(job.get("valid_through","") or "").strip()
    if not raw:return ""
    try:
        limit=datetime.fromisoformat(raw.replace("Z","+00:00")).date()
    except Exception:
        try:limit=datetime.strptime(raw[:10],"%Y-%m-%d").date()
        except Exception:return ""
    return "data limite de candidatura encerrada" if limit<datetime.now().date() else ""

def requires_completed_higher_education(text):
    """
    Hard-discard only explicit completed-degree requirements.
    Do not discard 'cursando', 'completo ou cursando', or merely desirable/preferred degrees.
    """
    t=norm(text)
    if not t:return False,""
    # Explicit alternatives that the current profile can satisfy.
    alternatives=[
        "superior completo ou cursando","superior cursando ou completo",
        "graduacao completa ou cursando","graduacao cursando ou completa",
        "ensino superior completo ou em andamento","ensino superior em andamento ou completo",
        "superior em andamento","graduacao em andamento"
    ]
    if any(x in t for x in alternatives):
        return False,""

    patterns=[
        r"\bensino\s+superior\s+complet[oa]\b",
        r"\bsuperior\s+complet[oa]\b",
        r"\bgraduacao\s+complet[oa]\b",
        r"\bcurso\s+superior\s+complet[oa]\b",
        r"\bformacao\s+superior\s+complet[oa]\b",
        r"\bformacao\s+academica\s*:\s*superior\s+complet[oa]\b",
        r"\bbachelor(?:'s)?\s+degree\s+(?:is\s+)?required\b",
        r"\bcompleted\s+bachelor(?:'s)?\s+degree\b"
    ]
    for pat in patterns:
        m=re.search(pat,t)
        if not m:continue
        left=t[max(0,m.start()-90):m.start()]
        # If clearly optional/preferred, don't hard discard.
        if any(x in left for x in ["desejavel","diferencial","preferencial","preferivel","preferred","nice to have"]):
            continue
        return True,m.group(0)
    return False,""

def live_page_invalid_reason(page):
    """Check the opened vacancy page immediately before preparing an application."""
    try:
        body=page.locator("body").inner_text(timeout=8000)
    except:
        return ""
    reason=closed_job_reason(body)
    if reason:return "vaga encerrada/finalizada"
    req,phrase=requires_completed_higher_education(body)
    if req:return "exige ensino superior completo"
    if load_profile().get("descartar_vagas_exclusivas_pcd",True):
        pcd_reason=pcd_exclusive_reason(body)
        if pcd_reason:return pcd_reason
    return ""

def parse_monthly_salary(raw,desc=""):
    text=norm((raw or "")+" "+(desc or "")[:3500])
    vals=[]
    for m in re.finditer(r"(?:r\$|brl)\s*([\d\.\,]+)",text):
        try:
            v=float(m.group(1).replace(".","").replace(",","."))
            if 500<=v<=100000:vals.append(v)
        except:pass
    if vals:return min(vals)
    return None


def pcd_exclusive_reason(text):
    """Descarta somente exclusividade PCD explícita, evitando textos genéricos de diversidade."""
    raw=text or ""
    t=norm(raw)
    # Analisa principalmente o começo do anúncio, onde título/cabeçalho/requisito afirmativo aparecem.
    head=t[:1800]
    patterns=[
        r"\bvaga\s+exclusiva\s+(?:para\s+)?pcd\b",
        r"\bvaga\s+exclusiva\s+(?:para\s+)?pessoas?\s+com\s+deficiencia\b",
        r"\boportunidade\s+exclusiva\s+(?:para\s+)?pcd\b",
        r"\bprocesso\s+seletivo\s+exclusivo\s+(?:para\s+)?pcd\b",
        r"\bvaga\s+afirmativa\s+(?:para\s+)?pcd\b",
        r"\boportunidade\s+afirmativa\s+(?:para\s+)?pcd\b",
        r"\bexclusiv[ao]\s+(?:para\s+)?pcd\b",
        r"\bsomente\s+(?:para\s+)?pcd\b",
        r"\bapenas\s+(?:para\s+)?pcd\b",
        r"\breservad[ao]\s+exclusivamente\s+(?:para\s+)?pcd\b",
        r"\bdestinad[ao]\s+exclusivamente\s+(?:a|para)\s+(?:pcd|pessoas?\s+com\s+deficiencia)\b"
    ]
    return "vaga exclusiva/afirmativa para PCD" if any(re.search(x,head) for x in patterns) else ""


def publication_age_days(job):
    """Calcula a idade da publicação; retorna None quando a fonte é ambígua."""
    raw=(job.get("data_publicacao","") or "").strip()
    if not raw:
        return None

    t=norm(raw)
    today=datetime.now().date()
    age=None

    if any(x in t for x in ["hoje","today","agora","just now"]):
        age=0
    elif any(x in t for x in ["ontem","yesterday"]):
        age=1
    else:
        m=re.search(r"(\d+)\s*(?:dia|dias|day|days)\b",t)
        if m:
            age=int(m.group(1))
        if age is None:
            m=re.search(r"(\d+)\s*(?:semana|semanas|week|weeks)\b",t)
            if m: age=int(m.group(1))*7
        if age is None:
            m=re.search(r"(\d+)\s*(?:mes|meses|month|months)\b",t)
            if m: age=int(m.group(1))*30

    if age is None:
        candidates=[
            "%Y-%m-%dT%H:%M:%S.%fZ","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%d.%m.%Y"
        ]
        cleaned=raw.strip()
        for fmt in candidates:
            try:
                dt=datetime.strptime(cleaned[:26] if "%f" in fmt else cleaned[:19] if "T" in fmt else cleaned[:10],fmt)
                age=max(0,(today-dt.date()).days)
                break
            except Exception:
                pass

    # Data que não conseguimos interpretar não elimina a vaga.
    if age is None:
        return None

    return age

def vacancy_date_ok(job,p):
    """Retorna (aceita, idade_em_dias). Datas desconhecidas são mantidas."""
    age=publication_age_days(job)
    if age is None:return True,None

    max_days=int(p.get("idade_maxima_vaga_dias",60))
    return age<=max_days,age


def mandatory_blocker(job,p):
    """Barreiras objetivas; evita descartar por mera preferência/diferencial."""
    text=norm((job.get("titulo","") or "")+" "+(job.get("descricao","") or ""))
    title=norm(job.get("titulo","") or "")

    optional=("desejavel","diferencial","preferencial","preferred","nice to have")
    def optional_near(pos):
        return any(x in text[max(0,pos-90):pos] for x in optional)

    # Advocacia/OAB.
    for pat in [r"\boab\s+ativa\b",r"\binscricao\s+(?:ativa\s+)?na\s+oab\b",
                r"\bregistro\s+(?:ativo\s+)?na\s+oab\b",r"\boab\s+obrigatoria\b"]:
        m=re.search(pat,text)
        if m and not optional_near(m.start()):
            return "OAB ativa/obrigatória"

    if re.search(r"\badvogad[oa]\b",title):
        return "cargo de advogado/OAB"

    # Senioridade inequívoca.
    senior=r"\b(senior|sr\.?|especialista|coordenador(?:a)?|gerente|supervisor(?:a)?|head|lead)\b"
    subordinate=bool(re.search(
        r"\b(assistente|auxiliar|secretari[oa])\s+(?:do|da|de)\s+"
        r"(coordenador(?:a)?|gerente|supervisor(?:a)?|head|lead)\b",title))
    if re.search(senior,title) and not subordinate:
        return "senioridade/cargo acima do perfil"

    # Experiência específica longa e explicitamente requerida.
    for m in re.finditer(r"(?:minimo|minima|pelo menos|at least|minimum of)?\s*(\d+)\s*(?:anos|years)\s+(?:de\s+)?experiencia",text):
        try:
            yrs=int(m.group(1))
            context=text[max(0,m.start()-80):m.end()+80]
            if yrs>20 or any(x in context for x in ["empresa","mercado","historia","fundada"]):
                continue
            if yrs>=int(p.get("descartar_experiencia_especifica_anos",5)) and not optional_near(m.start()):
                return f"exige {yrs}+ anos de experiência"
        except: pass

    # Inglês fluente obrigatório.
    m=re.search(r"\b(ingles fluente|fluent english|english fluency|ingles avancado obrigatorio)\b",text)
    if m and not optional_near(m.start()):
        return "inglês fluente obrigatório"

    return ""

def internship_course_status(job,p=None):
    """Retorna OK_PERFIL, FORA ou REVISAR sem presumir uma formação fixa."""
    text=norm((job.get("titulo","") or "")+" "+(job.get("descricao","") or ""))
    if not is_intern(job): return ""

    if p:
        courses=profile_courses(p)
        if courses:
            for course in courses:
                significant=[token for token in course.split() if len(token)>=4]
                if course in text or (significant and sum(token in text for token in significant)>=max(1,len(significant)//2)):
                    return "OK_PERFIL"
            if re.search(r"\b(cursando|curso|graduacao|formacao|estudante|semestre|periodo)\b",text):
                return "FORA"
            return "REVISAR"

    legal=["direito","curso de direito","graduacao em direito","bacharelado em direito"]
    ads=["analise e desenvolvimento de sistemas","sistemas de informacao","ciencia da computacao",
         "engenharia de software","tecnologia da informacao","computacao","desenvolvimento de sistemas",
         "ads"]
    outside=["administracao","ciencias contabeis","contabilidade","recursos humanos","gestao de rh",
             "marketing","publicidade","engenharia civil","engenharia mecanica","pedagogia",
             "psicologia","farmacia","enfermagem","arquitetura"]

    course_context=bool(re.search(r"\b(cursando|curso|graduacao|formacao|estudante|semestre|periodo)\b",text))
    if any(x in text for x in legal+ads) or re.search(r"(?<!\w)ti(?!\w)",text): return "OK_PERFIL"
    if course_context and any(x in text for x in outside): return "FORA"
    return "REVISAR"

def collection_confidence(job):
    company=norm(job.get("empresa",""))
    loc=norm(job.get("local",""))
    desc=(job.get("descricao","") or "").strip()
    if company not in ("","nao informado") and loc not in ("","nao informado") and len(desc)>=250:
        return "Alta"
    if len(desc)>=180 and (company not in ("","nao informado") or loc not in ("","nao informado")):
        return "Média"
    return "Baixa"


def decision_level(job,p,mode):
    if is_intern(job) and internship_course_status(job,p)=="REVISAR":
        return "REVISAR"
    ld=location_decision(job,p)
    if "conflitante" in norm(ld["mode"]):
        return "REVISAR"
    if ld["confidence"]=="Baixa":
        return "REVISAR"
    if "confirmar" in norm(ld["mode"]) or "nao confirmados" in norm(ld["mode"]):
        return "REVISAR"
    if collection_confidence(job)=="Baixa":
        return "REVISAR"
    return "APROVADA"

def hard_filter(job,p):
    date_ok,age_days=vacancy_date_ok(job,p)
    if not date_ok:
        return False,f"vaga antiga ({age_days} dias)" if age_days is not None else "vaga antiga"

    text=(job.get("titulo","") or "")+" "+(job.get("descricao","") or "")
    if p.get("descartar_vagas_encerradas",True):
        reason=expired_job_reason(job)
        if reason:return False,"vaga encerrada/finalizada"

    if p.get("descartar_vagas_exclusivas_pcd",True):
        reason=pcd_exclusive_reason(text)
        if reason:return False,reason

    blocker=mandatory_blocker(job,p)
    if blocker:return False,blocker

    if p.get("descartar_superior_completo_obrigatorio",True):
        req,phrase=requires_completed_higher_education(text)
        if req:return False,"exige ensino superior completo"

    if is_intern(job) and not p.get("buscar_estagios",True):
        return False,"estágio desativado pelo usuário"

    if is_intern(job):
        cs=internship_course_status(job,p)
        if cs=="FORA":
            text=norm((job.get("titulo","") or "")+" "+(job.get("descricao","") or ""))
            detected="outro curso"
            mapa=[
                ("ciencias contabeis","Ciências Contábeis"),("contabilidade","Contabilidade"),
                ("administracao","Administração"),("recursos humanos","Recursos Humanos"),
                ("marketing","Marketing"),("publicidade","Publicidade"),
                ("engenharia civil","Engenharia Civil"),("engenharia mecanica","Engenharia Mecânica"),
                ("psicologia","Psicologia"),("pedagogia","Pedagogia"),
                ("enfermagem","Enfermagem"),("arquitetura","Arquitetura")
            ]
            for token,label in mapa:
                if token in text:
                    detected=label;break
            return False,f"estágio fora da formação identificada — {detected}"

    mode,ok=location_mode(job,p)
    if not ok:return False,mode

    return True,mode

def score_job(job,p,cv):
    title=norm(job.get("titulo",""));desc=norm(job.get("descricao",""));allx=title+" "+desc
    parts=[];score=30

    terms=profile_terms(p)
    th=sum(1 for x in terms if x in title)
    dh=sum(1 for x in terms if x in desc)
    cargo=min(25,th*10+dh*2)
    score+=cargo
    if cargo:parts.append(f"Cargo/área +{cargo}")

    skills=set(x for x in profile_skills(p) if x in allx)
    comp=min(22,len(skills)*3)
    score+=comp
    if comp:parts.append(f"Competências +{comp}")

    feedback=p.get("feedback_preferencias",{})
    preference=sum(max(-2,min(2,int(feedback.get(token,0)))) for token in feedback_tokens(allx))
    preference=max(-6,min(6,preference))
    if preference:
        score+=preference;parts.append(f"Preferências {preference:+d}")

    area_hits=sum(1 for area in p.get("areas_curriculo_detectadas",[]) if norm(area) in allx)
    if area_hits:
        bonus=min(12,area_hits*6);score+=bonus;parts.append(f"Área do currículo +{bonus}")

    age=publication_age_days(job)
    freshness=5 if age is not None and age<=3 else 3 if age is not None and age<=7 else 1 if age is not None and age<=14 else 0
    if freshness:
        score+=freshness;parts.append(f"Publicação recente +{freshness}")

    if is_intern(job):
        cs=internship_course_status(job,p)
        if cs=="OK_PERFIL":
            score+=8;parts.append("Estágio compatível +8")

    ld=location_decision(job,p);mode=ld["mode"]
    if "Remoto Brasil" in mode:
        score+=10;parts.append("Remoto elegível +10")
    elif "Local permitido" in mode or "confirmado" in mode:
        score+=7;parts.append("Local/modalidade +7")
    if ld["confidence"]=="Baixa":
        score-=8;parts.append("Local/modalidade incertos -8")

    subordinate=bool(re.search(
        r"\b(assistente|auxiliar|secretari[oa])\s+(?:do|da|de)\s+"
        r"(coordenador(?:a)?|gerente|supervisor(?:a)?|head|lead)\b",title))
    if re.search(r"\b(pleno|senior|sr\.?|especialista|coordenador|coordenadora|gerente|lead|head)\b",title) and not subordinate:
        score-=25;parts.append("Senioridade -25")

    yrs=[int(x) for x in re.findall(r"(\d+)\+?\s*(?:anos|years)\s+(?:de\s+)?(?:experiencia|experience)",desc)]
    if yrs:
        req=max(yrs)
        if req>=5:
            score-=35;parts.append(f"Experiência {req}+ anos -35")
        elif req>=3:
            score-=15;parts.append(f"Experiência {req}+ anos -15")

    conf=collection_confidence(job)
    if conf=="Baixa":
        score-=8;parts.append("Dados incompletos -8")
    elif conf=="Alta":
        score+=3;parts.append("Dados completos +3")

    score=max(0,min(100,score))
    label="Excelente" if score>=85 else "Boa" if score>=70 else "Possível" if score>=55 else "Incompatível"
    reason="Base +30" + ((" | "+" | ".join(parts)) if parts else "")
    return score,label,reason,mode

def curriculum_compatibility(job,p,cv):
    """Usa a mesma régua explicável da lista principal sem alterar a vaga."""
    return score_job(job,p,cv)[0]

def keep_compatible_outside_region(job,p,cv,reason):
    # Compatibilidade é exibida dentro de Fora do perfil, mas nunca recoloca uma
    # vaga presencial/híbrida externa na lista principal.
    return False

def extract_requirements(job):
    text=norm(job.get("titulo","")+" "+job.get("descricao",""))
    req=[]
    if re.search(r"\bexcel\b",text): req.append(("Excel","excel"))
    if any(x in text for x in ["pacote office","microsoft office"]): req.append(("Pacote Office","office"))
    if any(x in text for x in ["atendimento ao cliente","customer service","customer support"]): req.append(("Atendimento ao cliente","atendimento"))
    if any(x in text for x in ["help desk","service desk","suporte tecnico","suporte técnico"]): req.append(("Suporte/Service Desk","suporte"))
    if any(x in text for x in ["juridico","jurídico","direito","legal operations"]): req.append(("Área jurídica","juridico"))
    if any(x in text for x in ["processos administrativos","rotinas administrativas","administrativo"]): req.append(("Rotinas administrativas","administrativo"))
    if any(x in text for x in ["ingles fluente","inglês fluente","fluent english","native english"]): req.append(("Inglês fluente","ingles_fluente"))
    yrs=[int(x) for x in re.findall(r"(\d+)\+?\s*(?:anos|years)\s+(?:de\s+)?(?:experiencia|experience)",text)]
    if yrs:req.append((f"{max(yrs)}+ anos de experiência específica",f"anos:{max(yrs)}"))
    if any(x in text for x in ["senior","sênior","sr.","tier iii","tier 3","lead","manager","gerente","coordenador"]):
        req.append(("Senioridade elevada","senioridade"))
    return req

def requirement_report(job,p,cv):
    cvn=norm(cv)
    met=[];unknown=[];notmet=[]
    for label,key in extract_requirements(job):
        if key=="ingles_fluente":
            notmet.append(label)
        elif key=="senioridade":
            notmet.append(label)
        elif key.startswith("anos:"):
            n=int(key.split(":")[1])
            # General professional history is long, but do not claim same-specialty years unless explicit.
            if n>=5:notmet.append(label)
            elif n>=3:unknown.append(label)
            else:met.append(label)
        elif key=="excel":
            if "excel" in cvn:met.append(label)
            else:unknown.append(label)
        elif key=="office":
            if "office" in cvn:met.append(label)
            else:unknown.append(label)
        elif key=="atendimento":
            met.append(label)
        elif key=="suporte":
            if "suporte" in cvn or "tecnologia" in cvn:met.append(label)
            else:unknown.append(label)
        elif key=="juridico":
            met.append(label)
        elif key=="administrativo":
            met.append(label)
    return met,unknown,notmet

def autofill_known_fields(page,p):
    d=p.get("dados_candidatura",{})
    candidates = {
        "nome": d.get("nome_completo",""),
        "name": d.get("nome_completo",""),
        "email": d.get("email",""),
        "e-mail": d.get("email",""),
        "telefone": d.get("telefone",""),
        "phone": d.get("telefone",""),
        "celular": d.get("telefone",""),
        "cidade": d.get("cidade",""),
        "city": d.get("cidade",""),
        "estado": d.get("estado",""),
        "state": d.get("estado",""),
        "country": d.get("pais",""),
        "pais": d.get("pais",""),
        "país": d.get("pais",""),
        "linkedin": d.get("linkedin",""),
        "portfolio": d.get("portfolio","")
    }
    filled=0
    for field in page.locator("input, textarea").all():
        try:
            typ=(field.get_attribute("type") or "text").lower()
            if typ in ("hidden","submit","button","checkbox","radio","file"):continue
            label=" ".join(filter(None,[
                field.get_attribute("name"), field.get_attribute("id"),
                field.get_attribute("placeholder"), field.get_attribute("aria-label")
            ]))
            ln=norm(label)
            value=""
            for k,v in candidates.items():
                if v and k in ln:
                    value=v;break
            if value and not field.input_value():
                field.fill(value);filled+=1
        except:pass
    return filled

def resume_attachment_path(p=None):
    p=p or load_profile()
    configured=p.get("arquivo_curriculo_original","")
    candidates=[]
    if configured:
        candidates.append(configured if os.path.isabs(configured) else os.path.join(BASE_DIR,configured))
    candidates.extend(os.path.join(BASE_DIR,"curriculo_original"+ext) for ext in (".pdf",".docx",".txt"))
    candidates.append(os.path.join(BASE_DIR,"curriculo.pdf"))
    return next((path for path in candidates if os.path.isfile(path)),"")


def attach_resume(page,p=None):
    resume=resume_attachment_path(p)
    if not resume:return 0
    count=0
    for field in page.locator('input[type="file"]').all():
        try:
            accept=norm(field.get_attribute("accept") or "")
            ext=os.path.splitext(resume)[1].lstrip(".")
            if not accept or ext in accept or "document" in accept or "*/*" in accept:
                field.set_input_files(resume);count+=1
        except:pass
    return count

def find_unknown_required_fields(page):
    unknown=[]
    for field in page.locator("input, textarea, select").all():
        try:
            if not field.is_visible():continue
            required=field.get_attribute("required") is not None or field.get_attribute("aria-required")=="true"
            if not required:continue
            tag=field.evaluate("(e)=>e.tagName.toLowerCase()")
            typ=(field.get_attribute("type") or "").lower()
            if typ in ("hidden","submit","button","file"):continue
            val=""
            if tag=="select":
                val=field.input_value()
            elif typ in ("checkbox","radio"):
                val="checked" if field.is_checked() else ""
            else:
                val=field.input_value()
            if val:continue
            desc=" ".join(filter(None,[field.get_attribute("name"),field.get_attribute("id"),
                                       field.get_attribute("placeholder"),field.get_attribute("aria-label")]))
            unknown.append(desc or "campo obrigatório não identificado")
        except:pass
    return unknown[:10]

def detect_browser_path(browser):
    browser=norm(browser)
    envs={k:os.environ.get(k,"") for k in ("LOCALAPPDATA","PROGRAMFILES","PROGRAMFILES(X86)")}
    candidates=[]
    if browser=="brave":
        candidates=[
            os.path.join(envs["LOCALAPPDATA"],"BraveSoftware","Brave-Browser","Application","brave.exe"),
            os.path.join(envs["PROGRAMFILES"],"BraveSoftware","Brave-Browser","Application","brave.exe"),
            os.path.join(envs["PROGRAMFILES(X86)"],"BraveSoftware","Brave-Browser","Application","brave.exe"),
        ]
    elif browser=="chrome":
        candidates=[
            os.path.join(envs["LOCALAPPDATA"],"Google","Chrome","Application","chrome.exe"),
            os.path.join(envs["PROGRAMFILES"],"Google","Chrome","Application","chrome.exe"),
            os.path.join(envs["PROGRAMFILES(X86)"],"Google","Chrome","Application","chrome.exe"),
        ]
    elif browser=="edge":
        candidates=[
            os.path.join(envs["PROGRAMFILES(X86)"],"Microsoft","Edge","Application","msedge.exe"),
            os.path.join(envs["PROGRAMFILES"],"Microsoft","Edge","Application","msedge.exe"),
            os.path.join(envs["LOCALAPPDATA"],"Microsoft","Edge","Application","msedge.exe"),
        ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""

def get_browser_launch_settings(p):
    choice=norm(p.get("navegador_automacao","automatico"))
    aliases={"automático":"automatico","google chrome":"chrome","microsoft edge":"edge",
             "chromium interno":"chromium","navegador interno":"chromium"}
    choice=aliases.get(choice,choice)

    # Automático: Chrome -> Edge -> Brave -> Chromium do Playwright.
    if choice in ("automatico","auto",""):
        for name in ("chrome","edge","brave"):
            path=detect_browser_path(name)
            if path:
                return {"browser":"chromium","channel":None,"executable_path":path,
                        "profile_dir":os.path.join(BASE_DIR,"browser_profiles",name),
                        "label":name.title()}
        return {"browser":"chromium","channel":None,"executable_path":None,
                "profile_dir":os.path.join(BASE_DIR,"browser_profiles","chromium"),
                "label":"Chromium"}

    if choice in ("chrome","edge","brave"):
        path=detect_browser_path(choice)
        if not path:
            raise RuntimeError(f"{choice.title()} não foi encontrado neste computador. Escolha Automático ou outro navegador.")
        return {"browser":"chromium","channel":None,"executable_path":path,
                "profile_dir":os.path.join(BASE_DIR,"browser_profiles",choice),
                "label":choice.title()}

    if choice=="firefox":
        return {"browser":"firefox","channel":None,"executable_path":None,
                "profile_dir":os.path.join(BASE_DIR,"browser_profiles","firefox"),
                "label":"Firefox (Playwright)"}

    return {"browser":"chromium","channel":None,"executable_path":None,
            "profile_dir":os.path.join(BASE_DIR,"browser_profiles","chromium"),
            "label":"Chromium"}


def simple_location_mode(local, modalidade):
    loc=(local or "").strip()
    mode=norm(modalidade or "")

    if mode.startswith("remoto brasil") and "confirmado" in mode:
        simple_mode="Remoto"
        if not loc or norm(loc) in ("remoto","remota","remote","brasil","brazil","anywhere","worldwide"):
            return "Remoto"
        return f"{loc} • Remoto"

    if mode.startswith("remoto"):
        simple_mode="Verificar modelo"
    elif mode.startswith("presencial"):
        simple_mode="Presencial"
    elif mode.startswith("hibrid") or mode.startswith("híbr"):
        simple_mode="Híbrido"
    elif "conflit" in mode or "confirm" in mode or "verificar" in mode or not mode:
        simple_mode="Verificar modelo"
    else:
        simple_mode="Verificar modelo"

    if not loc or norm(loc) in ("nao informado","não informado",""):
        return simple_mode

    return f"{loc} • {simple_mode}"

def format_date_br(value):
    raw=str(value or "").strip()
    if not raw:return "Data não informada"
    try:return datetime.fromisoformat(raw.replace("Z","+00:00")).strftime("%d/%m/%Y")
    except Exception:pass
    for fmt in ("%d/%m/%Y","%d-%m-%Y","%Y/%m/%d"):
        try:return datetime.strptime(raw[:10],fmt).strftime("%d/%m/%Y")
        except Exception:pass
    return raw[:10]


def jobs_query(view="todas",search=""):
    sql=("SELECT id,score,titulo,empresa,local,modalidade,COALESCE(NULLIF(categoria,''),'Geral'),status,"
         "COALESCE(selecionada_lote,0),COALESCE(data_publicacao,'') "
         "FROM vagas")
    clauses=[];params=[]
    if view=="candidaturas":
        clauses.append("status IN ('Candidatado','Entrevista','Rejeitado')")
    else:
        clauses.extend(["status='Nova'","COALESCE(selecionada_lote,0)=0","decisao IN ('APROVADA','REVISAR')"])
        if view=="recomendadas":
            clauses.append("decisao='APROVADA'")
        elif view=="revisar":
            clauses.append("decisao='REVISAR'")
        elif view=="estagio":
            clauses.append("(categoria LIKE 'Estágio%' OR lower(titulo) LIKE '%estágio%' OR lower(titulo) LIKE '%estagio%')")
        elif view in ("remoto","home_office"):
            clauses.append("modalidade LIKE 'Remoto%confirmado%'")
        elif view=="presencial":
            clauses.append("(modalidade LIKE 'Presencial%' OR modalidade LIKE 'Híbrido%')")
    if search.strip():
        clauses.append("(titulo LIKE ? OR empresa LIKE ? OR descricao LIKE ?)")
        value="%"+search.strip()+"%";params.extend([value,value,value])
    if clauses:sql+=" WHERE "+" AND ".join(clauses)
    sql+=" ORDER BY CASE decisao WHEN 'APROVADA' THEN 0 ELSE 1 END,score DESC,id DESC"
    return sql,params

class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title(APP_TITLE)
        self.instance_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:self.instance_socket.bind(("127.0.0.1",47832))
        except OSError:
            messagebox.showinfo(APP_TITLE,"O aplicativo já está aberto.")
            self.destroy();raise SystemExit
        try:backup_database()
        except Exception:LOGGER.exception("Não foi possível criar o backup automático")
        self.geometry("1420x820")
        self.minsize(1100,700)
        self.configure(bg="#eef0f5");self.geometry("1450x820");self.minsize(1150,680)
        if requests is None or BeautifulSoup is None:
            messagebox.showerror("Dependências","Execute iniciar.bat para instalar requests e beautifulsoup4.")
        self.p=load_profile();self.cv=read_cv();self.conn=sqlite3.connect(DB_PATH,check_same_thread=False);self.current=None
        if self.cv.strip() and int(self.p.get("perfil_curriculo_versao",0) or 0)<2:
            adapt_profile_to_cv(self.p,self.cv);save_json_file(PROFILE_PATH,self.p)
        self.search_running=False;self.open_windows={}
        self.db();self.load_feedback_profile();self.migrate_v19();self.migrate_v23();self.migrate_v24();self.migrate_v25();self.migrate_v26();self.ui()
        self.apply_internship_preference(bool(self.p.get("buscar_estagios",True)));self.refresh()
        self.protocol("WM_DELETE_WINDOW",self.close_app)
        if not self.cv.strip():self.after(350,self.edit_profile)

    def db(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS vagas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,titulo TEXT,empresa TEXT,local TEXT,modalidade TEXT,descricao TEXT,
        url TEXT UNIQUE,fonte TEXT,data_publicacao TEXT,salario TEXT,score INTEGER,classificacao TEXT,motivo TEXT,
        status TEXT DEFAULT 'Nova',criada_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS descartadas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,titulo TEXT,empresa TEXT,local TEXT,descricao TEXT,
        url TEXT UNIQUE,fonte TEXT,data_publicacao TEXT,salario TEXT,motivo_descarte TEXT,
        descartada_em TEXT DEFAULT CURRENT_TIMESTAMP)""")
        for col,ddl in [
            ("selecionada_lote","INTEGER DEFAULT 0"),
            ("tentativas_envio","INTEGER DEFAULT 0"),
            ("ultimo_resultado","TEXT DEFAULT ''"),
            ("workplace_type","TEXT DEFAULT ''"),
            ("location_confidence","TEXT DEFAULT ''"),
            ("location_evidence","TEXT DEFAULT ''"),
            ("workplace_type_raw","TEXT DEFAULT ''"),
            ("workplace_source","TEXT DEFAULT ''"),
            ("structured_location_json","TEXT DEFAULT ''"),
            ("applicant_location_requirements","TEXT DEFAULT ''"),
            ("remote_eligible_brazil","INTEGER DEFAULT NULL"),
            ("modality_checked_at","TEXT DEFAULT ''"),
            ("description_status","TEXT DEFAULT ''"),
            ("description_attempts","INTEGER DEFAULT 0"),
            ("description_last_error","TEXT DEFAULT ''"),
            ("description_last_attempt_at","TEXT DEFAULT ''"),
            ("description_next_retry_at","TEXT DEFAULT ''"),
            ("description_source","TEXT DEFAULT ''"),
            ("candidatura_em","TEXT DEFAULT ''")
        ]:
            try:self.conn.execute(f"ALTER TABLE vagas ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:pass
        try:self.conn.execute("ALTER TABLE vagas ADD COLUMN categoria TEXT DEFAULT ''")
        except sqlite3.OperationalError:pass
        try:self.conn.execute("ALTER TABLE vagas ADD COLUMN decisao TEXT DEFAULT 'APROVADA'")
        except sqlite3.OperationalError:pass
        try:self.conn.execute("ALTER TABLE vagas ADD COLUMN confianca TEXT DEFAULT 'Média'")
        except sqlite3.OperationalError:pass
        try:self.conn.execute("ALTER TABLE vagas ADD COLUMN fontes TEXT DEFAULT ''")
        except sqlite3.OperationalError:pass
        try:self.conn.execute("ALTER TABLE vagas ADD COLUMN fingerprint TEXT DEFAULT ''")
        except sqlite3.OperationalError:pass
        try:self.conn.execute("CREATE INDEX IF NOT EXISTS idx_vagas_fingerprint ON vagas(fingerprint)")
        except sqlite3.OperationalError:pass
        self.conn.execute("""CREATE TABLE IF NOT EXISTS preferencias_feedback(
            termo TEXT PRIMARY KEY,positivo INTEGER DEFAULT 0,negativo INTEGER DEFAULT 0)""")
        try:
            rows=self.conn.execute("SELECT id,titulo,empresa,local FROM vagas WHERE COALESCE(fingerprint,'')=''").fetchall()
            for vid,t,e,l in rows:
                fp=job_fingerprint({"titulo":t,"empresa":e,"local":l})
                if fp:self.conn.execute("UPDATE vagas SET fingerprint=? WHERE id=?",(fp,vid))
        except Exception:
            LOGGER.exception("Falha ao preencher fingerprints durante a migration")
        self.conn.commit()

    def close_app(self):
        try:self.conn.close()
        except Exception:pass
        try:self.instance_socket.close()
        except Exception:pass
        self.destroy()

    def load_feedback_profile(self):
        profile = self.__dict__.get("p") if hasattr(self, "__dict__") else None
        if profile is None:
            return
        try:
            profile["feedback_preferencias"]={term:int(pos or 0)-int(neg or 0)
                for term,pos,neg in self.conn.execute("SELECT termo,positivo,negativo FROM preferencias_feedback")}
        except Exception:
            profile["feedback_preferencias"]={}

    def record_feedback(self,vid,positive):
        row=self.conn.execute("SELECT titulo FROM vagas WHERE id=?",(vid,)).fetchone()
        if not row:return
        column="positivo" if positive else "negativo"
        for token in feedback_tokens(row[0]):
            self.conn.execute("INSERT OR IGNORE INTO preferencias_feedback(termo) VALUES(?)",(token,))
            self.conn.execute(f"UPDATE preferencias_feedback SET {column}={column}+1 WHERE termo=?",(token,))
        self.conn.commit()
        self.load_feedback_profile()

    def migrate_v19(self):
        """Corrige classificações antigas do LinkedIn sem apagar vagas/candidaturas."""
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS app_meta(chave TEXT PRIMARY KEY, valor TEXT)")
            done=self.conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v19' ").fetchone()
            if done:return
            # Versões anteriores usavam o filtro da pesquisa remota como se fosse prova da modalidade.
            # Essas vagas passam para 'a confirmar' até serem coletadas novamente com evidência real.
            self.conn.execute("""UPDATE vagas
                               SET modalidade='Local/modalidade não confirmados', decisao='REVISAR'
                               WHERE fonte='LinkedIn' AND status='Nova'
                                 AND modalidade LIKE 'Remoto%'""")
            self.conn.execute("INSERT OR REPLACE INTO app_meta(chave,valor) VALUES('migracao_v19','1')")
            self.conn.commit()
        except Exception:
            LOGGER.exception("Falha na migration v19")

    def migrate_v23(self):
        """Reclassifica modalidade sem apagar vagas nem alterar candidaturas."""
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS app_meta(chave TEXT PRIMARY KEY, valor TEXT)")
            done=self.conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v23_modalidade'").fetchone()
            if done:return
            rows=self.conn.execute("""SELECT id,titulo,local,descricao,fonte,COALESCE(workplace_type,'')
                                      FROM vagas""").fetchall()
            for vid,title,local,description,source,workplace_type in rows:
                job={"titulo":title or "","local":local or "","descricao":description or "",
                     "fonte":source or "","workplace_type":workplace_type or ""}
                ld=location_decision(job,self.p)
                decision="REVISAR" if not ld["ok"] else decision_level(job,self.p,ld["mode"])
                self.conn.execute("""UPDATE vagas SET modalidade=?,decisao=?,location_confidence=?,
                                      location_evidence=? WHERE id=?""",
                                  (ld["mode"],decision,ld["confidence"],ld["evidence"],vid))
            self.conn.execute("INSERT OR REPLACE INTO app_meta(chave,valor) VALUES('migracao_v23_modalidade','1')")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            LOGGER.exception("Falha na migration de modalidade v23")

    def migrate_v24(self):
        """Preserva dados estruturados existentes sem remover ou recriar tabelas."""
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS app_meta(chave TEXT PRIMARY KEY, valor TEXT)")
            done=self.conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v24_dados_estruturados'").fetchone()
            if done:return
            rows=self.conn.execute("""SELECT id,local,modalidade,COALESCE(workplace_type,''),
                                      COALESCE(workplace_type_raw,''),COALESCE(workplace_source,''),
                                      COALESCE(structured_location_json,''),remote_eligible_brazil,
                                      COALESCE(modality_checked_at,'') FROM vagas""").fetchall()
            checked=datetime.now(timezone.utc).isoformat(timespec="seconds")
            for vid,local,mode,workplace,raw,source,structured,eligible,checked_at in rows:
                raw=raw or workplace or ""
                source=source or ("legacy" if workplace else "")
                structured=structured or compact_json({"display":local or ""})
                if eligible is None:
                    normalized_mode=norm(mode)
                    if normalized_mode.startswith("remoto brasil") and "confirmado" in normalized_mode:eligible=1
                    elif normalized_mode.startswith("remoto sem"):eligible=0
                self.conn.execute("""UPDATE vagas SET workplace_type_raw=?,workplace_source=?,
                                      structured_location_json=?,remote_eligible_brazil=?,modality_checked_at=?
                                      WHERE id=?""",
                                  (raw,source,structured,eligible,checked_at or checked,vid))
            self.conn.execute("INSERT OR REPLACE INTO app_meta(chave,valor) VALUES('migracao_v24_dados_estruturados','1')")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            LOGGER.exception("Falha na migration de dados estruturados v24")

    def migrate_v25(self):
        """Classifica descrições existentes; migration aditiva e idempotente."""
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS app_meta(chave TEXT PRIMARY KEY, valor TEXT)")
            done=self.conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v25_descricoes'").fetchone()
            if done:return
            self.conn.execute("""UPDATE vagas SET description_status=CASE
                WHEN LENGTH(TRIM(COALESCE(descricao,'')))>=120 THEN 'disponivel'
                WHEN fonte='LinkedIn' THEN 'pendente'
                ELSE 'indisponivel' END
                WHERE COALESCE(description_status,'')=''""")
            self.conn.execute("""UPDATE vagas SET description_source=fonte
                                 WHERE COALESCE(description_source,'')='' AND LENGTH(TRIM(COALESCE(descricao,'')))>=120""")
            self.conn.execute("INSERT OR REPLACE INTO app_meta(chave,valor) VALUES('migracao_v25_descricoes','1')")
            self.conn.commit()
        except Exception:
            self.conn.rollback();LOGGER.exception("Falha na migration v25 de descrições")

    def migrate_v26(self):
        """Adiciona a data da candidatura preservando registros antigos."""
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS app_meta(chave TEXT PRIMARY KEY, valor TEXT)")
            done=self.conn.execute("SELECT valor FROM app_meta WHERE chave='migracao_v26_data_candidatura'").fetchone()
            if done:return
            self.conn.execute("""UPDATE vagas SET candidatura_em=COALESCE(NULLIF(criada_em,''),CURRENT_TIMESTAMP)
                                 WHERE status IN ('Candidatado','Entrevista','Rejeitado')
                                   AND COALESCE(candidatura_em,'')=''""")
            self.conn.execute("INSERT OR REPLACE INTO app_meta(chave,valor) VALUES('migracao_v26_data_candidatura','1')")
            self.conn.commit()
        except Exception:
            self.conn.rollback();LOGGER.exception("Falha na migration v26 de candidatura")


    def ui(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except Exception: pass
        colors={"bg":"#eef3f7","panel":"#f8fafc","white":"#ffffff","ink":"#243447",
                "muted":"#66788a","blue":"#4f7cac","blue_dark":"#385f87","blue_soft":"#dfeaf5",
                "green":"#4f8a72","green_soft":"#e4f1eb","danger":"#a85c62","line":"#d8e2ea"}
        self.configure(bg=colors["bg"])
        style.configure(".",font=("Segoe UI",10),background=colors["bg"],foreground=colors["ink"])
        style.configure("TFrame",background=colors["bg"])
        style.configure("TLabel",background=colors["bg"],foreground=colors["ink"])
        style.configure("Panel.TFrame",background=colors["panel"])
        style.configure("Panel.TLabel",background=colors["panel"],foreground=colors["ink"])
        style.configure("Muted.Panel.TLabel",background=colors["panel"],foreground=colors["muted"])
        style.configure("TButton",font=("Segoe UI",10,"bold"),padding=(15,10),borderwidth=0)
        style.configure("Primary.TButton",background=colors["blue"],foreground="white",padding=(20,12))
        style.map("Primary.TButton",background=[("active",colors["blue_dark"]),("disabled","#aebdca")])
        style.configure("Soft.TButton",background=colors["blue_soft"],foreground=colors["blue_dark"])
        style.map("Soft.TButton",background=[("active","#cfdeec")])
        style.configure("Danger.TButton",background="#f5e7e8",foreground=colors["danger"])
        style.map("Danger.TButton",background=[("active","#ecd6d8")])
        style.configure("Summary.TButton",background=colors["panel"],foreground=colors["muted"],
                        font=("Segoe UI",10),padding=(6,5),anchor="w",borderwidth=0)
        style.map("Summary.TButton",background=[("active",colors["blue_soft"])],foreground=[("active",colors["blue_dark"])])
        style.configure("Filter.TRadiobutton",background=colors["panel"],foreground=colors["ink"],
                        font=("Segoe UI",11,"bold"),padding=(8,9))
        style.map("Filter.TRadiobutton",background=[("selected",colors["blue_soft"]),("active","#eaf1f7")],
                  foreground=[("selected",colors["blue_dark"])])
        style.configure("Treeview",font=("Segoe UI",10),rowheight=58,background=colors["white"],
                        fieldbackground=colors["white"],foreground=colors["ink"],borderwidth=0)
        style.configure("Treeview.Heading",font=("Segoe UI",9,"bold"),padding=(10,11),
                        background="#edf2f6",foreground=colors["muted"],relief="flat")
        style.map("Treeview",background=[("selected",colors["blue_soft"])],foreground=[("selected",colors["ink"])])
        style.configure("Status.Horizontal.TProgressbar",background=colors["blue"],troughcolor="#dfe7ed",borderwidth=0)

        header=tk.Frame(self,bg=colors["panel"],highlightbackground=colors["line"],highlightthickness=0)
        header.pack(fill="x")
        brand=tk.Frame(header,bg=colors["panel"]);brand.pack(side="left",padx=(24,20),pady=15)
        tk.Label(brand,text="Tô no Corre",font=("Segoe UI",23,"bold"),bg=colors["panel"],fg=colors["ink"]).pack(anchor="w")
        tk.Label(brand,text="Vagas trabalhando por você.",font=("Segoe UI",10),bg=colors["panel"],fg=colors["muted"]).pack(anchor="w")
        nav=ttk.Frame(header,style="Panel.TFrame");nav.pack(side="right",padx=20,pady=16)
        self.search_button=ttk.Button(nav,text="Buscar vagas",style="Primary.TButton",command=lambda:self.start_source("all"))
        self.search_button.pack(side="left",padx=4)
        ttk.Button(nav,text="Limpar pesquisa",style="Soft.TButton",command=self.clear_search).pack(side="left",padx=4)
        ttk.Button(nav,text="Fila",style="Soft.TButton",command=self.show_batch).pack(side="left",padx=4)
        ttk.Button(nav,text="Candidatar",style="Soft.TButton",command=self.start_batch).pack(side="left",padx=4)
        ttk.Button(nav,text="Minhas candidaturas",command=self.show_applications).pack(side="left",padx=4)
        ttk.Button(nav,text="Configurações",command=self.edit_profile).pack(side="left",padx=4)

        workspace=ttk.Frame(self,padding=(18,16,18,8));workspace.pack(fill="both",expand=True)
        sidebar=ttk.Frame(workspace,style="Panel.TFrame",padding=(14,16));sidebar.pack(side="left",fill="y",padx=(0,14))
        ttk.Label(sidebar,text="MOSTRAR VAGAS",style="Muted.Panel.TLabel",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=6,pady=(0,8))
        self.view_mode=tk.StringVar(value="todas")
        for text,value in [("Todas","todas"),("Remoto","remoto"),("Estágio","estagio")]:
            ttk.Radiobutton(sidebar,text=text,value=value,variable=self.view_mode,command=self.refresh,
                            style="Filter.TRadiobutton",width=17).pack(fill="x",pady=2)
        ttk.Separator(sidebar).pack(fill="x",pady=14)
        ttk.Label(sidebar,text="RESUMO",style="Muted.Panel.TLabel",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=6,pady=(0,7))
        self.stat_rec=tk.StringVar(value="Recomendadas: 0")
        self.stat_rev=tk.StringVar(value="Vale conferir: 0")
        self.stat_app=tk.StringVar(value="Candidaturas: 0")
        self.stat_out=tk.StringVar(value="Fora do perfil: 0")
        self.stat_discarded=tk.StringVar(value="Descartadas: 0")
        for var,command in [(self.stat_rec,lambda:self.set_view("recomendadas")),
                            (self.stat_rev,lambda:self.set_view("revisar")),
                            (self.stat_app,self.show_applications),(self.stat_out,self.show_discarded),
                            (self.stat_discarded,self.show_manually_discarded)]:
            ttk.Button(sidebar,textvariable=var,style="Summary.TButton",command=command).pack(fill="x",pady=1)

        main=ttk.Frame(workspace);main.pack(side="left",fill="both",expand=True)
        tools=ttk.Frame(main);tools.pack(fill="x",pady=(0,10))
        titlebox=ttk.Frame(tools);titlebox.pack(side="left")
        ttk.Label(titlebox,text="Vagas para você",font=("Segoe UI",16,"bold")).pack(anchor="w")
        ttk.Label(titlebox,text="Escolha uma vaga para ver os detalhes.",foreground=colors["muted"]).pack(anchor="w")
        self.search_activity=tk.Frame(tools,bg=colors["blue_soft"],highlightthickness=0)
        self.search_spinner=tk.StringVar(value="◐")
        tk.Label(self.search_activity,textvariable=self.search_spinner,font=("Segoe UI",16,"bold"),
                 bg=colors["blue_soft"],fg=colors["blue_dark"]).pack(side="left",padx=(10,5),pady=7)
        tk.Label(self.search_activity,text="Buscando vagas para você…",font=("Segoe UI",10,"bold"),
                 bg=colors["blue_soft"],fg=colors["blue_dark"]).pack(side="left",padx=(0,10),pady=7)
        self.search_animation_job=None;self.search_animation_frame=0
        self.q=tk.StringVar()
        self.batch_selection={r[0] for r in self.conn.execute(
            "SELECT id FROM vagas WHERE selecionada_lote=1 AND status='Nova'").fetchall()}
        self.queue_action_text=tk.StringVar(value="Incluir na fila")
        ttk.Button(tools,textvariable=self.queue_action_text,style="Primary.TButton",
                   command=self.apply_batch_selection).pack(side="right",padx=(0,10))
        self.update_queue_action()

        pane=ttk.Panedwindow(main,orient="horizontal");pane.pack(fill="both",expand=True)
        left=ttk.Frame(pane,style="Panel.TFrame",padding=1)
        right=ttk.Frame(pane,style="Panel.TFrame",padding=(16,14))
        pane.add(left,weight=3);pane.add(right,weight=2)

        cols=("batch","score","titulo","empresa","local","data")
        self.tree=ttk.Treeview(left,columns=cols,show="headings",selectmode="browse")
        self.job_heading_labels={"batch":"FILA","score":"COMPAT.","titulo":"VAGA","empresa":"EMPRESA","local":"LOCAL / MODELO","data":"PUBLICAÇÃO"}
        self.job_sort_state={"column":"","reverse":False}
        for col,title,width,anchor in [("batch","FILA",58,"center"),("score","COMPAT.",88,"center"),("titulo","VAGA",275,"w"),
                                       ("empresa","EMPRESA",165,"w"),("local","LOCAL / MODELO",215,"w"),("data","PUBLICAÇÃO",105,"center")]:
            self.tree.heading(col,text=title,command=lambda c=col:self.sort_jobs(c))
            self.tree.column(col,width=width,anchor=anchor,minwidth=50 if col=="batch" else 70)
        tree_scroll=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview);self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right",fill="y");self.tree.pack(side="left",fill="both",expand=True)
        self.tree.tag_configure("great",foreground="#34705a")
        self.tree.tag_configure("possible",foreground=colors["ink"])
        self.tree.bind("<Button-1>",self.toggle_batch_checkbox,add="+")
        self.tree.bind("<<TreeviewSelect>>",self.select);self.tree.bind("<Double-1>",lambda e:self.open_job())

        detail_head=ttk.Frame(right,style="Panel.TFrame");detail_head.pack(fill="x")
        ttk.Label(detail_head,text="DETALHES DA VAGA",style="Muted.Panel.TLabel",font=("Segoe UI",9,"bold")).pack(side="left")
        ttk.Button(detail_head,text="Descartar",style="Danger.TButton",
                   command=self.discard_current).pack(side="right",padx=(5,0))
        ttk.Button(detail_head,text="Ver vaga",command=self.open_job).pack(side="right")
        self.tv=tk.StringVar(value="Selecione uma vaga")
        ttk.Label(right,textvariable=self.tv,style="Panel.TLabel",font=("Segoe UI",15,"bold"),wraplength=480).pack(anchor="w",pady=(5,3))
        self.meta=tk.StringVar(value="Escolha uma vaga na lista ao lado.")
        ttk.Label(right,textvariable=self.meta,style="Muted.Panel.TLabel",wraplength=480).pack(anchor="w")
        self.data_quality=tk.StringVar(value="")
        ttk.Label(right,textvariable=self.data_quality,style="Muted.Panel.TLabel",wraplength=480).pack(anchor="w",pady=(2,12))

        def detail_section(label,height,expand=False):
            ttk.Label(right,text=label,style="Panel.TLabel",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(3,4))
            box=tk.Text(right,height=height,wrap="word",padx=10,pady=9,font=("Segoe UI",10),
                        bg=colors["white"],fg=colors["ink"],relief="flat",highlightthickness=1,
                        highlightbackground=colors["line"],selectbackground=colors["blue_soft"])
            box.pack(fill="both" if expand else "x",expand=expand,pady=(0,9));box.configure(state="disabled")
            return box
        self.desc_box=detail_section("Descrição",9,True)
        self.req_box=detail_section("Requisitos",5)
        self.pay_box=detail_section("Salário e benefícios",4)

        status=tk.Frame(self,bg=colors["panel"],highlightbackground=colors["line"],highlightthickness=1)
        status.pack(fill="x",side="bottom")
        self.info=tk.StringVar(value="Pronto para buscar vagas")
        tk.Label(status,textvariable=self.info,font=("Segoe UI",9),bg=colors["panel"],fg=colors["muted"]).pack(side="left",padx=18,pady=7)
        self.prog=ttk.Progressbar(status,mode="indeterminate",length=120,style="Status.Horizontal.TProgressbar")
        self.prog.pack(side="right",padx=18,pady=9)

    def set_view(self,view):
        self.view_mode.set(view);self.refresh()

    def clear_search(self):
        total=self.conn.execute("""SELECT COUNT(*) FROM vagas
            WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0""").fetchone()[0]
        if not total:
            self.info.set("A pesquisa já está vazia. A fila e o histórico foram mantidos.");return 0
        if not messagebox.askyesno("Limpar pesquisa",
            f"Retirar {total} vaga(s) da pesquisa atual e começar novamente do zero?\n\n"
            "Fila, candidaturas e vagas fora do perfil serão mantidas."):
            return 0
        with self.conn:
            self.conn.execute("""UPDATE vagas SET status='Pesquisa limpa',selecionada_lote=0
                                 WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0""")
        self.current=None;self.q.set("");self.view_mode.set("todas");self.refresh()
        self.tv.set("Selecione uma vaga");self.meta.set("Faça uma nova busca para carregar vagas.");self.data_quality.set("")
        for box in (self.desc_box,self.req_box,self.pay_box):
            box.configure(state="normal");box.delete("1.0","end");box.configure(state="disabled")
        self.info.set(f"Pesquisa limpa: {total} vaga(s) arquivada(s). Você já pode buscar novamente.")
        return total

    def sort_jobs(self,column,reverse=None):
        if reverse is None:
            reverse=(not self.job_sort_state["reverse"]) if self.job_sort_state["column"]==column else False
        self.job_sort_state={"column":column,"reverse":reverse}
        index=list(self.tree["columns"]).index(column)
        def key(iid):
            value=self.tree.item(iid,"values")[index]
            if column=="score":
                try:return int(str(value).replace("%","").strip())
                except ValueError:return -1
            if column=="batch":return 1 if str(value)=="☑" else 0
            if column=="data":
                try:return datetime.strptime(str(value),"%d/%m/%Y")
                except ValueError:return datetime.min
            return norm(value)
        items=list(self.tree.get_children(""));items.sort(key=key,reverse=reverse)
        for position,iid in enumerate(items):self.tree.move(iid,"",position)
        for col,label in self.job_heading_labels.items():
            marker=(" ▼" if reverse else " ▲") if col==column else ""
            self.tree.heading(col,text=label+marker,command=lambda c=col:self.sort_jobs(c))

    def managed_window(self,key,title,geometry,modal=False):
        current=self.open_windows.get(key)
        if current is not None:
            try:
                if current.winfo_exists():
                    current.deiconify();current.lift();current.focus_force()
                    return current,False
            except tk.TclError:pass
        win=tk.Toplevel(self);win.title(title);win.transient(self)
        width,height=(int(x) for x in geometry.lower().split("x")[:2])
        self.center_window(win,width,height)
        self.open_windows[key]=win
        if modal:win.grab_set()
        def close():
            self.open_windows.pop(key,None)
            try:
                if modal:win.grab_release()
            except tk.TclError:pass
            win.destroy()
        win.protocol("WM_DELETE_WINDOW",close);win._managed_close=close
        return win,True

    def center_window(self,win,width,height):
        self.update_idletasks()
        x=self.winfo_rootx()+max(0,(self.winfo_width()-width)//2)
        y=self.winfo_rooty()+max(0,(self.winfo_height()-height)//2)
        x=max(0,min(x,win.winfo_screenwidth()-width))
        y=max(0,min(y,win.winfo_screenheight()-height))
        win.geometry(f"{width}x{height}+{x}+{y}")

    def show_advanced_tools(self):
        w,created=self.managed_window("diagnostico","Diagnóstico","430x390")
        if not created:return
        box=ttk.Frame(w,padding=14);box.pack(fill="both",expand=True)
        ttk.Label(box,text="Buscar uma fonte específica",font=("Segoe UI",11,"bold")).pack(anchor="w")
        self.adv_source=tk.StringVar(value="Gupy")
        cb=ttk.Combobox(box,textvariable=self.adv_source,state="readonly",width=28,
            values=["Gupy","LinkedIn","Google","Indeed via Google","Remotas internacionais"])
        cb.pack(anchor="w",pady=(5,8))
        source_map={"Gupy":"gupy","LinkedIn":"linkedin","Google":"google",
                    "Indeed via Google":"indeed","Remotas internacionais":"remote"}
        ttk.Button(box,text="Buscar fonte selecionada",
            command=lambda:self.start_source(source_map[self.adv_source.get()])).pack(fill="x",pady=3)
        ttk.Separator(box).pack(fill="x",pady=10)
        for text,cmd in [
            ("Revalidar vagas atuais",self.revalidate_modes),
            ("Ver vagas fora do perfil",self.show_discarded),
            ("Resumo dos descartes",self.show_discard_summary),
            ("Saúde das fontes",self.show_source_health),
            ("Selecionar 75%+ para fila",self.select_batch),
            ("Abrir fila de candidaturas",self.show_batch),
            ("Iniciar lote",self.start_batch)
        ]:
            ttk.Button(box,text=text,command=cmd).pack(fill="x",pady=2)

    def add_current_to_batch(self):
        if not self.current:return
        self.conn.execute("UPDATE vagas SET selecionada_lote=1 WHERE id=?",(self.current,))
        self.conn.commit()
        if "batch_selection" in self.__dict__:
            self.batch_selection.add(self.current);self.update_queue_action();self.refresh()
        self.info.set("Vaga adicionada à fila de candidaturas.")

    def update_queue_action(self):
        if "queue_action_text" not in self.__dict__:return
        count=len(self.batch_selection)
        self.queue_action_text.set(f"Incluir na fila ({count})" if count else "Incluir na fila")

    def toggle_batch_checkbox(self,event):
        if self.tree.identify_region(event.x,event.y)!="cell" or self.tree.identify_column(event.x)!="#1":return
        iid=self.tree.identify_row(event.y)
        if not iid:return "break"
        vid=int(iid)
        if vid in self.batch_selection:self.batch_selection.remove(vid)
        else:self.batch_selection.add(vid)
        values=list(self.tree.item(iid,"values"));values[0]="☑" if vid in self.batch_selection else "☐"
        self.tree.item(iid,values=values)
        self.update_queue_action()
        return "break"

    def apply_batch_selection(self):
        selected=sorted(self.batch_selection)
        with self.conn:
            self.conn.execute("UPDATE vagas SET selecionada_lote=0")
            self.conn.executemany("UPDATE vagas SET selecionada_lote=1 WHERE id=? AND status='Nova'",
                                  ((vid,) for vid in selected))
        self.batch_selection={r[0] for r in self.conn.execute(
            "SELECT id FROM vagas WHERE selecionada_lote=1 AND status='Nova'").fetchall()}
        total=len(self.batch_selection);self.update_queue_action()
        for vid in selected:self.record_feedback(vid,True)
        self.info.set(f"Fila atualizada: {total} vaga(s).")
        self.refresh()

    def sync_batch_selection(self):
        self.batch_selection={r[0] for r in self.conn.execute(
            "SELECT id FROM vagas WHERE selecionada_lote=1 AND status='Nova'").fetchall()}
        self.update_queue_action();self.refresh()

    def clear_batch(self,ask=True):
        total=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE selecionada_lote=1").fetchone()[0]
        if not total:
            self.info.set("A fila já está vazia.")
            return 0
        if ask and not messagebox.askyesno("Limpar fila",f"Remover {total} vaga(s) da fila?\n\nAs vagas não serão excluídas."):
            return 0
        with self.conn:self.conn.execute("UPDATE vagas SET selecionada_lote=0")
        self.sync_batch_selection();self.info.set("Fila limpa. As vagas foram mantidas.")
        return total

    def remove_from_batch(self,vid):
        with self.conn:self.conn.execute("UPDATE vagas SET selecionada_lote=0 WHERE id=?",(vid,))
        if "batch_selection" in self.__dict__:self.batch_selection.discard(vid)
        if "queue_action_text" in self.__dict__:self.update_queue_action()
        self.refresh();self.info.set("Vaga removida da fila. Ela continua na lista de vagas.")
        return True

    def mark_application_completed(self,vid):
        with self.conn:
            self.conn.execute("""UPDATE vagas SET status='Candidatado',selecionada_lote=0,
                                 ultimo_resultado='Candidatura confirmada pelo usuário',
                                 candidatura_em=?
                                 WHERE id=?""",(datetime.now().isoformat(timespec="seconds"),vid))

    def show_current_description(self):
        if not self.current:return
        row=self.conn.execute("SELECT titulo,descricao FROM vagas WHERE id=?",(self.current,)).fetchone()
        if not row:return
        w,created=self.managed_window(f"descricao_{self.current}",row[0] or "Descrição da vaga","760x650")
        if not created:return
        txt=tk.Text(w,wrap="word",padx=12,pady=12)
        txt.pack(fill="both",expand=True)
        txt.insert("1.0",row[1] or "Descrição ainda não disponível. Use Configurações > Atualizar descrições pendentes para tentar novamente.")
        txt.configure(state="disabled")

    def start_source(self,src):
        if self.search_running:
            self.info.set("A busca atual ainda está em andamento.")
            return
        self.cv=read_cv()
        if not self.cv.strip():
            messagebox.showinfo("Adicione seu currículo","Carregue seu currículo para o aplicativo preparar uma busca compatível com o seu perfil.")
            self.edit_profile();return
        self.p=load_profile()
        self.reactivate_searchable_jobs()
        self.separate_outside_region_jobs()
        self.apply_internship_preference(bool(self.p.get("buscar_estagios",True)))
        self.search_running=True
        self.search_button.configure(state="disabled")
        self.start_search_animation()
        self.info.set(f"Buscando {src}...");self.prog.start(10)
        threading.Thread(target=self.run_source,args=(src,),daemon=True).start()

    def collect(self,src):
        if src=="gupy":return dedupe_multisource(fetch_gupy(self.p),self.p)
        if src=="linkedin":return dedupe_multisource(fetch_linkedin(self.p),self.p)
        if src=="google":return dedupe_multisource(fetch_google(self.p),self.p)
        if src=="indeed":return dedupe_multisource(fetch_google(self.p,"br.indeed.com","Indeed/Google"),self.p)
        if src=="remote":return dedupe_multisource(fetch_remotive(self.p),self.p)
        if src=="all":
            jobs=[];self.after(0,lambda:self.info.set("Consultando 5 fontes em paralelo..."))
            sources={
                "Gupy":lambda:fetch_gupy(self.p),
                "LinkedIn":lambda:fetch_linkedin(self.p),
                "Google":lambda:fetch_google(self.p),
                "Indeed via Google":lambda:fetch_google(self.p,"br.indeed.com","Indeed/Google"),
                "Remotive":lambda:fetch_remotive(self.p)
            }
            with ThreadPoolExecutor(max_workers=5,thread_name_prefix="busca") as executor:
                futures={executor.submit(fn):name for name,fn in sources.items()}
                for future in as_completed(futures):
                    name=futures[future]
                    try:
                        found=future.result() or [];jobs+=found
                        self.after(0,lambda n=name,total=len(found):self.info.set(f"{n} concluída: {total} vaga(s)"))
                    except Exception:LOGGER.exception("Falha na fonte %s",name)
            return dedupe_multisource(jobs,self.p)
        return []

    def save_discarded(self,j,reason):
        vals=(j.get("titulo",""),j.get("empresa",""),j.get("local",""),j.get("descricao",""),
              j.get("url",""),j.get("fonte",""),j.get("data_publicacao",""),j.get("salario",""),reason)
        try:
            self.conn.execute("""INSERT INTO descartadas
                (titulo,empresa,local,descricao,url,fonte,data_publicacao,salario,motivo_descarte)
                VALUES(?,?,?,?,?,?,?,?,?)""",vals)
        except sqlite3.IntegrityError:
            self.conn.execute("""UPDATE descartadas SET titulo=?,empresa=?,local=?,descricao=?,fonte=?,
                data_publicacao=?,salario=?,motivo_descarte=CASE
                    WHEN motivo_descarte='Descartada pelo usuário' THEN motivo_descarte ELSE ? END,
                descartada_em=CURRENT_TIMESTAMP WHERE url=?""",
                (j.get("titulo",""),j.get("empresa",""),j.get("local",""),j.get("descricao",""),
                 j.get("fonte",""),j.get("data_publicacao",""),j.get("salario",""),reason,j.get("url","")))

    def restore_discarded_record(self,did,refresh=True):
        row=self.conn.execute("""SELECT titulo,empresa,local,descricao,url,fonte,data_publicacao,salario
                                 FROM descartadas WHERE id=?""",(did,)).fetchone()
        if not row:return False
        t,e,l,d,u,f,dt,sal=row
        job={"titulo":t or "","empresa":e or "","local":l or "","descricao":d or "",
             "url":u or "","fonte":f or "","data_publicacao":dt or "","salario":sal or "",
             "source_brazil":f in ("Gupy","LinkedIn","Google","Indeed/Google")}
        score,label,reason,mode=score_job(job,load_profile(),read_cv())
        with self.conn:
            existing=self.conn.execute("SELECT id FROM vagas WHERE url=?",(u,)).fetchone()
            if existing:
                self.conn.execute("""UPDATE vagas SET status='Nova',selecionada_lote=0,
                                     ultimo_resultado='' WHERE id=?""",(existing[0],))
            else:
                self.conn.execute("""INSERT INTO vagas(titulo,empresa,local,modalidade,descricao,url,fonte,
                    data_publicacao,salario,score,classificacao,motivo,status)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'Nova')""",
                    (t,e,l,mode,d,u,f,dt,sal,score,label,reason))
            self.conn.execute("DELETE FROM descartadas WHERE id=?",(did,))
        if refresh:self.refresh()
        return True

    def show_discard_summary(self):
        rows=self.conn.execute("""SELECT motivo_descarte,COUNT(*) FROM descartadas
                                  GROUP BY motivo_descarte ORDER BY COUNT(*) DESC""").fetchall()
        total=sum(r[1] for r in rows)
        if not rows:
            messagebox.showinfo("Resumo de descartes","Ainda não há vagas descartadas registradas.")
            return
        details="\n".join(f"• {motivo}: {n}" for motivo,n in rows[:15])
        messagebox.showinfo("Resumo de descartes",
            f"{total} vagas descartadas registradas.\n\n{details}")

    def reactivate_searchable_jobs(self):
        """Toda nova pesquisa reapresenta vagas salvas, exceto descartadas pelo usuário."""
        with self.conn:
            cursor=self.conn.execute("""UPDATE vagas SET status='Nova',selecionada_lote=0,
                ultimo_resultado=CASE WHEN status='Arquivada' THEN '' ELSE ultimo_resultado END
                WHERE status IN ('Pesquisa limpa','Arquivada')""")
        restored=max(0,cursor.rowcount);self.refresh()
        return restored

    def separate_outside_region_jobs(self):
        """Move vagas locais externas para Fora do perfil, preservando fila e histórico."""
        rows=self.conn.execute("""SELECT id,titulo,empresa,local,descricao,url,fonte,data_publicacao,salario,
                                  COALESCE(workplace_type,'') FROM vagas
                                  WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0""").fetchall()
        moved=0
        for vid,titulo,empresa,local,descricao,url,fonte,pub,salario,workplace in rows:
            job={"titulo":titulo or "","empresa":empresa or "","local":local or "",
                 "descricao":descricao or "","url":url or "","fonte":fonte or "",
                 "data_publicacao":pub or "","salario":salario or "","workplace_type":workplace or ""}
            ld=location_decision(job,self.p)
            if ld["ok"] or "fora da regiao" not in norm(ld["mode"]):continue
            self.save_discarded(job,ld["mode"]);moved+=1
            self.conn.execute("UPDATE vagas SET status='Ignorada',selecionada_lote=0,decisao='REVISAR' WHERE id=?",(vid,))
        self.conn.commit()
        if moved:self.refresh()
        return moved

    def apply_internship_preference(self,enabled):
        """Separa estágios quando desativados e restaura apenas os filtrados por essa preferência."""
        if enabled:
            ids=[r[0] for r in self.conn.execute(
                "SELECT id FROM descartadas WHERE motivo_descarte='estágio desativado pelo usuário'")]
            restored=sum(1 for did in ids if self.restore_discarded_record(did,refresh=False))
            if restored:self.refresh()
            return restored
        rows=self.conn.execute("""SELECT id,titulo,empresa,local,descricao,url,fonte,data_publicacao,salario
                                  FROM vagas WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0""").fetchall()
        moved=0
        for vid,titulo,empresa,local,descricao,url,fonte,pub,salario in rows:
            job={"titulo":titulo or "","empresa":empresa or "","local":local or "","descricao":descricao or "",
                 "url":url or "","fonte":fonte or "","data_publicacao":pub or "","salario":salario or ""}
            if not is_intern(job):continue
            self.save_discarded(job,"estágio desativado pelo usuário")
            self.conn.execute("UPDATE vagas SET status='Ignorada',selecionada_lote=0 WHERE id=?",(vid,));moved+=1
        self.conn.commit()
        if moved:self.refresh()
        return moved

    def show_manually_discarded(self):
        self.show_discarded(manual_only=True)

    def show_discarded(self,manual_only=False):
        window_key="descartadas_manuais" if manual_only else "fora_perfil"
        window_title="Vagas descartadas pelo usuário" if manual_only else "Vagas fora do perfil"
        win,created=self.managed_window(window_key,window_title,"1250x650")
        if not created:return

        top=ttk.Frame(win,padding=8);top.pack(fill="x")
        ttk.Label(top,text="Filtro:").pack(side="left")
        q=tk.StringVar()
        ent=ttk.Entry(top,textvariable=q,width=35);ent.pack(side="left",padx=5)
        ttk.Label(top,text="Compatibilidade:").pack(side="left",padx=(16,5))
        compatibility_filter=tk.StringVar(value="Todas")
        compatibility_box=ttk.Combobox(top,textvariable=compatibility_filter,state="readonly",width=12,
                                       values=["Todas","50% ou mais","70% ou mais","85% ou mais"])
        compatibility_box.pack(side="left")

        pane=ttk.Panedwindow(win,orient="horizontal");pane.pack(fill="both",expand=True,padx=8,pady=(0,8))
        left,right=ttk.Frame(pane),ttk.Frame(pane);pane.add(left,weight=3);pane.add(right,weight=2)

        cols=("compat","titulo","empresa","local","fonte","motivo")
        tr=ttk.Treeview(left,columns=cols,show="headings")
        for c,t,w in [
            ("compat","Compat.",75),("titulo","Título",260),("empresa","Empresa",160),("local","Local",150),
            ("fonte","Fonte",90),("motivo","Motivo do descarte",270)
        ]:
            tr.heading(c,text=t);tr.column(c,width=w,anchor="center" if c=="compat" else "w")
        tr.pack(fill="both",expand=True)

        title=tk.StringVar(value="Selecione uma vaga descartada")
        ttk.Label(right,textvariable=title,font=("Segoe UI",12,"bold"),wraplength=450).pack(anchor="w",pady=(5,8))
        meta=tk.StringVar();ttk.Label(right,textvariable=meta,wraplength=450).pack(anchor="w")
        desc=tk.Text(right,wrap="word");desc.pack(fill="both",expand=True,pady=8);desc.configure(state="disabled")
        current={"url":""};compatibility_scores={};visible_ids=[]

        def load():
            for x in tr.get_children():tr.delete(x)
            s=q.get().strip()
            sql="""SELECT id,titulo,empresa,local,fonte,motivo_descarte,descricao,url,data_publicacao,salario
                   FROM descartadas"""
            clauses=[];params=[]
            if manual_only:
                clauses.append("motivo_descarte = ?")
                params.append("Descartada pelo usuário")
            if s:
                clauses.append("(titulo LIKE ? OR empresa LIKE ? OR local LIKE ? OR motivo_descarte LIKE ?)")
                like="%"+s+"%";params.extend([like,like,like,like])
            if clauses:sql+=" WHERE "+" AND ".join(clauses)
            sql+=" ORDER BY descartada_em DESC"
            minimum={"Todas":0,"50% ou mais":50,"70% ou mais":70,"85% ou mais":85}.get(compatibility_filter.get(),0)
            compatibility_scores.clear();visible=[];visible_ids.clear()
            for r in self.conn.execute(sql,params):
                did,title_text,company,local,source,discard_reason,description,url,published,salary=r
                job={"titulo":title_text or "","empresa":company or "","local":local or "",
                     "descricao":description or "","url":url or "","fonte":source or "",
                     "data_publicacao":published or "","salario":salary or ""}
                score=curriculum_compatibility(job,self.p,self.cv);compatibility_scores[did]=score
                if score>=minimum:visible.append((did,score,title_text,company,local,source,discard_reason))
            visible.sort(key=lambda item:(-item[1],item[0]))
            for did,score,title_text,company,local,source,discard_reason in visible:
                visible_ids.append(did)
                tr.insert("","end",iid=str(did),values=(f"{score}%",title_text,company,local,source,discard_reason))

        def selected(_=None):
            sel=tr.selection()
            if not sel:return
            row=self.conn.execute("""SELECT titulo,empresa,local,fonte,motivo_descarte,descricao,url,
                                     data_publicacao,salario FROM descartadas WHERE id=?""",(int(sel[0]),)).fetchone()
            if not row:return
            t,e,l,f,m,d,u,dt,sal=row
            title.set(t)
            score=compatibility_scores.get(int(sel[0]),curriculum_compatibility(
                {"titulo":t or "","empresa":e or "","local":l or "","descricao":d or ""},self.p,self.cv))
            meta.set(f"Compatibilidade com o currículo: {score}%\\n{e} | {l} | {f} | {dt or 'data n/i'} | {sal or 'salário n/i'}\\nMotivo: {m}")
            current["url"]=u or ""
            desc.configure(state="normal");desc.delete("1.0","end");desc.insert("1.0",d or "Descrição não coletada.")
            desc.configure(state="disabled")

        def open_selected():
            if current["url"]:webbrowser.open(current["url"])

        def restore_selected():
            sel=tr.selection()
            if not sel:return
            if self.restore_discarded_record(int(sel[0])):load()

        def restore_all():
            if manual_only:
                ids=[r[0] for r in self.conn.execute(
                    "SELECT id FROM descartadas WHERE motivo_descarte=? ORDER BY descartada_em DESC",
                    ("Descartada pelo usuário",))]
            else:
                ids=[r[0] for r in self.conn.execute(
                    "SELECT id FROM descartadas ORDER BY descartada_em DESC")]
            if not ids:messagebox.showinfo("Restaurar todas","Não há vagas descartadas para restaurar.",parent=win);return
            if not messagebox.askyesno("Restaurar vagas",
                f"Devolver todas as {len(ids)} vaga(s) deste diretório à lista principal?\n\nEsta ação não considera o filtro exibido. Confira o local: algumas podem ser presenciais ou híbridas fora da sua região.",parent=win):return
            restored=0
            for did in ids:
                if self.restore_discarded_record(did,refresh=False):restored+=1
            self.refresh();load();messagebox.showinfo("Vagas restauradas",f"{restored} vaga(s) voltaram para a lista.",parent=win)

        btn=ttk.Frame(right);btn.pack(fill="x",pady=(0,5))
        ttk.Button(btn,text="Abrir vaga",command=open_selected).pack(side="left")
        ttk.Button(btn,text="Restaurar manualmente",command=restore_selected).pack(side="left",padx=5)
        ttk.Button(btn,text="Restaurar todas",style="Primary.TButton",command=restore_all).pack(side="left",padx=5)

        ent.bind("<KeyRelease>",lambda e:load())
        compatibility_box.bind("<<ComboboxSelected>>",lambda e:load())
        tr.bind("<<TreeviewSelect>>",selected)
        load()

    def update_source_health(self,jobs):
        groups={}
        for j in jobs:
            f=j.get("fonte") or "Desconhecida"
            d=groups.setdefault(f,{"total":0,"empresa":0,"local":0,"descricao":0,"data":0,"modalidade_estruturada":0})
            d["total"]+=1
            if norm(j.get("empresa")) not in ("","nao informado"):d["empresa"]+=1
            if norm(j.get("local")) not in ("","nao informado","brasil"):d["local"]+=1
            if len((j.get("descricao") or "").strip())>=120:d["descricao"]+=1
            if j.get("data_publicacao"):d["data"]+=1
            if j.get("workplace_type"):d["modalidade_estruturada"]+=1

        health={}
        for f,d in groups.items():
            n=max(1,d["total"])
            health[f]={
                "total":d["total"],
                "empresa_pct":round(100*d["empresa"]/n),
                "local_pct":round(100*d["local"]/n),
                "descricao_pct":round(100*d["descricao"]/n),
                "data_pct":round(100*d["data"]/n),
                "modalidade_pct":round(100*d["modalidade_estruturada"]/n),
                "atualizado_em":datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        health.pop("Vagas.com.br",None);health.pop("Vagas.com",None)
        save_json_file(HEALTH_PATH,health)

    def show_source_health(self):
        health=load_json_file(HEALTH_PATH,{})
        if not health:
            messagebox.showinfo("Saúde das fontes","Faça uma busca primeiro.")
            return
        lines=[]
        for fonte,d in sorted(health.items(),key=lambda kv:-kv[1].get("total",0)):
            lines.append(
                f"{fonte}: {d.get('total',0)} vagas\\n"
                f"  empresa {d.get('empresa_pct',0)}% | local {d.get('local_pct',0)}% | "
                f"descrição {d.get('descricao_pct',0)}% | data {d.get('data_pct',0)}% | "
                f"modalidade estruturada {d.get('modalidade_pct',0)}%"
            )
        messagebox.showinfo("Saúde das fontes","\\n\\n".join(lines))

    def recalculate_all_jobs(self):
        """Reaplica o perfil atual sem alterar status, fila ou histórico do usuário."""
        rows=self.conn.execute("""SELECT id,titulo,empresa,local,descricao,url,fonte,data_publicacao,
                                  salario,COALESCE(workplace_type,'') FROM vagas""").fetchall()
        for vid,titulo,empresa,local,descricao,url,fonte,pub,salario,workplace in rows:
            job={"titulo":titulo or "","empresa":empresa or "","local":local or "",
                 "descricao":descricao or "","url":url or "","fonte":fonte or "",
                 "data_publicacao":pub or "","salario":salario or "","workplace_type":workplace or ""}
            score,label,reason,mode=score_job(job,self.p,self.cv)
            ld=location_decision(job,self.p)
            self.conn.execute("""UPDATE vagas SET score=?,classificacao=?,motivo=?,modalidade=?,categoria=?,
                                  decisao=?,confianca=?,location_confidence=?,location_evidence=? WHERE id=?""",
                              (score,label,reason,mode,job_category(job,self.p),decision_level(job,self.p,mode),
                               collection_confidence(job),ld["confidence"],ld["evidence"],vid))
        self.conn.commit();self.separate_outside_region_jobs();return len(rows)

    def recalculate_with_notice(self,parent=None):
        self.p=load_profile();self.load_feedback_profile();self.cv=read_cv()
        total=self.recalculate_all_jobs();self.refresh()
        messagebox.showinfo("Vagas reavaliadas",f"{total} vaga(s) foram reavaliadas com o currículo e as preferências atuais.",parent=parent)

    def update_pending_descriptions(self,limit=40,notify=True):
        if getattr(self,"description_update_running",False):
            if notify:messagebox.showinfo("Descrições","A atualização já está em andamento.")
            return
        self.description_update_running=True
        self.info.set("Atualizando descrições pendentes...")
        threading.Thread(target=self._update_pending_descriptions_worker,args=(limit,notify),daemon=True).start()

    def _update_pending_descriptions_worker(self,limit,notify=True):
        updated=failed=0
        try:
            rows=self.conn.execute("""SELECT id,url FROM vagas
                WHERE fonte='LinkedIn' AND LENGTH(TRIM(COALESCE(descricao,'')))<120
                  AND COALESCE(description_attempts,0)<4
                  AND (COALESCE(description_next_retry_at,'')='' OR description_next_retry_at<=?)
                ORDER BY COALESCE(description_attempts,0),id DESC LIMIT ?""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"),int(limit))).fetchall()
            for vid,url in rows:
                attempted=datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    detail=generic_job_from_url(url,"LinkedIn")
                    desc=(detail.get("descricao") or "").strip()
                    if len(desc)<120:raise RuntimeError("A página não disponibilizou uma descrição completa")
                    self.conn.execute("""UPDATE vagas SET descricao=?,description_status='disponivel',
                        description_attempts=description_attempts+1,description_last_error='',
                        description_last_attempt_at=?,description_next_retry_at='',description_source='LinkedIn detalhe'
                        WHERE id=?""",(desc,attempted,vid));updated+=1
                except Exception as error:
                    retry=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat(timespec="seconds")
                    self.conn.execute("""UPDATE vagas SET description_status='pendente',
                        description_attempts=description_attempts+1,description_last_error=?,
                        description_last_attempt_at=?,description_next_retry_at=? WHERE id=?""",
                        (str(error)[:300],attempted,retry,vid));failed+=1
                self.conn.commit();time.sleep(.8)
            if updated:self.recalculate_all_jobs()
            self.after(0,lambda:self._finish_description_update(updated,failed,notify=notify))
        except Exception as error:
            LOGGER.exception("Falha ao atualizar descrições pendentes")
            self.after(0,lambda:self._finish_description_update(updated,failed,str(error),notify))

    def _finish_description_update(self,updated,failed,error="",notify=True):
        self.description_update_running=False;self.refresh()
        self.info.set(f"Descrições: {updated} atualizadas, {failed} ainda pendentes")
        if notify:
            if error:messagebox.showwarning("Descrições",f"A atualização terminou com erro: {error}")
            else:messagebox.showinfo("Descrições",f"{updated} descrição(ões) atualizada(s).\n{failed} continuará(ão) pendente(s) para nova tentativa.")

    def run_source(self,src):
        try:
            self.p=load_profile();self.load_feedback_profile();self.cv=read_cv();jobs=self.collect(src)
            self.update_source_health(jobs)
            a=u=f=0;seen=set();seen_fp=set()
            for j in jobs:
                url=j.get("url") or ""
                if not url:continue
                key=url.split("?")[0]
                if key in seen:continue
                fp=job_fingerprint(j)
                if fp and fp in seen_fp:continue
                seen.add(key)
                if fp:seen_fp.add(fp)
                j["url"]=key
                ok,why=hard_filter(j,self.p)
                if not ok:
                    self.save_discarded(j,why)
                    fp=job_fingerprint(j)
                    self.conn.execute("""UPDATE vagas SET status='Ignorada',selecionada_lote=0,decisao='REVISAR'
                                         WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0
                                           AND (url=? OR (?!='' AND fingerprint=?))""",(j["url"],fp,fp))
                    f+=1;continue
                score,label,reason,mode=score_job(j,self.p,self.cv)
                location_info=location_decision(j,self.p)
                structured=structured_persistence(j,location_info)
                # Se já havia sido descartada em uma busca anterior e agora passou, remove do histórico ativo.
                self.conn.execute("""DELETE FROM descartadas WHERE url=?
                                     AND motivo_descarte!='Descartada pelo usuário'""",(j["url"],))
                category=job_category(j,self.p)
                decisao=decision_level(j,self.p,mode)
                confianca=collection_confidence(j)
                fp=job_fingerprint(j)
                fontes=j.get("fontes_encontradas") or j.get("fonte","")

                existing=None
                if fp:
                    existing=self.conn.execute("SELECT id,fonte,fontes FROM vagas WHERE fingerprint=? ORDER BY id LIMIT 1",(fp,)).fetchone()

                if existing:
                    vid,old_source,old_fontes=existing
                    all_sources=[]
                    for raw in (old_fontes,old_source,fontes,j.get("fonte","")):
                        for source_name in str(raw or "").split(" + "):
                            if source_name and source_name not in all_sources:all_sources.append(source_name)
                    self.conn.execute("""UPDATE vagas SET titulo=?,empresa=?,local=?,modalidade=?,descricao=?,
                        fonte=?,fontes=?,data_publicacao=?,salario=?,score=?,classificacao=?,motivo=?,
                        categoria=?,decisao=?,confianca=?,fingerprint=?,workplace_type=?,
                        location_confidence=?,location_evidence=?,workplace_type_raw=?,workplace_source=?,
                        structured_location_json=?,applicant_location_requirements=?,remote_eligible_brazil=?,
                        modality_checked_at=?,status=CASE WHEN status='Pesquisa limpa' THEN 'Nova' ELSE status END WHERE id=?""",
                        (j.get("titulo",""),j.get("empresa",""),j.get("local",""),mode,j.get("descricao",""),
                         j.get("fonte","")," + ".join(all_sources),j.get("data_publicacao",""),j.get("salario",""),
                         score,label,reason,category,decisao,confianca,fp,j.get("workplace_type",""),
                         location_info["confidence"],location_info["evidence"],*structured,vid))
                    u+=1
                else:
                    vals=(j.get("titulo",""),j.get("empresa",""),j.get("local",""),mode,j.get("descricao",""),
                           j["url"],j.get("fonte",""),fontes,j.get("data_publicacao",""),j.get("salario",""),
                           score,label,reason,category,decisao,confianca,fp,j.get("workplace_type",""),
                           location_info["confidence"],location_info["evidence"],*structured)
                    try:
                        self.conn.execute("""INSERT INTO vagas(titulo,empresa,local,modalidade,descricao,url,fonte,fontes,
                        data_publicacao,salario,score,classificacao,motivo,categoria,decisao,confianca,fingerprint,
                        workplace_type,location_confidence,location_evidence,workplace_type_raw,workplace_source,
                        structured_location_json,applicant_location_requirements,remote_eligible_brazil,
                        modality_checked_at,status)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'Nova')""",vals);a+=1
                    except sqlite3.IntegrityError:
                        self.conn.execute("""UPDATE vagas SET titulo=?,empresa=?,local=?,modalidade=?,descricao=?,
                            fonte=?,fontes=?,data_publicacao=?,salario=?,score=?,classificacao=?,motivo=?,
                            categoria=?,decisao=?,confianca=?,fingerprint=?,workplace_type=?,
                            location_confidence=?,location_evidence=?,workplace_type_raw=?,workplace_source=?,
                            structured_location_json=?,applicant_location_requirements=?,remote_eligible_brazil=?,
                            modality_checked_at=?,status=CASE WHEN status='Pesquisa limpa' THEN 'Nova' ELSE status END WHERE url=?""",
                            (j.get("titulo",""),j.get("empresa",""),j.get("local",""),mode,j.get("descricao",""),
                             j.get("fonte",""),fontes,j.get("data_publicacao",""),j.get("salario",""),score,label,
                             reason,category,decisao,confianca,fp,j.get("workplace_type",""),
                             location_info["confidence"],location_info["evidence"],*structured,j["url"]));u+=1
            self.conn.execute("""UPDATE vagas SET description_status=CASE
                WHEN LENGTH(TRIM(COALESCE(descricao,'')))>=120 THEN 'disponivel'
                WHEN fonte='LinkedIn' THEN 'pendente' ELSE 'indisponivel' END,
                description_source=CASE WHEN LENGTH(TRIM(COALESCE(descricao,'')))>=120
                                        THEN fonte ELSE COALESCE(description_source,'') END
                WHERE COALESCE(description_status,'')='' OR description_status!='disponivel'""")
            self.conn.commit()
            self.after(0,lambda:self.finish(a,u,f,len(jobs),src))
        except Exception as e:
            LOGGER.exception("Falha durante a busca: %s",src)
            error_msg=str(e)
            self.after(0,lambda msg=error_msg:self.fail(msg))

    def finish(self,a,u,f,total,src):
        self.search_running=False;self.search_button.configure(state="normal")
        self.stop_search_animation()
        self.p=load_profile()
        self.apply_internship_preference(bool(self.p.get("buscar_estagios",True)))
        self.prog.stop();self.refresh()
        rec=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0 AND decisao='APROVADA'").fetchone()[0]
        rev=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE status='Nova' AND COALESCE(selecionada_lote,0)=0 AND decisao='REVISAR'").fetchone()[0]
        self.info.set(f"Busca concluída: {rec} recomendadas • {rev} para conferir • {f} fora do perfil nesta busca")
        if total and src in ("all","linkedin"):
            self.after(350,lambda:self.update_pending_descriptions(limit=20,notify=False))
        if total==0:
            messagebox.showwarning("Fonte sem resultados",f"A fonte '{src}' não retornou resultados nesta tentativa.\n\nGoogle e LinkedIn podem limitar consultas automatizadas temporariamente.")

    def fail(self,e):
        self.search_running=False;self.search_button.configure(state="normal")
        self.stop_search_animation()
        self.prog.stop();self.info.set("Não conseguimos buscar vagas agora.")
        messagebox.showerror("Não foi possível buscar","Não conseguimos buscar vagas agora. Tente novamente.\n\nOs detalhes foram registrados no diagnóstico.")

    def start_search_animation(self):
        self.search_button.configure(text="Buscando…")
        if not self.search_activity.winfo_ismapped():self.search_activity.pack(side="left",padx=20)
        self.search_animation_frame=0
        def animate():
            if not self.search_running:return
            frames=("◐","◓","◑","◒")
            self.search_spinner.set(frames[self.search_animation_frame%len(frames)])
            self.search_animation_frame+=1
            self.search_animation_job=self.after(140,animate)
        animate()

    def stop_search_animation(self):
        if self.search_animation_job:
            try:self.after_cancel(self.search_animation_job)
            except tk.TclError:pass
        self.search_animation_job=None;self.search_button.configure(text="Buscar vagas")
        self.search_activity.pack_forget()


    def update_dashboard_counts(self):
        try:
            rec=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE decisao='APROVADA' AND status='Nova' AND COALESCE(selecionada_lote,0)=0").fetchone()[0]
            rev=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE decisao='REVISAR' AND status='Nova' AND COALESCE(selecionada_lote,0)=0").fetchone()[0]
            appc=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE status IN ('Candidatado','Entrevista','Rejeitado')").fetchone()[0]
            out=self.conn.execute("SELECT COUNT(*) FROM descartadas").fetchone()[0]
            discarded=self.conn.execute("SELECT COUNT(*) FROM descartadas WHERE motivo_descarte=?",
                                        ("Descartada pelo usuário",)).fetchone()[0]
            self.stat_rec.set(f"Recomendadas: {rec}")
            self.stat_rev.set(f"Vale conferir: {rev}")
            self.stat_app.set(f"Candidaturas: {appc}")
            self.stat_out.set(f"Fora do perfil: {out}")
            self.stat_discarded.set(f"Descartadas: {discarded}")
        except Exception:
            pass

    def refresh(self):
        if not hasattr(self,"tree"):return
        for x in self.tree.get_children():self.tree.delete(x)

        view=self.view_mode.get() if hasattr(self,"view_mode") else "todas"
        sql,pa=jobs_query(view,self.q.get())

        for vid,score,titulo,empresa,local,modo,cat,status,queued,published_at in self.conn.execute(sql,pa):
            lm=simple_location_mode(local,modo)
            tag="great" if (score or 0)>=80 else "possible"
            checked=vid in self.batch_selection if hasattr(self,"batch_selection") else bool(queued)
            published=format_date_br(published_at)
            if published=="Data não informada":published="Não informada"
            self.tree.insert("","end",iid=str(vid),values=("☑" if checked else "☐",f"{score}%",titulo,empresa,lm,published),tags=(tag,))
        if self.job_sort_state["column"]:
            self.sort_jobs(self.job_sort_state["column"],self.job_sort_state["reverse"])
        self.update_dashboard_counts()

    def select(self,e=None):
        sel=self.tree.selection()
        if not sel:return
        self.current=int(sel[0])
        row=self.conn.execute("""SELECT titulo,empresa,local,modalidade,descricao,score,classificacao,status,salario,
                                COALESCE(location_evidence,''),COALESCE(data_publicacao,''),COALESCE(fonte,''),
                                COALESCE(confianca,'Baixa'),COALESCE(description_status,'')
                                FROM vagas WHERE id=?""",(self.current,)).fetchone()
        if not row:return
        t,emp,loc,mode,desc,score,cl,status,salario,location_evidence,published_at,source,confidence,description_status=row
        self.tv.set(f"{t}")
        model_detail=f" | Motivo: {location_evidence}" if mode=="Verificar modelo" and location_evidence else ""
        self.meta.set(f"{emp or 'Empresa não informada'} | {simple_location_mode(loc,mode)} | Publicação: {format_date_br(published_at)}{model_detail}")
        description_note=" • Descrição incompleta" if description_status!="disponivel" or len((desc or "").strip())<120 else ""
        self.data_quality.set(f"Fonte: {source or 'não informada'} • Qualidade dos dados: {confidence or 'Baixa'}{description_note}")
        self.desc_box.configure(state="normal");self.desc_box.delete("1.0","end");self.desc_box.insert("1.0",(desc or "Descrição ainda não disponível. Use Configurações > Atualizar descrições pendentes para tentar novamente.").strip());self.desc_box.configure(state="disabled")
        reqs=extract_requirements({"titulo":t or "","descricao":desc or ""})
        reqtxt="\n".join("• "+x[0] for x in reqs) if reqs else "Requisitos não identificados separadamente."
        self.req_box.configure(state="normal");self.req_box.delete("1.0","end");self.req_box.insert("1.0",reqtxt);self.req_box.configure(state="disabled")
        pay,bens=salary_and_benefits({"salario":salario or "","descricao":desc or ""})
        paytxt="Salário: "+pay
        if bens: paytxt+="\n"+"\n".join("• "+b for b in bens)
        else: paytxt+="\nBenefícios não identificados."
        self.pay_box.configure(state="normal");self.pay_box.delete("1.0","end");self.pay_box.insert("1.0",paytxt);self.pay_box.configure(state="disabled")

    def open_job(self):
        if not self.current:return
        row=self.conn.execute("SELECT url FROM vagas WHERE id=?",(self.current,)).fetchone()
        if row and row[0]:webbrowser.open(row[0])

    def set_status(self,st):
        if self.current:
            self.conn.execute("UPDATE vagas SET status=? WHERE id=?",(st,self.current));self.conn.commit();self.refresh()

    def discard_current(self):
        if not self.current:return
        row=self.conn.execute("""SELECT titulo,empresa,local,descricao,url,fonte,data_publicacao,salario
                                 FROM vagas WHERE id=?""",(self.current,)).fetchone()
        if not row:return
        if not messagebox.askyesno("Descartar vaga","Mover esta vaga para Descartadas?\n\nVocê poderá restaurá-la depois."):
            return
        t,e,l,d,u,f,dt,sal=row
        self.record_feedback(self.current,False)
        self.save_discarded({"titulo":t,"empresa":e,"local":l,"descricao":d,"url":u,
                             "fonte":f,"data_publicacao":dt,"salario":sal},"Descartada pelo usuário")
        with self.conn:
            self.conn.execute("UPDATE vagas SET status='Ignorada',selecionada_lote=0 WHERE id=?",(self.current,))
        if "batch_selection" in self.__dict__:self.batch_selection.discard(self.current);self.update_queue_action()
        self.current=None;self.info.set("Vaga movida para Descartadas.");self.refresh()

    def archive_application(self,vid):
        with self.conn:
            self.conn.execute("UPDATE vagas SET status='Arquivada',selecionada_lote=0 WHERE id=?",(vid,))
        if "batch_selection" in self.__dict__:self.batch_selection.discard(vid);self.update_queue_action()
        self.refresh()

    def remove_old_jobs(self):
        p=load_profile();max_days=int(p.get("idade_maxima_vaga_dias",60))
        rows=self.conn.execute("SELECT id,data_publicacao FROM vagas").fetchall()
        removed=unknown=kept=0
        for vid,pub in rows:
            age=vacancy_age_days(pub)
            if age is None:
                unknown+=1
            elif age>max_days:
                self.conn.execute("DELETE FROM vagas WHERE id=?",(vid,));removed+=1
            else:
                kept+=1
        self.conn.commit();self.refresh()
        messagebox.showinfo("Filtro de tempo",
            f"Limite atual: {max_days} dias.\\n\\n"
            f"{removed} vagas antigas removidas.\\n"
            f"{kept} vagas dentro do prazo.\\n"
            f"{unknown} vagas sem data confiável foram mantidas.")

    def revalidate_modes(self):
        self.p=load_profile()
        rows=self.conn.execute("""SELECT id,titulo,empresa,local,descricao,fonte,url,
                                  data_publicacao,salario,COALESCE(workplace_type,''),
                                  COALESCE(workplace_type_raw,''),COALESCE(workplace_source,''),
                                  COALESCE(structured_location_json,''),
                                  COALESCE(applicant_location_requirements,'') FROM vagas""").fetchall()
        kept=removed=0
        reasons={}
        for r in rows:
            (vid,titulo,empresa,local,descricao,fonte,url,pub,salario,workplace_type,
             workplace_raw,workplace_source,structured_location,applicant_requirements)=r
            job={"titulo":titulo or "","empresa":empresa or "","local":local or "",
                 "descricao":descricao or "","fonte":fonte or "","url":url or "",
                 "data_publicacao":pub or "","salario":salario or "","workplace_type":workplace_type or "",
                 "workplace_type_raw":workplace_raw or "","workplace_source":workplace_source or "",
                 "structured_location_json":structured_location or "",
                 "applicant_location_requirements":applicant_requirements or "",
                 "source_brazil": fonte in ("Gupy","LinkedIn","Google","Indeed/Google")}
            ok,why=hard_filter(job,self.p)
            if ok:
                ld=location_decision(job,self.p);mode=ld["mode"]
                decision=decision_level(job,self.p,mode)
                structured=structured_persistence(job,ld)
                self.conn.execute("""UPDATE vagas SET modalidade=?,decisao=?,location_confidence=?,
                                     location_evidence=?,workplace_type_raw=?,workplace_source=?,
                                     structured_location_json=?,applicant_location_requirements=?,
                                     remote_eligible_brazil=?,modality_checked_at=? WHERE id=?""",
                                  (mode,decision,ld["confidence"],ld["evidence"],*structured,vid));kept+=1
            else:
                discarded_job={"titulo":titulo or "","empresa":empresa or "","local":local or "",
                               "descricao":descricao or "","fonte":fonte or "","url":url or "",
                               "data_publicacao":pub or "","salario":salario or ""}
                self.save_discarded(discarded_job,why)
                self.conn.execute("DELETE FROM vagas WHERE id=?",(vid,));removed+=1
                reasons[why]=reasons.get(why,0)+1
        self.conn.commit()
        self.refresh()
        details="\n".join(f"• {k}: {v}" for k,v in sorted(reasons.items(),key=lambda x:-x[1])[:7])
        messagebox.showinfo("Revalidação concluída",
            f"{kept} vagas permaneceram.\n{removed} vagas foram removidas."
            + (f"\n\nPrincipais motivos:\n{details}" if details else ""))


    def select_batch(self):
        cutoff=int(load_profile().get("score_lote_padrao",75))
        self.conn.execute("UPDATE vagas SET selecionada_lote=0")
        self.conn.execute("""UPDATE vagas SET selecionada_lote=1
                             WHERE score>=? AND status='Nova' AND decisao='APROVADA'
                             AND (
                               modalidade LIKE 'Remoto Brasil%'
                               OR modalidade LIKE 'Presencial%confirmado'
                               OR modalidade LIKE 'Híbrido%confirmado'
                             )""",(cutoff,))
        self.conn.commit()
        if "batch_selection" in self.__dict__:
            self.batch_selection={r[0] for r in self.conn.execute(
                "SELECT id FROM vagas WHERE selecionada_lote=1 AND status='Nova'").fetchall()}
            self.update_queue_action();self.refresh()
        n=self.conn.execute("SELECT COUNT(*) FROM vagas WHERE selecionada_lote=1 AND status='Nova'").fetchone()[0]
        messagebox.showinfo("Fila preparada",f"{n} vagas foram adicionadas à fila com score mínimo de {cutoff}%.")

    def show_applications(self):
        win,created=self.managed_window("candidaturas","Minhas candidaturas","1120x650")
        if not created:return
        body=ttk.Frame(win,padding=18);body.pack(fill="both",expand=True)
        head=ttk.Frame(body);head.pack(fill="x",pady=(0,14))
        title=ttk.Frame(head);title.pack(side="left")
        ttk.Label(title,text="Minhas candidaturas",font=("Segoe UI",18,"bold")).pack(anchor="w")
        summary=tk.StringVar(value="Nenhuma candidatura registrada")
        ttk.Label(title,textvariable=summary,foreground="#66788a").pack(anchor="w",pady=(2,0))
        ttk.Button(head,text="Voltar às vagas",command=win._managed_close).pack(side="right")

        cols=("data","titulo","empresa","remove")
        table_frame=ttk.Frame(body,style="Panel.TFrame",padding=1);table_frame.pack(fill="both",expand=True)
        tr=ttk.Treeview(table_frame,columns=cols,show="headings",selectmode="browse")
        self.applications_tree=tr
        for col,label,width in [("data","DATA",110),("titulo","VAGA",440),("empresa","EMPRESA",300),("remove","AÇÃO",90)]:
            tr.heading(col,text=label);tr.column(col,width=width,anchor="center" if col=="remove" else "w")
        scroll=ttk.Scrollbar(table_frame,orient="vertical",command=tr.yview);tr.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y");tr.pack(side="left",fill="both",expand=True)

        def load():
            for item in tr.get_children():tr.delete(item)
            rows=self.conn.execute("""SELECT id,titulo,empresa,COALESCE(candidatura_em,'')
                                    FROM vagas WHERE status IN ('Candidatado','Entrevista','Rejeitado')
                                    ORDER BY COALESCE(NULLIF(candidatura_em,''),criada_em) DESC,id DESC""").fetchall()
            for vid,job,company,applied_at in rows:
                date_text="Data não registrada"
                if applied_at:
                    try:date_text=datetime.fromisoformat(applied_at.replace("Z","+00:00")).strftime("%d/%m/%Y")
                    except Exception:date_text=applied_at[:10]
                tr.insert("","end",iid=str(vid),values=(date_text,job,company,"Remover"))
            summary.set(f"{len(rows)} candidatura(s) registrada(s)" if rows else "Nenhuma candidatura registrada")

        def open_selected(_event=None):
            selected=tr.selection()
            if not selected:return
            row=self.conn.execute("SELECT url FROM vagas WHERE id=?",(int(selected[0]),)).fetchone()
            if row and row[0]:webbrowser.open(row[0])

        def remove_selected():
            selected=tr.selection()
            if not selected:return
            if not messagebox.askyesno("Remover do resumo",
                "Remover esta vaga de Minhas candidaturas?\n\nO registro será arquivado, não apagado.",parent=win):return
            self.archive_application(int(selected[0]));load()

        def click_action(event):
            if tr.identify_region(event.x,event.y)!="cell" or tr.identify_column(event.x)!="#4":return
            iid=tr.identify_row(event.y)
            if not iid:return "break"
            tr.selection_set(iid);remove_selected();return "break"

        actions=ttk.Frame(body);actions.pack(fill="x",pady=(10,0))
        ttk.Button(actions,text="Abrir vaga selecionada",command=open_selected).pack(side="left")
        ttk.Button(actions,text="Atualizar resumo",command=load).pack(side="left",padx=6)
        tr.bind("<Button-1>",click_action,add="+");tr.bind("<Double-1>",open_selected);load()

    def show_batch(self):
        win,created=self.managed_window("fila","Fila de candidaturas","1050x560")
        if not created:return
        cols=("score","titulo","empresa","modalidade","resultado","remove")
        tr=ttk.Treeview(win,columns=cols,show="headings")
        for c,t,w in [("score","Score",60),("titulo","Título",300),("empresa","Empresa",180),
                      ("modalidade","Modalidade",150),("resultado","Último resultado",230),("remove","Ação",90)]:
            tr.heading(c,text=t);tr.column(c,width=w,anchor="center" if c=="remove" else "w")
        tr.pack(fill="both",expand=True,padx=8,pady=8)
        def load():
            for item in tr.get_children():tr.delete(item)
            rows=self.conn.execute("""SELECT id,score,titulo,empresa,modalidade,COALESCE(ultimo_resultado,'')
                                    FROM vagas WHERE selecionada_lote=1 ORDER BY score DESC""").fetchall()
            for vid,score,title,company,mode,result in rows:
                tr.insert("","end",iid=str(vid),values=(score,title,company,mode,result,"Remover"))
        def remove_selected():
            selected=tr.selection()
            if not selected:return
            self.remove_from_batch(int(selected[0]));load()
        def click_action(event):
            if tr.identify_region(event.x,event.y)!="cell" or tr.identify_column(event.x)!="#6":return
            iid=tr.identify_row(event.y)
            if iid:tr.selection_set(iid);remove_selected();return "break"
        tr.bind("<Button-1>",click_action,add="+");load()
        footer=ttk.Frame(win,padding=(8,0,8,8));footer.pack(fill="x")
        ttk.Label(footer,text="A fila não envia respostas desconhecidas, CAPTCHAs ou declarações por você.").pack(side="left")
        def clear_and_close():
            if self.clear_batch():win._managed_close()
        ttk.Button(footer,text="Limpar fila",style="Danger.TButton",command=clear_and_close).pack(side="right")
        ttk.Button(footer,text="Remover selecionada",command=remove_selected).pack(side="right",padx=6)

    def wait_for_user_review(self,titulo,vid):
        """
        Called by worker thread. Opens a Tk dialog on the UI thread and truly
        waits until the user chooses what to do before proceeding.
        """
        done=threading.Event()
        action={"value":"next"}

        def show():
            try:
                self.deiconify();self.lift();self.focus_force()
                win=tk.Toplevel(self);win.title("Confirmar candidatura");win.transient(self);win.withdraw()
                win.resizable(False,False)
                card=ttk.Frame(win,padding=(18,15,18,14));card.pack(fill="both",expand=True)
                ttk.Label(card,text="Você concluiu esta candidatura?",font=("Segoe UI",13,"bold")).pack(anchor="w")
                ttk.Label(card,text=titulo,font=("Segoe UI",10,"bold"),wraplength=540).pack(anchor="w",pady=(8,4))
                ttk.Label(card,text="Revise a vaga no navegador e informe o resultado. Assim a fila e Minhas candidaturas serão atualizadas.",
                          wraplength=540).pack(anchor="w",pady=(0,12))
                ttk.Separator(card).pack(fill="x",pady=(0,12))
                b=ttk.Frame(card);b.pack(fill="x")
                for column in range(3):b.columnconfigure(column,weight=1,uniform="review")

                def finish(value):
                    action["value"]=value
                    try:win.grab_release();win.destroy()
                    finally:done.set()

                ttk.Button(b,text="Sim, candidatei-me",style="Primary.TButton",command=lambda:finish("applied")).grid(row=0,column=0,sticky="ew",padx=(0,5))
                ttk.Button(b,text="Ainda não",command=lambda:finish("skip")).grid(row=0,column=1,sticky="ew",padx=5)
                ttk.Button(b,text="Parar lote",command=lambda:finish("stop")).grid(row=0,column=2,sticky="ew",padx=(5,0))
                win.protocol("WM_DELETE_WINDOW",lambda:finish("skip"))
                win.update_idletasks();self.center_window(win,580,win.winfo_reqheight());win.deiconify()
                win.attributes("-topmost",True);win.grab_set()
                win.after(100,lambda:(win.lift(),win.focus_force(),self.bell()))
            except Exception:
                LOGGER.exception("Falha ao exibir confirmação da candidatura")
                action["value"]="stop";done.set()

        self.after(0,show)
        done.wait()
        if action["value"]=="applied":
            self.mark_application_completed(vid)
            self.after(0,self.sync_batch_selection)
        return action["value"]

    def start_batch(self):
        rows=self.conn.execute("""SELECT id FROM vagas WHERE selecionada_lote=1 AND status='Nova'
                                  ORDER BY score DESC""").fetchall()
        if not rows:
            messagebox.showinfo("Fila vazia","Adicione vagas à fila antes de iniciar o lote.")
            return
        p=load_profile();limit=int(p.get("max_candidaturas_sessao",20))
        if not messagebox.askyesno("Iniciar lote",
            f"Há {len(rows)} vagas na fila.\n\nNesta sessão serão abertas no máximo {limit}.\n"
            "O programa preencherá dados conhecidos e anexará o currículo. "
            "O envio automático fica DESATIVADO por padrão.\n\nContinuar?"):
            return
        threading.Thread(target=self.run_batch,args=([r[0] for r in rows[:limit]],),daemon=True).start()

    def run_batch(self,ids):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.after(0,lambda:messagebox.showerror("Playwright",
                "Playwright não está instalado corretamente. Execute preparar_navegador.bat."))
            return

        p=load_profile()
        try:
            browser_cfg=get_browser_launch_settings(p)
            profile_dir=browser_cfg["profile_dir"]
            os.makedirs(profile_dir,exist_ok=True)
        except Exception as e:
            self.after(0,lambda:messagebox.showerror("Navegador",str(e)))
            return

        try:
            with sync_playwright() as pw:
                launch_args={"user_data_dir":profile_dir,"headless":False}
                if browser_cfg.get("executable_path"):
                    launch_args["executable_path"]=browser_cfg["executable_path"]
                browser_type=pw.firefox if browser_cfg["browser"]=="firefox" else pw.chromium
                ctx=browser_type.launch_persistent_context(**launch_args)
                page=ctx.pages[0] if ctx.pages else ctx.new_page()
                close_previous=False

                for idx,vid in enumerate(ids,1):
                    if idx>1:
                        previous_page=page
                        page=ctx.new_page()
                        page.bring_to_front()
                        if close_previous:
                            try:previous_page.close()
                            except Exception:pass
                        close_previous=False
                    row=self.conn.execute("""SELECT titulo,url,empresa,descricao,local,salario
                                             FROM vagas WHERE id=?""",(vid,)).fetchone()
                    if not row:continue
                    titulo,url,empresa,descricao,local,salario=row
                    self.after(0,lambda i=idx,t=titulo:
                        self.info.set(f"Candidatura {i}/{len(ids)}: {t}"))
                    result="";page_opened=False;review_shown=False

                    try:
                        page_opened=True
                        page.goto(url,wait_until="domcontentloaded",timeout=45000)
                        page.wait_for_timeout(2200)
                        content=norm(page.locator("body").inner_text(timeout=8000))

                        # Live validity check: pages may have closed after collection.
                        invalid=live_page_invalid_reason(page)
                        if invalid:
                            result="Pulada: "+invalid
                            self.conn.execute("""UPDATE vagas SET selecionada_lote=0,
                                               ultimo_resultado=?,tentativas_envio=tentativas_envio+1
                                               WHERE id=?""",(result,vid))
                            self.conn.commit()
                            continue

                        if any(x in content for x in [
                            "captcha","verify you are human","verifique que voce e humano",
                            "security check","confirme que voce e humano"
                        ]):
                            result="Revisão necessária: CAPTCHA/verificação humana"
                        else:
                            filled=autofill_known_fields(page,p)
                            files=attach_resume(page,p)
                            unknown=find_unknown_required_fields(page)
                            if unknown and p.get("parar_em_pergunta_desconhecida",True):
                                result=f"Revisão necessária: {len(unknown)} campo(s) obrigatório(s) sem resposta"
                            else:
                                result=f"Pronto para revisão; preenchidos={filled}, anexos={files}"

                        self.conn.execute("""UPDATE vagas SET tentativas_envio=tentativas_envio+1,
                                           ultimo_resultado=? WHERE id=?""",(result,vid))
                        self.conn.commit()

                        # Crucial V7.4 fix: actually WAIT for the user's decision.
                        review_shown=True
                        action=self.wait_for_user_review(titulo,vid)
                        if action=="stop":
                            self.after(0,lambda:self.info.set("Lote interrompido pelo usuário"))
                            break
                        close_previous=(action=="applied")
                        if idx<len(ids):
                            self.after(0,lambda:self.info.set("Abrindo a próxima vaga..."))

                        # O próximo link abre logo após a confirmação, sem depender do site anterior.
                        time.sleep(.2)

                    except Exception as e:
                        result="Erro: "+str(e)[:180]
                        LOGGER.exception("Falha ao preparar candidatura para a vaga %s",vid)
                        self.conn.execute("""UPDATE vagas SET tentativas_envio=tentativas_envio+1,
                                           ultimo_resultado=? WHERE id=?""",(result,vid))
                        self.conn.commit()
                        # A página pode ter aberto mesmo quando um seletor/preenchimento falhou.
                        # Nesse caso a confirmação continua obrigatória para não perder a candidatura manual.
                        if page_opened and not review_shown:
                            action=self.wait_for_user_review(titulo,vid)
                            if action=="stop":
                                self.after(0,lambda:self.info.set("Lote interrompido pelo usuário"));break
                            close_previous=(action=="applied")
                        continue

                try:ctx.close()
                except:pass

            self.after(0,lambda:self.info.set("Lote concluído"))
            self.after(0,self.refresh)

        except Exception as e:
            LOGGER.exception("Falha geral no lote de candidaturas")
            self.after(0,lambda:messagebox.showerror("Não foi possível continuar","Não conseguimos abrir essa vaga. Tente novamente.\n\nOs detalhes foram registrados no diagnóstico."))


    def edit_profile(self):
        w,created=self.managed_window("configuracoes","Configurações","620x470",modal=True)
        if not created:return
        body=ttk.Frame(w,padding=16);body.pack(fill="both",expand=True)
        ttk.Label(body,text="Configurações",font=("Segoe UI",15,"bold")).pack(anchor="w")
        ttk.Label(body,text="Ajuste apenas o necessário. O restante é definido pelo currículo.").pack(anchor="w",pady=(2,14))

        cvf=ttk.LabelFrame(body,text="Currículo",padding=10);cvf.pack(fill="x",pady=(0,10))
        cvstatus=tk.StringVar(value="Currículo carregado" if self.cv.strip() else "Nenhum currículo carregado")
        ttk.Label(cvf,textvariable=cvstatus).pack(side="left")
        def load_cv_click():
            path=filedialog.askopenfilename(title="Escolha seu currículo",filetypes=[("Currículo","*.pdf *.docx *.txt"),("PDF","*.pdf"),("Word","*.docx"),("Texto","*.txt")])
            if not path:return
            try:
                text=parse_cv_file(path)
                if len(text.strip())<80:raise RuntimeError("O currículo parece estar vazio ou não pôde ser lido.")
                open(CV_PATH,"w",encoding="utf-8").write(text)
                ext=os.path.splitext(path)[1].lower(); dest=os.path.join(BASE_DIR,"curriculo_original"+ext)
                import shutil; shutil.copy2(path,dest)
                self.p["arquivo_curriculo_original"]=os.path.basename(dest)
                self.cv=text
                prof=adapt_profile_to_cv(self.p,text);save_json_file(PROFILE_PATH,self.p)
                recalculated=self.recalculate_all_jobs();self.refresh()
                cvstatus.set("Currículo carregado — perfil atualizado")
                areas.set(", ".join(prof["areas"]))
                messagebox.showinfo("Currículo pronto",f"Currículo lido com sucesso. A busca foi adaptada ao seu perfil e {recalculated} vaga(s) foram reavaliadas.",parent=w)
            except Exception as e:messagebox.showerror("Não foi possível carregar",str(e),parent=w)
        ttk.Button(cvf,text="Carregar meu currículo",command=load_cv_click).pack(side="right")
        areas=tk.StringVar(value=", ".join(self.p.get("areas_curriculo_detectadas",[])) or "Será identificado pelo currículo")
        ttk.Label(body,text="Áreas identificadas:").pack(anchor="w")
        ttk.Label(body,textvariable=areas,wraplength=560).pack(anchor="w",pady=(0,12))

        locf=ttk.LabelFrame(body,text="Onde quero trabalhar",padding=10);locf.pack(fill="x",pady=(0,10))
        ttk.Label(locf,text="Cidades para presencial/híbrido (separadas por vírgula)").pack(anchor="w")
        cities=tk.StringVar(value=", ".join(self.p.get("cidades_presencial",self.p.get("cidades_presencial_hibrido",[]))))
        location_row=ttk.Frame(locf);location_row.pack(fill="x",pady=(3,7))
        ttk.Entry(location_row,textvariable=cities).pack(side="left",fill="x",expand=True)
        ttk.Label(location_row,text="UF").pack(side="left",padx=(10,4))
        state=tk.StringVar(value=str(self.p.get("estado_local","")).upper())
        ttk.Entry(location_row,textvariable=state,width=4).pack(side="left")
        remote=tk.BooleanVar(value=self.p.get("aceitar_remoto",True));ttk.Checkbutton(locf,text="Aceito vagas remotas",variable=remote).pack(anchor="w")
        internships=tk.BooleanVar(value=self.p.get("buscar_estagios",True))
        ttk.Checkbutton(locf,text="Buscar estágios",variable=internships).pack(anchor="w",pady=(4,0))

        advanced=ttk.Frame(body)
        navf=ttk.LabelFrame(advanced,text="Navegador para candidaturas",padding=10);navf.pack(fill="x",pady=(8,10))
        ttk.Label(navf,text="Automático é recomendado. O app tenta usar um navegador instalado e, se necessário, o Chromium.").pack(anchor="w")
        browser_choice=tk.StringVar(value=self.p.get("navegador_automacao","Automático"))
        browser_combo=ttk.Combobox(navf,textvariable=browser_choice,state="readonly",width=24,
                                  values=["Automático","Google Chrome","Microsoft Edge","Brave","Chromium interno","Firefox"])
        browser_combo.pack(anchor="w",pady=(5,0))


        agef=ttk.Frame(advanced);agef.pack(fill="x",pady=(2,10))
        ttk.Label(agef,text="Mostrar vagas publicadas nos últimos").pack(side="left")
        days=tk.StringVar(value=str(self.p.get("idade_maxima_dias",self.p.get("max_age_days",60))))
        ttk.Entry(agef,textvariable=days,width=5).pack(side="left",padx=5);ttk.Label(agef,text="dias").pack(side="left")

        def save():
            vals=[x.strip() for x in cities.get().split(",") if x.strip()]
            self.p["cidades_presencial"]=vals;self.p["cidades_presencial_hibrido"]=vals
            self.p["estado_local"]=state.get().strip().upper()[:2]
            self.p["aceitar_remoto"]=bool(remote.get())
            self.p["buscar_estagios"]=bool(internships.get())
            self.p["mostrar_compativeis_fora_regiao"]=False
            browser_map={"Automático":"automatico","Google Chrome":"chrome","Microsoft Edge":"edge",
                         "Brave":"brave","Chromium interno":"chromium","Firefox":"firefox"}
            self.p["navegador_automacao"]=browser_map.get(browser_choice.get(),"automatico")
            try:self.p["idade_maxima_dias"]=max(1,int(days.get()))
            except:pass
            if self.cv.strip():adapt_profile_to_cv(self.p,self.cv)
            save_json_file(PROFILE_PATH,self.p)
            self.apply_internship_preference(bool(internships.get()));self.recalculate_all_jobs();self.refresh()
            messagebox.showinfo("Configurações","Alterações salvas.",parent=w);w._managed_close()
        maintenance=ttk.Frame(advanced);maintenance.pack(fill="x",pady=(0,8))
        ttk.Button(maintenance,text="Atualizar descrições pendentes",command=lambda:self.update_pending_descriptions()).pack(side="left")
        ttk.Button(maintenance,text="Reavaliar vagas",command=lambda:self.recalculate_with_notice(w)).pack(side="left",padx=6)

        advanced_text=tk.StringVar(value="Mostrar opções avançadas")
        def toggle_advanced():
            if advanced.winfo_manager():
                advanced.pack_forget();advanced_text.set("Mostrar opções avançadas");self.center_window(w,620,470)
            else:
                advanced.pack(fill="x",before=actions);advanced_text.set("Ocultar opções avançadas");self.center_window(w,620,650)

        actions=ttk.Frame(body);actions.pack(fill="x",pady=8)
        ttk.Button(actions,textvariable=advanced_text,style="Soft.TButton",command=toggle_advanced).pack(side="left")
        ttk.Button(actions,text="Salvar",style="Primary.TButton",command=save).pack(side="right")

    def edit_cv(self):
        os.startfile(CV_PATH) if os.name=="nt" else webbrowser.open("file://"+CV_PATH)

if __name__=="__main__":
    App().mainloop()
