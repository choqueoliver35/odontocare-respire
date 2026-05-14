from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3, os, random, re, unicodedata, json, hashlib

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'data' / 'odontocare_respire.sqlite3'
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '35')) * 1024 * 1024
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-cambiar')

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@odontocare.edu.bo')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Ollama / DeepSeek
USE_OLLAMA = os.getenv('USE_OLLAMA', '0') == '1'
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'deepseek-r1:1.5b')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
# Motor documental local: permite subir PDFs y responder solo con fragmentos recuperados.
KNOWLEDGE_DIR = BASE_DIR / 'knowledge_base'
UPLOAD_DIR = BASE_DIR / 'data' / 'uploads'
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '35'))
ALLOWED_DOC_EXT = {'.pdf', '.txt'}

DEVS = [
    'Mijail Oliver Choque Amaro',
    'Luis Álvarez Medina',
    'Ever Moya Icono Miranda',
    'Rodrigo Brian Rojas Aliaga',
    'Daniel Condori Laura'
]

TOPICS = {
    'historia_clinica': {
        'label':'Historia clínica odontológica',
        'keys':['historia clinica','historia clínica','anamnesis','filiacion','filiación','motivo de consulta','enfermedad actual','antecedentes personales','antecedentes familiares','antecedentes patologicos','antecedentes patológicos','antecedentes odontologicos','antecedentes odontológicos','alergias','medicacion','medicación','examen extraoral','examen intraoral','odontograma','periodontograma','diagnostico presuntivo','diagnóstico presuntivo','diagnostico definitivo','diagnóstico definitivo','plan de tratamiento','consentimiento informado','evolucion clinica','evolución clínica','registro clinico','registro clínico','signos vitales','interconsulta','historial medico','historial médico'],
        'definition':'La historia clínica odontológica es el registro ordenado de la información del paciente, sus antecedentes, el motivo de consulta, la enfermedad actual, el examen clínico, el diagnóstico y el plan de tratamiento.',
        'base':'Debe diferenciar datos subjetivos del paciente y hallazgos objetivos. Su estructura permite tomar decisiones clínicas y dejar evidencia académica del caso.'
    },
    'endodoncia': {
        'label':'Endodoncia y diagnóstico pulpar',
        'keys':['endodoncia','pulpa','pulpar','pulpitis','pulpitis reversible','pulpitis irreversible','necrosis','necrosis pulpar','dolor nocturno','dolor espontaneo','dolor espontáneo','dolor al frio','dolor al frío','dolor al calor','prueba termica','prueba térmica','prueba electrica','prueba eléctrica','percusion','percusión','palpacion','palpación','conducto','conductos radiculares','tratamiento de conducto','instrumentacion','instrumentación','irrigacion','irrigación','obturacion','obturación','apex','ápice','apical','periapical','periodontitis apical','lesion periapical','lesión periapical','absceso periapical','fistula','fístula','fractura radicular','reabsorcion radicular','reabsorción radicular','hidroxido de calcio','hipoclorito','gutapercha'],
        'definition':'La endodoncia es el área que estudia, diagnostica y trata las alteraciones de la pulpa dental y de los tejidos periapicales.',
        'base':'Para orientar un diagnóstico pulpar se revisa historia del dolor, respuesta a pruebas térmicas, percusión, palpación, radiografía y condición periodontal.'
    },
    'protesis_dental': {
        'label':'Prótesis dental',
        'keys':['protesis dental','prótesis dental','protesis','prótesis','protesis fija','prótesis fija','protesis removible','prótesis removible','protesis total','prótesis total','protesis parcial removible','prótesis parcial removible','ppr','ppf','corona','coronas','puente','puente fijo','carilla','incrustacion','incrustación','onlay','inlay','edentulo','edéntulo','edéntulismo','dentadura','base protetica','base protética','retenedor','conector mayor','conector menor','apoyo oclusal','gancho','kennedy','applegate','oclusion','oclusión','dimension vertical','dimensión vertical','relacion centrica','relación céntrica','impresion definitiva','impresión definitiva','cubeta individual','modelo maestro','articulador','rehabilitacion oral','rehabilitación oral'],
        'definition':'La prótesis dental busca reemplazar dientes perdidos o restaurar estructuras dentarias afectadas para recuperar función, estética, fonética y estabilidad oclusal.',
        'base':'Puede ser fija, removible, parcial o total. La elección depende de pilares, soporte, extensión del espacio edéntulo, estado periodontal, estética y biomecánica.'
    },
    'periodoncia': {
        'label':'Periodoncia clínica',
        'keys':['periodoncia','periodontal','periodonto','encia','encía','gingiva','gingival','gingivitis','periodontitis','bolsa periodontal','sondaje periodontal','profundidad de sondaje','nivel de insercion','nivel de inserción','perdida de insercion','pérdida de inserción','sangrado gingival','sangrado al sondaje','placa bacteriana','biofilm','calculo dental','cálculo dental','sarro','raspado y alisado radicular','detartraje','curetaje','recesion','recesión','furca','movilidad dental','perdida osea','pérdida ósea','hueso alveolar','ligamento periodontal','cemento radicular','periodontograma','absceso periodontal','periimplantitis','mucositis periimplantaria'],
        'definition':'La periodoncia estudia los tejidos de soporte del diente: encía, ligamento periodontal, cemento radicular y hueso alveolar.',
        'base':'Diferencia gingivitis, donde no hay pérdida de inserción, de periodontitis, donde existe destrucción de soporte periodontal.'
    },
    'biomateriales': {
        'label':'Biomateriales y materiales dentales',
        'keys':['biomateriales','materiales dentales','resina','resina compuesta','composite','adhesivo dental','grabado acido','grabado ácido','fotopolimerizacion','fotopolimerización','ionomero','ionómero','ionomero de vidrio','ionómero de vidrio','alginato','silicona','poliéter','yeso','yeso tipo iii','yeso tipo iv','amalgama','mercurio','cemento','cemento dental','fosfato de zinc','oxido de zinc eugenol','óxido de zinc eugenol','eugenol','zirconia','ceramica','cerámica','disilicato','metal porcelana','biocompatibilidad','fraguado','tiempo de trabajo','tiempo de fraguado','expansion termica','expansión térmica','contraccion','contracción','estabilidad dimensional','microfiltracion','microfiltración','polimerizacion','polimerización'],
        'definition':'Los biomateriales dentales son materiales usados para restaurar, registrar, cementar, reemplazar o reproducir estructuras orales.',
        'base':'Se evalúan por biocompatibilidad, resistencia, adhesión, estabilidad dimensional, manipulación, expansión, contracción y comportamiento clínico.'
    },
    'salud_oral': {
        'label':'Salud oral, prevención y normas',
        'keys':['salud oral','salud bucal','prevencion','prevención','promocion','promoción','profilaxis','higiene bucal','higiene oral','cepillado','hilo dental','placa bacteriana','bioseguridad','barrera de proteccion','barrera de protección','esterilizacion','esterilización','desinfeccion','desinfección','asepsia','antisepsia','fluor','flúor','fluoruro','sellantes','selladores','barniz de fluor','barniz de flúor','caries temprana','riesgo cariogenico','riesgo cariogénico','dieta cariogenica','dieta cariogénica','educacion al paciente','educación al paciente','normas','protocolo clinico','protocolo clínico','control de infecciones'],
        'definition':'La salud oral comprende la prevención, diagnóstico, tratamiento y educación para mantener la boca, dientes, encías y tejidos orales en condiciones funcionales y saludables.',
        'base':'Incluye promoción, prevención primaria, secundaria y terciaria, bioseguridad, educación al paciente y atención odontológica integral.'
    },
    'odontologia_general': {
        'label':'Odontología general',
        'keys':['odontologia','odontología','odontologico','odontológico','dental','dentales','diente','dientes','pieza dental','piezas dentales','boca','cavidad oral','cavidad bucal','labio','labios','lengua','paladar','mejilla','carrillo','mucosa','encia','encía','maxilar','mandibula','mandíbula','ATM','articulacion temporomandibular','articulación temporomandibular','oclusion','oclusión','mordida','denticion','dentición','denticion temporal','dentición temporal','denticion permanente','dentición permanente','incisivo','canino','premolar','molar','tercer molar','muela del juicio','caries','lesion cariosa','lesión cariosa','abrasion','abrasión','erosion','erosión','atricion','atrición','fractura dental','trauma dental','absceso','celulitis','infeccion odontogena','infección odontógena','radiografia dental','radiografía dental','periapical','panoramica','panorámica','tomografia','tomografía','tejido blando','tejidos blandos','tejido duro','tejidos duros','enfermedad bucal','enfermedades bucales','enfermedades de tejido','enfermedades bacterianas','bacterianas','lesiones orales','lesion oral','lesión oral'],
        'definition':'La odontología general aborda el cuidado integral de la boca, dientes, encías, tejidos orales y estructuras relacionadas.',
        'base':'Incluye conceptos básicos, prevención, diagnóstico inicial, orientación clínica y derivación cuando el caso requiere atención especializada.'
    }
}

DENTAL_HINTS = sorted(set(
    kw for topic in TOPICS.values() for kw in topic['keys']
) | {
    'odontologo','odontóloga','odontologo','estomatologia','estomatología','operatoria dental','cirugia oral','cirugía oral','exodoncia','extraccion dental','extracción dental','implante','implantes','implantologia','implantología','ortodoncia','brackets','alineadores','maloclusion','maloclusión','bruxismo','xerostomia','xerostomía','halitosis','afta','aftas','ulcera oral','úlcera oral','candidiasis oral','leucoplasia','liquen plano','herpes oral','queilitis','granuloma','quiste odontogeno','quiste odontógeno','tumor odontogeno','tumor odontógeno','patologia oral','patología oral','odontopediatria','odontopediatría','sellante','pediatrico','pediátrico','farmacologia dental','farmacología dental','anestesia local','lidocaina','lidocaína','vasoconstrictor','epinefrina','antibiotico','antibiótico','analgesico','analgésico','antiinflamatorio','radiologia oral','radiología oral','cefalometria','cefalometría'
})
OUT_DOMAIN = ['matematica','matemática','integral','fisica','física','programacion','programación','java','python','javascript','politica','política','futbol','fútbol','finanzas','contabilidad','historia universal','receta','cocina','criptomonedas','bitcoin','videojuego','videojuegos']

TYPO = {'qeu':'que','qe':'que','pregutna':'pregunta','hisotria':'historia','clincia':'clinica','endodncia':'endodoncia','proteis':'protesis','protesi':'protesis','cuandos':'cuantos','q':'que','odontolgia':'odontologia','odotologia':'odontologia','diganostico':'diagnostico','peridontitis':'periodontitis','gingivits':'gingivitis'}

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def strip_accents(s):
    return ''.join(ch for ch in unicodedata.normalize('NFD', s or '') if unicodedata.category(ch) != 'Mn')

def norm(s):
    s = strip_accents(s).lower()
    s = re.sub(r'[^a-z0-9ñ\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return ' '.join(TYPO.get(w,w) for w in s.split())

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,correo TEXT UNIQUE,password_hash TEXT,role TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS threads(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,title TEXT,created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id INTEGER,user_id INTEGER,user_message TEXT,bot_response TEXT,stress_level TEXT,stress_score INTEGER,topic_key TEXT,topic_label TEXT,reframe INTEGER DEFAULT 0,out_domain INTEGER DEFAULT 0,model_used TEXT DEFAULT 'interno',created_at TEXT);
        CREATE TABLE IF NOT EXISTS breathing(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,thread_id INTEGER,stress_level TEXT,completed INTEGER,created_at TEXT);
        CREATE TABLE IF NOT EXISTS recovery(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,thread_id INTEGER,status TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT,filename TEXT,path TEXT UNIQUE,sha256 TEXT UNIQUE,total_pages INTEGER DEFAULT 0,status TEXT DEFAULT 'pendiente',created_at TEXT);
        CREATE TABLE IF NOT EXISTS doc_chunks(id INTEGER PRIMARY KEY AUTOINCREMENT,doc_id INTEGER,filename TEXT,page INTEGER,chunk_index INTEGER,text TEXT,norm_text TEXT,created_at TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(text, filename, content='doc_chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
        CREATE TRIGGER IF NOT EXISTS doc_chunks_ai AFTER INSERT ON doc_chunks BEGIN
          INSERT INTO doc_chunks_fts(rowid,text,filename) VALUES (new.id,new.text,new.filename);
        END;
        CREATE TRIGGER IF NOT EXISTS doc_chunks_ad AFTER DELETE ON doc_chunks BEGIN
          INSERT INTO doc_chunks_fts(doc_chunks_fts,rowid,text,filename) VALUES('delete',old.id,old.text,old.filename);
        END;
        CREATE TRIGGER IF NOT EXISTS doc_chunks_au AFTER UPDATE ON doc_chunks BEGIN
          INSERT INTO doc_chunks_fts(doc_chunks_fts,rowid,text,filename) VALUES('delete',old.id,old.text,old.filename);
          INSERT INTO doc_chunks_fts(rowid,text,filename) VALUES (new.id,new.text,new.filename);
        END;
        ''')
        cols=[r[1] for r in c.execute('PRAGMA table_info(messages)').fetchall()]
        if 'model_used' not in cols:
            c.execute("ALTER TABLE messages ADD COLUMN model_used TEXT DEFAULT 'interno'")
        if not c.execute('SELECT id FROM users WHERE correo=?',(ADMIN_EMAIL,)).fetchone():
            c.execute('INSERT INTO users(nombre,correo,password_hash,role,created_at) VALUES(?,?,?,?,?)',('Administrador',ADMIN_EMAIL,generate_password_hash(ADMIN_PASSWORD),'admin',now()))
        if not c.execute('SELECT id FROM users WHERE correo=?',('demo@odontocare.edu.bo',)).fetchone():
            c.execute('INSERT INTO users(nombre,correo,password_hash,role,created_at) VALUES(?,?,?,?,?)',('Estudiante Demo','demo@odontocare.edu.bo',generate_password_hash('demo123'),'estudiante',now()))
        c.commit()
    seed_demo()

def seed_demo():
    with conn() as c:
        if c.execute('SELECT COUNT(*) n FROM messages').fetchone()['n'] >= 80:
            return
        students = [('Ana Vargas','ana@demo.edu'),('Diego Rojas','diego@demo.edu'),('Camila Flores','camila@demo.edu'),('Marco Salazar','marco@demo.edu'),('Lucía Pérez','lucia@demo.edu'),('Sofía Terán','sofia@demo.edu')]
        user_ids=[]
        for n,e in students:
            row=c.execute('SELECT id FROM users WHERE correo=?',(e,)).fetchone()
            if not row:
                cur=c.execute('INSERT INTO users(nombre,correo,password_hash,role,created_at) VALUES(?,?,?,?,?)',(n,e,generate_password_hash('demo123'),'estudiante',now()))
                user_ids.append(cur.lastrowid)
            else: user_ids.append(row['id'])
        levels = ['Sin alerta']*30 + ['Nivel 1']*20 + ['Nivel 2']*40 + ['Nivel 3']*10
        topics = list(TOPICS.keys())
        today = datetime(2026,5,13,14,0,0)
        random.seed(21)
        for i in range(110):
            uid=random.choice(user_ids)
            dt=today - timedelta(days=random.randint(0,27), hours=random.randint(0,8), minutes=random.randint(0,59))
            topic=random.choice(topics)
            level=random.choice(levels)
            score={'Sin alerta':0,'Nivel 1':30,'Nivel 2':65,'Nivel 3':95}[level]
            title=f"Consulta {TOPICS[topic]['label'][:22]}"
            cur=c.execute('INSERT INTO threads(user_id,title,created_at,updated_at) VALUES(?,?,?,?)',(uid,title,dt.strftime('%Y-%m-%d %H:%M:%S'),dt.strftime('%Y-%m-%d %H:%M:%S')))
            msg=random.choice(['Necesito repasar este tema','Estoy nervioso con este caso','No sé cómo responder esta pregunta','Quiero estudiar para clínica','Tengo dudas sobre el diagnóstico'])
            resp=f"Respuesta académica demo sobre {TOPICS[topic]['label']}"
            c.execute('INSERT INTO messages(thread_id,user_id,user_message,bot_response,stress_level,stress_score,topic_key,topic_label,reframe,out_domain,model_used,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cur.lastrowid,uid,msg,resp,level,score,topic,TOPICS[topic]['label'],1 if random.random()<.28 else 0,1 if random.random()<.04 else 0,'demo',dt.strftime('%Y-%m-%d %H:%M:%S')))
            if level in ['Nivel 2','Nivel 3'] and random.random()<.38:
                c.execute('INSERT INTO breathing(user_id,thread_id,stress_level,completed,created_at) VALUES(?,?,?,?,?)',(uid,cur.lastrowid,level,1,dt.strftime('%Y-%m-%d %H:%M:%S')))
            if level == 'Nivel 3' and random.random()<.72:
                c.execute('INSERT INTO recovery(user_id,thread_id,status,created_at) VALUES(?,?,?,?)',(uid,cur.lastrowid,'recuperado',dt.strftime('%Y-%m-%d %H:%M:%S')))
        c.commit()

def login_required(fn):
    def wrap(*a,**kw):
        if 'user_id' not in session: return jsonify(ok=False,message='No autenticado'),401
        return fn(*a,**kw)
    wrap.__name__=fn.__name__; return wrap

def admin_required(fn):
    def wrap(*a,**kw):
        if session.get('user',{}).get('role')!='admin': return jsonify(ok=False,message='Solo administrador'),403
        return fn(*a,**kw)
    wrap.__name__=fn.__name__; return wrap

def detect_topic(message):
    t=norm(message)
    if any(x in t for x in OUT_DOMAIN):
        if not any(k in t for d in TOPICS.values() for k in [norm(x) for x in d['keys']]):
            return None, True
    scores=[]
    for key,d in TOPICS.items():
        score=0
        for kw in d['keys']:
            nkw=norm(kw)
            if nkw and nkw in t: score+=5+len(nkw.split())
        if score: scores.append((score,key))
    if not scores:
        # Si suena a odontología, aunque esté mal escrito o sea una pregunta general, no lo mandamos al fallback vacío.
        if any(norm(w) in t for w in DENTAL_HINTS):
            return 'odontologia_general', False
        return None, False
    return sorted(scores,reverse=True)[0][1],False

STRESS_PATTERNS = {
    'nivel3': [
        'me falta el aire','no puedo respirar','me cuesta respirar','me voy a desmayar','siento que me desmayo',
        'voy a colapsar','siento que voy a colapsar','no puedo continuar','no aguanto mas','no aguanto más',
        'me siento muy mal','me siento fatal','estoy desesperado','estoy desesperada','estoy en crisis',
        'siento que no puedo mas','siento que no puedo más','no puedo mas con esto','no puedo más con esto',
        'estoy temblando','tengo panico','tengo pánico','ataque de panico','ataque de pánico',
        'me bloqueo por completo','no puedo pensar','se me nubla la mente'
    ],
    'riesgo': [
        'no quiero vivir','quiero desaparecer','hacerme daño','hacerme dano','lastimarme','suicidio','suicidarme'
    ],
    'nivel2': [
        'estoy estresado','estoy estresada','estoy ansioso','estoy ansiosa','me estoy bloqueando',
        'no se que hacer','no sé qué hacer','no puedo avanzar','tengo miedo','me da miedo','me preocupa',
        'estoy preocupado','estoy preocupada','me frustra','estoy frustrado','estoy frustrada','no me sale',
        'me van a bajar','bajar puntos','paciente no llega','me siento mal','estoy nervioso','estoy nerviosa',
        'me confundo','estoy confundido','estoy confundida','me siento presionado','me siento presionada',
        'tengo que entregar','no entiendo nada','estoy bloqueado','estoy bloqueada'
    ],
    'nivel1': [
        'puedo intentar','paso a paso','quiero resolver','con calma','estoy nervioso pero','estoy nerviosa pero',
        'puedo revisar','estoy aprendiendo','todavia','todavía','tengo una duda','necesito ayuda',
        'quiero entender','me gustaria saber','me gustaría saber'
    ]
}

def detect_stress(message):
    """Motor interno de detección emocional.
    No depende de Ollama/DeepSeek: solo evalúa palabras, frases y combinaciones de intensidad.
    """
    t=norm(message)
    hits3=[x for x in STRESS_PATTERNS['nivel3'] if norm(x) in t]
    risk=[x for x in STRESS_PATTERNS['riesgo'] if norm(x) in t]
    hits2=[x for x in STRESS_PATTERNS['nivel2'] if norm(x) in t]
    hits1=[x for x in STRESS_PATTERNS['nivel1'] if norm(x) in t]

    # Combinaciones que suben el nivel: malestar + incapacidad + urgencia académica.
    escalators = 0
    if any(x in t for x in ['muy','demasiado','horrible','fatal','desesperado','desesperada']): escalators += 1
    if any(x in t for x in ['no puedo','no se','no sé','no entiendo','me bloqueo','no logro']): escalators += 1
    if any(x in t for x in ['entregar','examen','docente','paciente','historia clinica','historia clínica','caso clinico','caso clínico']): escalators += 1
    if 'me siento mal' in t and escalators >= 2:
        hits3.append('me siento mal + bloqueo académico')

    if risk:
        return {'level':'Nivel 3','label':'Nivel 3 - Alerta crítica','score':100,'color':'danger','requires_breathing':True,'optional_breathing':False,'tags':['riesgo emocional', *risk[:3]]}
    if hits3:
        return {'level':'Nivel 3','label':'Nivel 3 - Alerta crítica','score':92,'color':'danger','requires_breathing':True,'optional_breathing':False,'tags':['crisis emocional', *hits3[:3]]}
    if hits2 or escalators >= 2:
        tags = hits2[:3] if hits2 else ['presión académica']
        return {'level':'Nivel 2','label':'Nivel 2 - Alerta emocional','score':68,'color':'warning','requires_breathing':False,'optional_breathing':True,'tags':tags}
    if hits1:
        return {'level':'Nivel 1','label':'Nivel 1 - Estado de recursos','score':32,'color':'success','requires_breathing':False,'optional_breathing':False,'tags':['reencuadre activo', *hits1[:2]]}
    return {'level':'Sin alerta','label':'Sin alerta emocional','score':0,'color':'neutral','requires_breathing':False,'optional_breathing':False,'tags':[]}

STOPWORDS = set("""a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos el ella ellas ellos en entre era es esa esas ese esos esta estas este esto estos fue ha hay la las le lo los mas más me mi mis muy no nos o para pero por que qué se si sí sin sobre son su sus te tu tus un una unas unos ya cual cuales cuál cuáles quien quién quienes quiénes""".split())

def short_clean(text, limit=1200):
    text = re.sub(r'\s+', ' ', text or '').strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0]
    return cut + '…'

def query_terms(q):
    return [w for w in norm(q).split() if len(w) > 2 and w not in STOPWORDS]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def extract_text_by_page(path):
    path = Path(path)
    pages = []
    if path.suffix.lower() == '.txt':
        txt = path.read_text(errors='ignore')
        return [(1, txt)]
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages, start=1):
            try:
                txt = page.extract_text() or ''
            except Exception:
                txt = ''
            if txt.strip():
                pages.append((i, txt))
    except Exception as e:
        print('[PDF EXTRACTION ERROR]', path.name, e)
    return pages

def make_chunks(text, size=1050, overlap=170):
    text = re.sub(r'\s+', ' ', text or '').strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunk = text[start:end].strip()
        if len(chunk) > 80:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks

def index_document(file_path, display_name=None):
    file_path = Path(file_path)
    if not file_path.exists() or file_path.suffix.lower() not in ALLOWED_DOC_EXT:
        return {'ok': False, 'message': 'Archivo no permitido'}
    file_hash = sha256_file(file_path)
    display_name = display_name or file_path.name
    pages = extract_text_by_page(file_path)
    if not pages:
        return {'ok': False, 'message': 'No se pudo extraer texto del archivo. Si es escaneado como imagen, se necesitaría OCR.'}
    with conn() as c:
        existing = c.execute('SELECT id FROM documents WHERE sha256=?', (file_hash,)).fetchone()
        if existing:
            chunks = c.execute('SELECT COUNT(*) n FROM doc_chunks WHERE doc_id=?', (existing['id'],)).fetchone()['n']
            return {'ok': True, 'message': 'El documento ya estaba indexado.', 'chunks': chunks}
        cur = c.execute('INSERT INTO documents(filename,path,sha256,total_pages,status,created_at) VALUES(?,?,?,?,?,?)',
                        (display_name, str(file_path), file_hash, len(pages), 'indexado', now()))
        doc_id = cur.lastrowid
        total_chunks = 0
        for page_num, page_text in pages:
            for idx, chunk in enumerate(make_chunks(page_text)):
                c.execute('INSERT INTO doc_chunks(doc_id,filename,page,chunk_index,text,norm_text,created_at) VALUES(?,?,?,?,?,?,?)',
                          (doc_id, display_name, page_num, idx, chunk, norm(chunk), now()))
                total_chunks += 1
        c.commit()
    return {'ok': True, 'message': 'Documento indexado correctamente.', 'chunks': total_chunks}

def auto_index_knowledge_base():
    for path in sorted(KNOWLEDGE_DIR.glob('*')):
        if path.suffix.lower() in ALLOWED_DOC_EXT:
            index_document(path, path.name)

def expand_query_terms(message, topic_key):
    terms = query_terms(message)
    if topic_key and topic_key in TOPICS:
        for kw in TOPICS[topic_key]['keys'][:18]:
            terms.extend(query_terms(kw))
    synonyms = {
        'endodoncia': ['pulpa','pulpar','pulpitis','conducto','periapical','dolor'],
        'historia': ['anamnesis','antecedentes','examen','diagnostico','tratamiento'],
        'clinica': ['historia','anamnesis','examen','diagnostico'],
        'caries': ['lesion','esmalte','dentina','cavitacion'],
        'periodontitis': ['periodontal','encia','sondaje','insercion','gingival'],
        'protesis': ['corona','puente','carilla','removible','rehabilitacion'],
        'materiales': ['biomateriales','resina','yeso','cemento','ceramica'],
        'resina': ['compuesta','adhesivo','fotopolimerizacion','restauracion'],
    }
    base = set(terms)
    for t in list(base):
        terms.extend(synonyms.get(t, []))
    seen=[]
    for t in terms:
        if t not in STOPWORDS and len(t)>2 and t not in seen:
            seen.append(t)
    return seen[:24]

def search_documents(message, topic_key=None, limit=5):
    terms = expand_query_terms(message, topic_key)
    if not terms:
        return []
    fts_query = ' OR '.join(terms[:16])
    hits = []
    with conn() as c:
        try:
            sql = ("SELECT dc.id, dc.filename, dc.page, dc.text, bm25(doc_chunks_fts) AS rank "
                   "FROM doc_chunks_fts JOIN doc_chunks dc ON dc.id = doc_chunks_fts.rowid "
                   "WHERE doc_chunks_fts MATCH ? ORDER BY rank LIMIT 35")
            rows = c.execute(sql, (fts_query,)).fetchall()
        except Exception:
            like = '%' + '%'.join(terms[:3]) + '%'
            rows = c.execute('SELECT id, filename, page, text, 0 AS rank FROM doc_chunks WHERE norm_text LIKE ? LIMIT 35', (like,)).fetchall()
    qset = set(terms)
    for r in rows:
        txt_norm = norm(r['text'])
        words = set(txt_norm.split())
        overlap = len(qset & words)
        phrase_bonus = sum(1 for t in terms[:8] if t in txt_norm)
        score = overlap*3 + phrase_bonus - float(r['rank'] or 0)
        hits.append({'filename': r['filename'], 'page': r['page'], 'text': r['text'], 'score': score})
    hits.sort(key=lambda x: x['score'], reverse=True)
    out=[]; seen=set()
    for h in hits:
        key=(h['filename'], h['page'])
        if key not in seen:
            out.append(h); seen.add(key)
        if len(out)>=limit: break
    return out

def best_sentences(text, terms, max_sentences=3):
    parts = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', text or '').strip())
    scored=[]
    for snt in parts:
        ns = norm(snt)
        score = sum(1 for t in terms if t in ns)
        if score:
            scored.append((score, snt))
    scored.sort(reverse=True, key=lambda x:x[0])
    selected = [s for _,s in scored[:max_sentences]] or parts[:max_sentences]
    return ' '.join(selected)

def answer_from_documents(message, topic_key, stress):
    hits = search_documents(message, topic_key, limit=4)
    if not hits:
        return None, 'interno'
    terms = expand_query_terms(message, topic_key)
    pref = ''
    if stress['level']=='Nivel 1': pref='Detecto algo de tensión, pero podemos resolverlo por partes.\n\n'
    elif stress['level']=='Nivel 2': pref='Entiendo la presión. Primero ordeno la información encontrada en la biblioteca local.\n\n'
    elif stress['level']=='Nivel 3': pref='Alerta emocional de nivel 3 detectada. Primero completa el anclaje respiratorio. Mientras respiras, dejo preparada la información recuperada de la biblioteca local.\n\n'
    body = pref
    body += 'Respuesta basada únicamente en la biblioteca cargada:\n'
    for i,h in enumerate(hits[:3], start=1):
        excerpt = short_clean(best_sentences(h['text'], terms, 2), 520)
        body += f'\n{i}. {excerpt}\n   Fuente: {h["filename"]}, pág. {h["page"]}.'
    body += '\n\nNota de alcance: este modo no usa Ollama ni DeepSeek. No genera análisis clínico profundo por fuera de los libros/PDF cargados; solo recupera y organiza la información encontrada. Para diagnóstico real, debe validar un docente u odontólogo.'
    return body, 'biblioteca local'

def answer(message, topic_key, out_domain, stress):
    if out_domain:
        return 'Este sistema está limitado al área de odontología y apoyo emocional académico. Puedo ayudarte con historia clínica, periodoncia, prótesis, biomateriales, endodoncia, salud oral u odontología general.'
    t=norm(message)
    pref=''
    if stress['level']=='Nivel 1': pref='Detecto que hay nervios, pero también intención de resolver. Trabajemos por partes.\n\n'
    elif stress['level']=='Nivel 2': pref='Entiendo la presión. Primero ordenemos lo inmediato y luego resolvemos el tema clínico.\n\n'
    elif stress['level']=='Nivel 3': pref='Alerta emocional de nivel 3. Primero realiza el anclaje respiratorio. Mientras tanto, dejo ordenada la parte odontológica para que puedas continuar sin presión.\n\n'
    if stress['level']=='Nivel 3' and not topic_key:
        return 'Alerta emocional de nivel 3. Primero realiza el anclaje respiratorio y busca apoyo cercano si el malestar continúa. Luego escribe una pregunta odontológica concreta y la resolvemos por pasos.'
    if stress['level']=='Nivel 2' and not topic_key:
        if 'paciente' in t and ('no llega' in t or 'no llego' in t):
            return pref+'Acción práctica: espera unos minutos según la norma de tu clínica, intenta contactar al paciente, registra hora e intento de contacto, informa al docente y pregunta si corresponde reprogramación o alternativa académica.'
        return pref+'Dime qué tema odontológico necesitas resolver: historia clínica, diagnóstico, endodoncia, periodoncia, prótesis o materiales dentales.'
    if not topic_key:
        return pref+'Puedo responder dudas de odontología. Por ejemplo: qué es historia clínica, qué es endodoncia, qué es prótesis dental, diferencia entre gingivitis y periodontitis, o diagnóstico pulpar.'
    topic=TOPICS[topic_key]
    if ('enfermedad' in t or 'enfermedades' in t) and ('tejido' in t or 'tejidos' in t):
        if 'blando' in t or 'blandos' in t:
            body='Las enfermedades de tejidos blandos en odontología afectan estructuras como encía, mucosa, lengua, labios y tejidos periorales. Pueden incluir gingivitis, lesiones ulcerativas, abscesos, infecciones odontógenas, celulitis y alteraciones de la mucosa. Para orientarlas se revisa localización, dolor, color, aumento de volumen, sangrado, fiebre, evolución y factores sistémicos.'
        elif 'duro' in t or 'duros' in t:
            body='Las enfermedades de tejidos duros afectan principalmente esmalte, dentina, cemento, hueso alveolar o estructuras dentarias de soporte. Ejemplos frecuentes son caries, alteraciones periapicales, lesiones asociadas a trauma, pérdida ósea periodontal y complicaciones de origen pulpar. Se evalúan con examen clínico, radiografía y pruebas diagnósticas.'
        else:
            body='En odontología, las enfermedades pueden afectar tejidos duros, como esmalte, dentina, cemento y hueso, o tejidos blandos, como encía, mucosa, lengua y tejidos periorales. Para responder mejor conviene especificar si quieres revisar tejidos blandos, tejidos duros, infecciones bacterianas, lesiones periodontales o lesiones pulpares.'
    elif 'que es historia clinica' in t or (topic_key=='historia_clinica' and 'que es' in t):
        body='La historia clínica odontológica es el documento donde se registra de forma ordenada la información del paciente, el motivo de consulta, la enfermedad actual, antecedentes, examen clínico, diagnóstico y plan de tratamiento. Sirve para razonar el caso, dar seguimiento y respaldar la atención.'
    elif 'que es endodoncia' in t or (topic_key=='endodoncia' and 'que es' in t):
        body='La endodoncia es la especialidad odontológica que estudia y trata la pulpa dental y los tejidos periapicales. Se relaciona con diagnósticos como pulpitis, necrosis pulpar, periodontitis apical y abscesos de origen pulpar.'
    elif 'que es protesis' in t or 'protesis dental' in t or (topic_key=='protesis_dental' and 'que es' in t):
        body='La prótesis dental es el recurso clínico que reemplaza dientes ausentes o restaura estructuras dentarias para recuperar función, estética, fonación y estabilidad. Puede ser fija, parcial removible o total, según el caso.'
    elif 'cuantos dientes' in t or ('dientes' in t and 'humano' in t):
        body='Un adulto normalmente tiene 32 dientes permanentes si se incluyen las muelas del juicio: 8 incisivos, 4 caninos, 8 premolares y 12 molares. En niños, la dentición temporal tiene 20 dientes.'
    elif 'caries' in t:
        body='La caries es una enfermedad multifactorial de los tejidos duros dentarios. Se relaciona con biofilm, dieta rica en azúcares fermentables, tiempo y susceptibilidad del huésped. Puede iniciar como mancha blanca y progresar a cavitación o compromiso pulpar si no se controla.'
    elif 'gingivitis' in t or 'periodontitis' in t:
        body='La gingivitis es inflamación de la encía sin pérdida de inserción clínica. La periodontitis implica destrucción del soporte periodontal, con pérdida de inserción y posible pérdida ósea. Para diferenciarlas se evalúa sondaje, sangrado, movilidad, radiografía y factores de riesgo.'
    elif 'pulpitis' in t or 'dolor nocturno' in t or 'dolor espontaneo' in t:
        body='Dolor espontáneo, prolongado y nocturno orienta a pulpitis irreversible sintomática, pero debe confirmarse con pruebas térmicas, percusión, palpación, radiografía y evaluación clínica. Una molestia breve al frío o dulce puede orientar más a sensibilidad o pulpitis reversible.'
    elif 'yeso' in t:
        body='Si aumentas la relación agua/polvo en yeso tipo III, la mezcla queda más fluida, pero disminuye la resistencia del modelo, aumenta la porosidad y puede alterar precisión dimensional, dureza y expansión de fraguado.'
    elif 'ionomero' in t:
        body='El ionómero de vidrio convencional se usa cuando se busca adhesión química y liberación de flúor, por ejemplo en lesiones cervicales, restauraciones atraumáticas o bases. No es ideal para cavidades grandes sometidas a alta carga por su menor resistencia mecánica.'
    else:
        body=f'{topic["definition"]} {topic["base"]}'
    return pref + body

def ollama_answer(message, topic_key, out_domain, stress):
    if not USE_OLLAMA:
        return None, 'interno'
    if out_domain or not topic_key:
        return None, 'interno'
    topic = TOPICS.get(topic_key)
    if not topic:
        return None, 'interno'
    prompt = f"""
Responde SIEMPRE en español latino neutro. No uses inglés bajo ninguna circunstancia. No muestres razonamiento interno.
Eres OdontoCare Respire, un tutor académico especializado exclusivamente en odontología para estudiantes universitarios.

Área permitida del sistema:
- Historia clínica odontológica
- Periodoncia clínica
- Prótesis removible
- Prótesis fija
- Prótesis total
- Biomateriales y materiales dentales
- Endodoncia y diagnóstico pulpar
- Salud oral, prevención y normas
- Odontología general
- Operatoria dental, cirugía oral básica, radiología oral, oclusión, ortodoncia básica, patología oral, odontopediatría y farmacología dental básica cuando la consulta sea académica

Reglas obligatorias:
1. Responde solo si la pregunta pertenece al área odontológica o al apoyo emocional académico.
2. Si la pregunta no es odontológica, recházala brevemente.
3. No inventes fuentes, autores ni bibliografía.
4. No digas que consultaste libros o PDFs.
5. Responde con claridad para un estudiante.
6. Si la pregunta es simple, responde directo y breve.
7. Si es caso clínico, estructura en: respuesta directa, fundamento clínico, aplicación al caso y siguiente paso.
8. No muestres razonamiento interno ni frases como Thinking.

Tema detectado: {topic['label']}
Contexto permitido: {topic['definition']} {topic['base']}
Estado emocional detectado por motor interno: {stress['label']}
Si el estado es Nivel 3, no hagas terapia ni diagnostiques salud mental. Da una respuesta odontológica clara, breve y estructurada, con tono calmado.

Pregunta del estudiante:
{message}
""".strip()
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.25, 'num_predict': 700},
            },
            timeout=120,
        )
        r.raise_for_status()
        txt = (r.json().get('response') or '').strip()
        txt = re.sub(r'<think>.*?</think>', '', txt, flags=re.S | re.I).strip()
        txt = re.sub(r'(?is)^thinking\.\.\..*?\.\.\.done thinking\.', '', txt).strip()
        if not txt:
            return None, 'interno'
        return txt, OLLAMA_MODEL
    except Exception as e:
        print('[OLLAMA ERROR]', e)
        return None, 'interno'


def build_answer(message, topic_key, out_domain, stress):
    # Versión documental: el nivel emocional se calcula por reglas internas.
    # La respuesta odontológica se intenta resolver primero desde los libros/PDF indexados.
    # No depende de Ollama ni DeepSeek para poder desplegarse en hosting gratuito.
    if not out_domain and topic_key:
        doc_text, model_used = answer_from_documents(message, topic_key, stress)
        if doc_text:
            return doc_text, model_used
    return answer(message, topic_key, out_domain, stress), 'interno'

@app.route('/')
def index(): return render_template('app.html',user=session.get('user'),topics=TOPICS,devs=DEVS,use_ollama=USE_OLLAMA,ollama_model=OLLAMA_MODEL)

@app.route('/api/login',methods=['POST'])
def api_login():
    d=request.get_json() or {}; email=d.get('correo','').lower().strip(); pw=d.get('password','')
    with conn() as c:
        u=c.execute('SELECT * FROM users WHERE correo=?',(email,)).fetchone()
        if not u or not check_password_hash(u['password_hash'],pw): return jsonify(ok=False,message='Credenciales incorrectas'),401
        session['user_id']=u['id']; session['user']={'nombre':u['nombre'],'correo':u['correo'],'role':u['role']}
    return jsonify(ok=True)

@app.route('/api/demo-login',methods=['POST'])
def demo_login():
    with conn() as c:
        u=c.execute('SELECT * FROM users WHERE correo=?',('demo@odontocare.edu.bo',)).fetchone()
        session['user_id']=u['id']; session['user']={'nombre':u['nombre'],'correo':u['correo'],'role':u['role']}
    return jsonify(ok=True)

@app.route('/api/register',methods=['POST'])
def register():
    d=request.get_json() or {}; n=d.get('nombre','').strip(); e=d.get('correo','').lower().strip(); p=d.get('password','')
    if not n or not e or not p: return jsonify(ok=False,message='Completa todos los campos'),400
    try:
        with conn() as c:
            cur=c.execute('INSERT INTO users(nombre,correo,password_hash,role,created_at) VALUES(?,?,?,?,?)',(n,e,generate_password_hash(p),'estudiante',now()))
            session['user_id']=cur.lastrowid; session['user']={'nombre':n,'correo':e,'role':'estudiante'}; c.commit()
        return jsonify(ok=True)
    except sqlite3.IntegrityError: return jsonify(ok=False,message='Correo ya registrado'),409

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

@app.route('/api/chat',methods=['POST'])
@login_required
def chat():
    d=request.get_json() or {}; msg=d.get('message','').strip(); thread_id=d.get('thread_id')
    if not msg: return jsonify(ok=False,message='Mensaje vacío'),400
    stress=detect_stress(msg); topic_key,out_domain=detect_topic(msg); resp,model_used=build_answer(msg,topic_key,out_domain,stress)
    uid=session['user_id']; ts=now()
    with conn() as c:
        if thread_id:
            row=c.execute('SELECT id FROM threads WHERE id=? AND user_id=?',(thread_id,uid)).fetchone()
        else: row=None
        if not row:
            cur=c.execute('INSERT INTO threads(user_id,title,created_at,updated_at) VALUES(?,?,?,?)',(uid,msg[:45] or 'Nuevo chat',ts,ts)); thread_id=cur.lastrowid
        else:
            c.execute('UPDATE threads SET updated_at=? WHERE id=?',(ts,thread_id))
        c.execute('INSERT INTO messages(thread_id,user_id,user_message,bot_response,stress_level,stress_score,topic_key,topic_label,reframe,out_domain,model_used,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(thread_id,uid,msg,resp,stress['level'],stress['score'],topic_key,TOPICS.get(topic_key,{}).get('label'),1 if 'reencuadre' in stress.get('tags',[]) else 0,1 if out_domain else 0,model_used,ts))
        c.commit()
    recs = [{'icon':'check','title':'Siguiente paso','text':'Haz una pregunta concreta o dame datos del caso.'}]
    if stress['level']=='Nivel 2': recs=[{'icon':'route','title':'Orden inmediato','text':'Define qué pasó, qué dato falta y quién debe ser informado.'}]
    if stress['level']=='Nivel 3': recs=[{'icon':'alert','title':'Pausa obligatoria','text':'Detén la actividad y busca acompañamiento.'}]
    return jsonify(ok=True,response=resp,thread_id=thread_id,analysis=stress,recommendations=recs,model_used=model_used)

@app.route('/api/threads')
@login_required
def threads():
    with conn() as c:
        rows=c.execute('SELECT id,title,updated_at FROM threads WHERE user_id=? ORDER BY updated_at DESC LIMIT 30',(session['user_id'],)).fetchall()
    return jsonify(ok=True,threads=[dict(r) for r in rows])

@app.route('/api/threads/<int:id>')
@login_required
def thread(id):
    with conn() as c:
        rows=c.execute('SELECT user_message,bot_response,stress_level,created_at,model_used FROM messages WHERE thread_id=? AND user_id=? ORDER BY id',(id,session['user_id'])).fetchall()
    return jsonify(ok=True,messages=[dict(r) for r in rows])

@app.route('/api/breathing-event',methods=['POST'])
@login_required
def breath():
    d=request.get_json() or {}
    with conn() as c:
        c.execute('INSERT INTO breathing(user_id,thread_id,stress_level,completed,created_at) VALUES(?,?,?,?,?)',(session['user_id'],d.get('thread_id'),d.get('stress_level'),1,now())); c.commit()
    return jsonify(ok=True)

@app.route('/api/admin/dashboard')
@login_required
@admin_required
def dashboard():
    days=int(request.args.get('days',30)); student=request.args.get('student_id','all')
    since=(datetime.now()-timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    where='WHERE m.created_at>=?'; params=[since]
    if student!='all': where+=' AND m.user_id=?'; params.append(student)
    with conn() as c:
        total=c.execute(f'SELECT COUNT(*) n FROM messages m {where}',params).fetchone()['n']
        sin=c.execute(f"SELECT COUNT(*) n FROM messages m {where} AND stress_level='Sin alerta'",params).fetchone()['n']
        fuera=c.execute(f'SELECT COUNT(*) n FROM messages m {where} AND out_domain=1',params).fetchone()['n']
        refr=c.execute(f'SELECT COUNT(*) n FROM messages m {where} AND reframe=1',params).fetchone()['n']
        anch=c.execute('SELECT COUNT(*) n FROM breathing').fetchone()['n']
        crit=c.execute(f"SELECT COUNT(*) n FROM messages m {where} AND stress_level='Nivel 3'",params).fetchone()['n']
        rec=c.execute('SELECT COUNT(*) n FROM recovery WHERE status="recuperado"').fetchone()['n']
        levels=[]
        for lvl in ['Sin alerta','Nivel 1','Nivel 2','Nivel 3']:
            levels.append({'label':lvl,'value':c.execute(f'SELECT COUNT(*) n FROM messages m {where} AND stress_level=?',params+[lvl]).fetchone()['n']})
        activity=[]
        for i in range(days-1,-1,-1):
            day=(datetime.now()-timedelta(days=i)).strftime('%Y-%m-%d')
            if student!='all':
                n=c.execute('SELECT COUNT(*) n FROM messages WHERE substr(created_at,1,10)=? AND user_id=?',(day,student)).fetchone()['n']
            else:
                n=c.execute('SELECT COUNT(*) n FROM messages WHERE substr(created_at,1,10)=?',(day,)).fetchone()['n']
            activity.append({'date':day[5:],'value':n})
        topics=[dict(r) for r in c.execute(f'SELECT COALESCE(topic_label,"Sin tema") label, COUNT(*) c FROM messages m {where} GROUP BY topic_label ORDER BY c DESC LIMIT 8',params).fetchall()]
        students=[dict(r) for r in c.execute("SELECT id,nombre FROM users WHERE role='estudiante' ORDER BY nombre").fetchall()]
        recent=[dict(r) for r in c.execute(f'SELECT u.nombre,m.user_message,m.stress_level,m.topic_label,m.model_used,m.created_at FROM messages m JOIN users u ON u.id=m.user_id {where} ORDER BY m.created_at DESC LIMIT 10',params).fetchall()]
    kpis={'mensajes':total,'sesiones_sin_estres':sin,'tasa_recuperacion':round((rec/max(1,crit))*100),'reencuadre_activo':round((refr/max(1,total))*100),'anclajes_respiratorios':anch,'fuera_dominio':fuera}
    return jsonify(ok=True,kpis=kpis,levels=levels,activity=activity,topics=topics,students=students,recent=recent)

@app.route('/api/documents')
@login_required
def documents_list():
    with conn() as c:
        sql = ("SELECT d.id,d.filename,d.total_pages,d.status,d.created_at,COUNT(c.id) chunks "
               "FROM documents d LEFT JOIN doc_chunks c ON c.doc_id=d.id "
               "GROUP BY d.id ORDER BY d.created_at DESC")
        docs=[dict(r) for r in c.execute(sql).fetchall()]
    return jsonify(ok=True,documents=docs)

@app.route('/api/documents/upload', methods=['POST'])
@login_required
def documents_upload():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify(ok=False,message='Selecciona un PDF o TXT.'),400
    name = secure_filename(f.filename) or 'documento.pdf'
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_DOC_EXT:
        return jsonify(ok=False,message='Solo se permiten archivos PDF o TXT.'),400
    if request.content_length and request.content_length > MAX_UPLOAD_MB*1024*1024:
        return jsonify(ok=False,message=f'El archivo supera {MAX_UPLOAD_MB} MB.'),400
    target = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}"
    f.save(target)
    result = index_document(target, f.filename)
    if not result.get('ok'):
        try: target.unlink()
        except Exception: pass
        return jsonify(ok=False,message=result.get('message','No se pudo indexar.')),400
    return jsonify(ok=True,message=result.get('message'),chunks=result.get('chunks',0))

@app.route('/api/documents/reindex', methods=['POST'])
@login_required
def documents_reindex():
    auto_index_knowledge_base()
    return jsonify(ok=True,message='Biblioteca base revisada e indexada.')

@app.route('/api/topics')
def api_topics(): return jsonify(ok=True,topics={k:v['label'] for k,v in TOPICS.items()})

@app.route('/api/model-status')
def model_status():
    return jsonify(ok=True,use_ollama=False,model='biblioteca local',url='sin servicio externo')

# Inicialización compatible con gunicorn/Render y ejecución local.
init_db()
auto_index_knowledge_base()

if __name__ == '__main__':
    print('='*64)
    print('OdontoCare Respire - Biblioteca documental local')
    print('USE_OLLAMA:', False)
    print('MOTOR:', 'biblioteca local + reglas internas')
    print('KNOWLEDGE_DIR:', KNOWLEDGE_DIR)
    print('='*64)
    app.run(debug=True)
