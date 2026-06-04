"""
RO Bot â€” Template Matching + Rotacao inteligente
==================================================
Comandos:
  python ro_bot.py --capturar   -> salva sprites (S=salvar varios, Q=sair)
  python ro_bot.py --verificar  -> mostra deteccao ao vivo
  python ro_bot.py              -> roda o bot

Banco de mobs: pasta templates/  (mob_0.png, mob_1.png, ...)

Instalar:
  pip install opencv-python numpy pygetwindow pyautogui keyboard pywin32
"""

import ctypes
import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
import win32api, win32con, win32gui, win32ui
import time, sys, threading, random, os, glob, json, heapq
from datetime import datetime
from enum import Enum

if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  CONFIGURE AQUI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

JANELA      = "4th | Gepard Shield 3.0 (^-_-^)"
TECLA_PASSO = "f3"
TECLA_LOOT  = "z"
TECLA_TAB   = "tab"
TECLA_REFRESH_MOD = "alt"
TECLA_REFRESH_KEY = "1"

# Rotacao de skills: (tecla, delay_antes_da_proxima)
# Ajuste os delays conforme o cooldown de cada skill
ROTACAO = [
    ("f1", 0.4),   # skill 1 -> aguarda 0.4s
    ("f2", 0.4),   # skill 2 -> aguarda 0.4s
]

MAX_CICLOS_ATAQUE = 5    # maximo de rotacoes por mob antes de desistir
DELAY_PASSO       = 0.18
DELAY_LOOT        = 0.15
EXPLORAR_SETTLE_S = 1.25
EXPLORAR_SETTLE_LONGO_S = 1.65

# Persistencia de alvo: YOLO pode piscar durante movimento/animacao. Nao
# transforme 1 frame sem bbox em SKIP+blacklist.
ALVO_GRACE_S = 1.8
ALVO_RECHECK_S = 0.15
ALVO_REAQUIRE_RAIO = 190
ALVO_APROX_FATOR = 0.28
ALVO_LOCK_S = 4.0  # segundos maximos travando no mesmo alvo sem redeteccao visual

# Switch oportunista: se mob detectado e < ALVO_SWITCH_RATIO vezes a distancia do alvo atual,
# troca de alvo imediatamente. Evita bot perseguir mob longe ignorando um ao lado.
ALVO_SWITCH_RATIO = 0.65   # troca se novo mob < 65% da dist do alvo atual (35% mais perto)
ALVO_SWITCH_MIN_DIST = 60  # px minimos de diferenca para valer a troca (evita micro-trocas)

# Grace period de redeteccao escalavel com distancia:
# grace = ALVO_GRACE_BASE + dist_px/100 * ALVO_GRACE_POR_100PX
# Exemplo: mob a 514px â†’ 1.8 + (514/100 Ã— 0.6) = ~5s de tentativas
ALVO_GRACE_BASE      = 1.8   # segundos base (para mobs perto)
ALVO_GRACE_POR_100PX = 0.60  # segundos extras por 100px de distancia

# â”€â”€ Maquina de estados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HP_RECUPERAR_MIN  = 0.40   # transiciona para RECUPERAR quando HP cai abaixo disto
SP_RECUPERAR_MIN  = 0.18   # transiciona para RECUPERAR quando SP cai abaixo disto

# â”€â”€ YOLO Tracking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
USAR_YOLO_TRACKING = True  # usa model.track() â€” da ID persistente ao mob entre frames

# â”€â”€ Deteccao de HP bar do mob â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HP_BAR_MOB_ATIVO    = True  # detecta barra de HP colorida acima do sprite do mob
HP_BAR_MOB_Y_BUSCA  = 58    # pixels acima do centro do mob para buscar a barra
HP_BAR_MOB_PIX_MIN  = 14    # min pixels coloridos em uma linha para confirmar barra

# â”€â”€ Mapa caminhavel estabilizado (media de frames) â”€â”€â”€â”€â”€â”€â”€â”€â”€
WALK_HIST_N = 3   # frames para media do mapa caminhavel (menor = adapta mais rapido a efeitos de skill)

# â”€â”€ Log visual (screenshots anotados + video MP4) â”€â”€â”€â”€â”€â”€â”€â”€â”€
VISUAL_LOG_ATIVO    = os.environ.get("RO_VISUAL_LOG", "0").lower() in ("1", "true", "yes", "on")
VISUAL_LOG_PASTA    = "visual_log"
VISUAL_LOG_VIDEO    = os.environ.get("RO_VISUAL_LOG_VIDEO", "1").lower() in ("1", "true", "yes", "on")
VISUAL_LOG_FPS      = 4      # FPS do video gerado (4 = 1 frame a cada 250ms)
# Eventos que disparam screenshot (remova os que nao quiser)
VISUAL_LOG_EVENTOS  = {"MOB", "MOVE", "SKILL", "KILL", "PATH", "STUCK", "EXPLORE",
                        "BLIND_ATTACK", "LOOT"}

# â”€â”€ Scan assincrono (thread dedicada de deteccao) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Thread separada roda YOLO a SCAN_IMGSZ continuamente e deposita resultados
# em _scan_result. Main loop consome sem esperar inferencia â€” reacao em ~50ms.
SCAN_ASYNC_ATIVO = os.environ.get("RO_SCAN_ASYNC", "0").lower() in ("1", "true", "yes", "on")
SCAN_IMGSZ       = 320    # resolucao reduzida (~4x mais rapido que 640)
SCAN_CONF        = 0.38   # confianÃ§a um pouco maior para compensar baixa res
SCAN_INTERVALO   = 0.028  # ~35fps de scan (ms por ciclo do worker)

# Sincronia de combate 2.5D: nao dispare skill enquanto ainda esta fora
# de alcance ou no meio da animacao de movimento.
COMBATE_RANGE_PX = 235
COMBATE_APROX_FATOR = 0.72
COMBATE_MOVE_SETTLE_S = 0.65  # tempo para o personagem andar ~65px antes de re-avaliar range
SKILL_CLICAR_ALVO = True
SKILL_CLICK_DELAY_S = 0.06
SKILL_POS_CAST_S = 0.35
YOLO_TARGET_Y_RATIO = 0.74

# Filtro contra "visao de raio-x": ignora mobs vistos atras de parede.
LOS_MOB_ATIVO = True
LOS_MIN_PCT = 0.84
CAMINHO_ALVO_MAX_ALONGAMENTO = 2.8
COMBATE_USAR_WAYPOINT = True
COMBATE_WAYPOINT_CELLS = 10
ROI_DIREITA_MAX = 0.78
EXPLORAR_X_MAX = 0.74
EXPLORAR_HEADING_ATIVO = True
EXPLORAR_HEADING_TEMPO = 24.0
EXPLORAR_HEADING_BONUS = 420

# Watchdog de aproximacao: se a distancia nao cai, o alvo provavelmente e
# inalcanÃ§avel por parede/colisao.
APROX_WATCH_ATIVO = True
APROX_WATCH_TENTATIVAS = 3
APROX_WATCH_MIN_DELTA = 28
APROX_WATCH_RAIO = 160

# Limpeza de cliente Ragnarok: usa Alt+1 configurado como @refresh.
REFRESH_ATIVO = True
REFRESH_COOLDOWN_S = 45
REFRESH_PERIODICO_S = 240
REFRESH_APOS_MISS = True
REFRESH_APOS_STUCK = True

TEMPLATES_DIR  = "templates"
THRESHOLD      = 0.72   # 0.75 perdia mobs reais; 0.65 gerava falsos positivos
TEMPLATE_RAIO  = 32
TEMPLATE_NMS_RAIO = 45  # junta matches repetidos do mesmo mob
TEMPLATE_MIN_PIXELS = 80
TEMPLATE_ESCALAS = (1.00,)

# YOLO: detector moderno treinado com imagens do seu jogo.
USAR_YOLO = True
YOLO_MODEL_PATH = os.environ.get("RO_YOLO_MODEL", os.path.join("models", "mob_yolo.pt"))
YOLO_CONF = 0.32
YOLO_IMGSZ = 640
# Vazio = aceita todas as classes do modelo. Isso permite trocar entre:
# - modelo antigo com uma classe: mob
# - modelos por mapa: am_mut, dokebi, horong, etc.
YOLO_CLASSES_MOB = set()

# Contraste: fallback quando nao ha templates. Desative se tiver templates bons.
USAR_CONTRASTE = False
CONTRASTE_MIN  = 80
CONTRASTE_AREA = 220   # area minima maior para nao pegar loot/cursor

# Detector generico: procura sprites coloridos/claros no mapa, sem template.
# Funciona como fallback quando o template nao achou nada.
USAR_DETECTOR_SPRITE = False
SPRITE_AREA_MIN = 90
SPRITE_AREA_MAX = 2600
SPRITE_SAT_MIN  = 45
SPRITE_VAL_MIN  = 70
CURSOR_RAIO_IGNORE = 55

# Detector por movimento entre frames. Mais proximo de "se mexeu, e mob".
USAR_DETECTOR_MOVIMENTO = False
MOV_AREA_MIN = 45
MOV_AREA_MAX = 2200
MOV_DIFF_MIN = 18

# â”€â”€ Auto-pocao â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Ajuste as teclas conforme sua hotkey no jogo (barra de consumiveis)
TECLA_POT_HP  = "insert"   # pocao de HP â€” mude para sua tecla
TECLA_POT_SP  = "home"     # pocao de SP â€” mude para sua tecla
HP_MINIMO     = 0.60       # usa pocao HP quando abaixo de 60%
SP_MINIMO     = 0.35       # usa pocao SP quando abaixo de 35%
INTERVALO_POT = 2.5        # segundos minimos entre pots (anti-spam)

# Posicao das barras HP/SP no frame capturado (calibrado para 1286x1024)
# Se a janela for diferente, ajuste estes valores com --verificar
HP_BAR_Y  = 0.066    # linha central do HP bar (% da altura do frame)
HP_BAR_X0 = 0.045    # borda esquerda da barra (% da largura)
HP_BAR_X1 = 0.150    # borda direita

SP_BAR_Y  = 0.080
SP_BAR_X0 = 0.045
SP_BAR_X1 = 0.150

# â”€â”€ Peso / stuck â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
KILLS_AVISO_PESO = 200    # avisa sobre peso a cada N kills
STUCK_SPREAD_MIN = 280    # px â€” variacao minima em 8 exploracoes (abaixo = stuck)

# Navegacao visual: monta uma mascara local de chao caminhavel e escolhe
# waypoints por A* em vez de clicar em direcoes aleatorias.
USAR_MAPA_VISUAL = True
MAPA_LIMIAR_PAREDE = 18
MAPA_CLEARANCE_MIN = 18
MAPA_GRID = 16
MAPA_WAYPOINT_CURTO = 10
MAPA_WAYPOINT_LONGO = 16

# â”€â”€ Anti-jail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ANTIJAIL_ATIVO       = True
# Cores de texto GM no chat (BGR) â€” so coloque cores EXCLUSIVAS de GM
# NAO inclua cores de mensagens automaticas do servidor (ciano, laranja, vermelho)
# Para descobrir a cor real do GM: peca a um amigo GM para te whispar e
# use --verificar para observar o chat naquele momento.
ANTIJAIL_CORES_GM    = [
    (200,  20, 200),   # roxo/magenta â€” whisper de GM (mais comum em RO)
    ( 20,  20, 255),   # azul vivo    â€” alguns servidores usam para GMs
]
ANTIJAIL_TOL_COR     = 40     # tolerancia de cor (0-255)
ANTIJAIL_PIX_MIN     = 60     # pixels minimos para confirmar (mais alto = menos falso positivo)
ANTIJAIL_FRAMES_MIN  = 8      # frames consecutivos necessarios para disparar o alarme
ANTIJAIL_MAPA_DIFF   = 55.0   # diferenca media de pixel para detectar teletransporte
ANTIJAIL_CHAT_Y0     = 0.855  # inicio da area de chat (% da altura)
ANTIJAIL_CHAT_Y1     = 0.960  # fim da area de chat

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

class Estado(Enum):
    """Estados da maquina de combate."""
    BUSCAR    = "BUSCAR"
    APROXIMAR = "APROXIMAR"
    ATACAR    = "ATACAR"
    LOOT      = "LOOT"
    RECUPERAR = "RECUPERAR"


class Logger:
    """Registra todos os eventos em JSON-lines para analise com ro_viewer.py"""
    def __init__(self, j=None):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.arquivo = f"ro_log_{ts}.log"
        self._t0     = time.time()
        self._kills  = 0
        self._j      = j
        self._f      = open(self.arquivo, "w", encoding="utf-8")
        dados = {}
        if j is not None:
            dados = {
                "left": j.left, "top": j.top, "right": j.right, "bottom": j.bottom,
                "width": j.width, "height": j.height,
            }
        self._w("INICIO", dados)
        print(f"  [LOG] {self.arquivo}")

    def _w(self, tipo, dados):
        # Converte numpy int64/float64 para tipos nativos do Python
        def _conv(v):
            if hasattr(v, "item"):   # numpy scalar
                return v.item()
            return v
        entry = {"ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                 "t":  round(time.time() - self._t0, 2),
                 "ev": tipo}
        entry.update({k: _conv(v) for k, v in dados.items()})
        self._f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._f.flush()

    def _xy(self, x, y, extra=None):
        dados = {"x": x, "y": y}
        if self._j is not None:
            rx, ry = x - self._j.left, y - self._j.top
            dados.update({
                "rx": rx, "ry": ry,
                "inside": 0 <= rx < self._j.width and 0 <= ry < self._j.height,
            })
        if extra:
            dados.update(extra)
        return dados

    def mob(self, ax, ay, qtd):    self._w("MOB",    self._xy(ax, ay, {"qtd": qtd}))
    def move(self, ax, ay):        self._w("MOVE",   self._xy(ax, ay))
    def skip(self, ax, ay):        self._w("SKIP",   self._xy(ax, ay))
    def skill(self, tecla, ciclo): self._w("SKILL",  {"k": tecla, "c": ciclo})
    def miss(self, ax, ay):        self._w("MISS",   self._xy(ax, ay))
    def loot(self, ax, ay):        self._w("LOOT",   self._xy(ax, ay))
    def explore(self, tx, ty, ok): self._w("EXPLORE",self._xy(tx, ty, {"ok": ok}))
    def idle(self, n):             self._w("IDLE",   {"n": n})
    def pot(self, tipo, nivel):    self._w("POT",      {"tipo": tipo, "nivel": round(nivel, 2)})
    def morte(self):               self._w("MORTE",    {})
    def stuck(self):               self._w("STUCK",    {})
    def antijail(self, motivo):    self._w("ANTIJAIL", {"motivo": motivo})
    def refresh(self, motivo):      self._w("REFRESH",  {"motivo": motivo})
    def path(self, ax, ay, motivo): self._w("PATH",     self._xy(ax, ay, {"motivo": motivo}))

    def kill(self, ax, ay, ciclos):
        self._kills += 1
        self._w("KILL", self._xy(ax, ay, {"n": self._kills, "c": ciclos}))

    def fim(self, kills, t_s):
        self._w("FIM", {"kills": kills, "t": round(t_s), "max_c": MAX_CICLOS_ATAQUE})
        self._f.close()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

rodando         = True
templates       = []
template_masks  = []
yolo_model      = None
_yolo_avisou    = False
log             = None
_blacklist      = []   # [(x, y, t)] â€” posicoes MISS recentes, ignoradas na deteccao
_hist_explore        = []   # [(x, y, t)] â€” historico de exploracao para evitar circulos
_ultimo_pot          = {"hp": 0.0, "sp": 0.0}
_ultimo_refresh      = 0.0
_mapa_fp_ref         = None  # fingerprint do mapa de referencia para detectar jail
_antijail_contador   = 0     # frames consecutivos com cor suspeita (evita falso positivo)
_hp_ultimo           = 1.0   # HP do frame anterior para detectar dano recebido
_mov_frame_ant       = None  # frame anterior para detector por movimento
_walk_cache_key      = None
_walk_cache_mask     = None
_walk_cache_frame    = None
_aprox_watch         = {"x": None, "y": None, "dist": None, "fails": 0}
_aprox_bloqueado     = False
_explore_until       = 0.0
_explore_dest        = None
_explore_heading     = None  # (angulo_rad, timestamp) da direcao recente de varredura
_alvo_lock           = None  # (ax, ay) do alvo travado na sessao de combate atual
_alvo_lock_t         = 0.0   # timestamp de quando o lock foi criado
_track_ids           = {}    # (mx, my) -> track_id da ultima deteccao YOLO
_walk_hist           = []    # ultimos WALK_HIST_N frames do mapa caminhavel

# Scan assincrono
import queue as _queue_mod
_scan_queue  = _queue_mod.Queue(maxsize=2)   # frame+mobs pre-calculados pelo worker
_scan_model  = None                          # instancia YOLO separada para o worker

HIST_RAIO  = 120   # px â€” raio de exclusao do historico de exploracao
HIST_TEMPO = 90    # segundos

# â”€â”€ HP / SP / recursos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _ler_barra(frame, y_pct, x0_pct, x1_pct):
    """Retorna nivel 0.0-1.0 da barra contando pixels brilhantes (preenchidos)."""
    h, w = frame.shape[:2]
    y  = int(h * y_pct)
    x0 = int(w * x0_pct)
    x1 = int(w * x1_pct)
    if not (0 <= y < h and 0 < x0 < x1 <= w):
        return 1.0
    linha  = frame[y, x0:x1]
    brilho = np.mean(linha, axis=1)
    return float(np.sum(brilho > 55)) / float(len(brilho))

def verificar_hp_sp(frame, j):
    """
    Le HP e SP do frame capturado. Usa pocoes se necessario.
    Retorna (morto, tomou_dano):
      morto     â€” True se HP < 2%
      tomou_dano â€” True se HP caiu > 1.5% desde o ultimo frame
    """
    global _ultimo_pot, _hp_ultimo
    hp = _ler_barra(frame, HP_BAR_Y, HP_BAR_X0, HP_BAR_X1)
    sp = _ler_barra(frame, SP_BAR_Y, SP_BAR_X0, SP_BAR_X1)
    agora = time.time()

    tomou_dano = hp < _hp_ultimo - 0.015   # queda de 1.5% = dano real
    _hp_ultimo = hp

    if hp < 0.02:
        print("  [MORTE] HP zerado â€” encerrando bot")
        if log: log.morte()
        return True, True

    if hp < HP_MINIMO and (agora - _ultimo_pot["hp"]) > INTERVALO_POT:
        focar(j)
        pyautogui.press(TECLA_POT_HP)
        _ultimo_pot["hp"] = agora
        print(f"  [POT HP]  {hp:.0%} â€” pocao usada")
        if log: log.pot("hp", hp)

    if sp < SP_MINIMO and (agora - _ultimo_pot["sp"]) > INTERVALO_POT:
        focar(j)
        pyautogui.press(TECLA_POT_SP)
        _ultimo_pot["sp"] = agora
        print(f"  [POT SP]  {sp:.0%} â€” pocao usada")
        if log: log.pot("sp", sp)

    return False, tomou_dano

def _verificar_stuck():
    """Retorna True se as ultimas 8 exploracoes cobriram area muito pequena (personagem preso)."""
    if len(_hist_explore) < 8:
        return False
    recentes = _hist_explore[-8:]
    xs = [h[0] for h in recentes]
    ys = [h[1] for h in recentes]
    spread = (max(xs) - min(xs)) + (max(ys) - min(ys))
    return spread < STUCK_SPREAD_MIN

# â”€â”€ Anti-jail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _fingerprint_mapa(frame):
    """
    Amostra 9 pontos do fundo do mapa ao redor do personagem.
    Retorna vetor BGR medio para comparacao â€” muda drasticamente em jail.
    """
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    offsets = [(-220,-150),(0,-150),(220,-150),
               (-220,0),   (0,0),   (220,0),
               (-220,150), (0,150), (220,150)]
    amostras = []
    for dx, dy in offsets:
        px, py = cx + dx, cy + dy
        if 0 <= px < w and 0 <= py < h:
            amostras.append(frame[py, px].astype(float))
    return np.mean(amostras, axis=0) if amostras else np.zeros(3)

def _scan_chat_gm(frame):
    """
    Varre a area de chat em busca de pixels com cores tipicas de mensagem GM.
    Retorna True se detectar texto colorido suspeito.
    """
    h, w = frame.shape[:2]
    y0 = int(h * ANTIJAIL_CHAT_Y0)
    y1 = int(h * ANTIJAIL_CHAT_Y1)
    x1 = int(w * 0.48)
    if y1 >= h or y0 >= y1:
        return False

    chat = frame[y0:y1, 0:x1].astype(int)
    for cor in ANTIJAIL_CORES_GM:
        c = np.array(cor, dtype=int)
        dist = np.max(np.abs(chat - c), axis=2)   # distancia Linf de cada pixel
        if int(np.sum(dist < ANTIJAIL_TOL_COR)) >= ANTIJAIL_PIX_MIN:
            return True
    return False

def antijail_verificar(frame):
    """
    Verifica dois sinais de GM/jail:
      1. Mensagem colorida de GM no chat (requer ANTIJAIL_FRAMES_MIN frames consecutivos)
      2. Teletransporte abrupto (fingerprint do mapa muda muito)
    Retorna string com o motivo ou None se tudo normal.
    """
    global _mapa_fp_ref, _antijail_contador

    if not ANTIJAIL_ATIVO:
        return None

    # -- Scan de chat (com confirmacao por frames consecutivos) -------
    if _scan_chat_gm(frame):
        _antijail_contador += 1
        if _antijail_contador >= ANTIJAIL_FRAMES_MIN:
            _antijail_contador = 0
            return "MENSAGEM_GM"
    else:
        _antijail_contador = max(0, _antijail_contador - 1)  # decai gradualmente

    # -- Fingerprint de mapa ------------------------------------------
    fp_atual = _fingerprint_mapa(frame)
    if _mapa_fp_ref is None:
        _mapa_fp_ref = fp_atual
    else:
        diff = float(np.mean(np.abs(fp_atual - _mapa_fp_ref)))
        if diff > ANTIJAIL_MAPA_DIFF:
            # Confirma em 2 frames para evitar flash de efeito visual
            _mapa_fp_ref = fp_atual  # reseta referencia
            return "JAIL_TELEPORT"
        _mapa_fp_ref = 0.97 * _mapa_fp_ref + 0.03 * fp_atual

    return None

def antijail_alertar(j, motivo):
    """Para o bot, emite alarme sonoro e popup de alerta."""
    global rodando
    rodando = False

    msg = {
        "MENSAGEM_GM":   "MENSAGEM DE GM DETECTADA NO CHAT",
        "JAIL_TELEPORT": "TELETRANSPORTE SUSPEITO (JAIL?)",
    }.get(motivo, motivo)

    print()
    print("!" * 56)
    print(f"  [ANTIJAIL] {msg}")
    print("  Bot pausado â€” verifique o jogo imediatamente!")
    print("!" * 56)
    print()

    if log:
        log.antijail(motivo)

    # Alarme sonoro (5 bipes rapidos)
    try:
        import winsound
        for _ in range(5):
            winsound.Beep(1200, 250)
            time.sleep(0.15)
    except Exception:
        pass

    # Popup de alerta (bloqueia ate o usuario clicar OK)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"[ANTIJAIL] {msg}\n\nVerifique o chat e o personagem!\nClique OK para fechar o bot.",
            "RO BOT â€” ALERTA",
            0x30 | 0x1000   # MB_ICONWARNING | MB_SYSTEMMODAL
        )
    except Exception:
        pass

# â”€â”€ janela â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def pegar_janela():
    lst = gw.getWindowsWithTitle(JANELA)
    if not lst:
        print(f"[ERRO] Janela '{JANELA}' nao encontrada.")
        sys.exit(1)
    return lst[0]

def pegar_hwnd():
    hwnd = win32gui.FindWindow(None, JANELA)
    if not hwnd:
        print("[ERRO] Handle nao encontrado."); sys.exit(1)
    return hwnd

def focar(j):
    try:
        if j.isMinimized:
            j.restore(); time.sleep(0.3)
        j.activate(); time.sleep(0.05)
    except Exception:
        pass

def janela_valida(j):
    try:
        return j.width >= 500 and j.height >= 300 and j.left > -10000 and j.top > -10000
    except Exception:
        return False

def preparar_janela(j, tentativas=5):
    """Garante geometria real antes de captura/log; evita rect 160x28/-32000."""
    ultimo = j
    for i in range(tentativas):
        try:
            focar(ultimo)
            time.sleep(0.15)
            atual = pegar_janela()
            if janela_valida(atual):
                return atual
            ultimo = atual
        except Exception:
            pass
        time.sleep(0.2 + i * 0.05)
    return ultimo

# â”€â”€ captura via PrintWindow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def capturar_cv(hwnd, j):
    w, h = j.width, j.height
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    bmp    = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0)
    raw = bmp.GetBitmapBits(True)
    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC(); mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    img = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

# â”€â”€ templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

template_nomes = []   # nome de cada template carregado (para debug no --verificar)

def _preparar_template(img):
    """
    Retorna (bgr, mask). A mask remove fundo/transparencia do template para
    o match nao ser dominado por pixels pretos ou pelo chao do recorte.
    """
    if img is None:
        return None, None

    if img.ndim == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3].copy()
        mask = (img[:, :, 3] > 10).astype(np.uint8) * 255
        bgr[mask == 0] = 0
    else:
        bgr = img[:, :, :3].copy()
        bordas = np.concatenate(
            [bgr[0, :, :], bgr[-1, :, :], bgr[:, 0, :], bgr[:, -1, :]],
            axis=0
        )
        fundo = np.median(bordas.reshape(-1, 3), axis=0)
        dist = np.max(np.abs(bgr.astype(int) - fundo.astype(int)), axis=2)
        mask = (dist > 18).astype(np.uint8) * 255

        if int(np.sum(mask > 0)) < TEMPLATE_MIN_PIXELS:
            brilho = np.mean(bgr, axis=2)
            mask = (brilho > 12).astype(np.uint8) * 255

    if int(np.sum(mask > 0)) < TEMPLATE_MIN_PIXELS:
        return None, None

    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        return None, None

    pad = 3
    h, w = bgr.shape[:2]
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(w, int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(h, int(ys.max()) + pad + 1)
    bgr = bgr[y0:y1, x0:x1].copy()
    mask = mask[y0:y1, x0:x1].copy()
    return bgr, mask

def carregar_templates():
    global templates, template_masks, template_nomes
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    arquivos = sorted(glob.glob(os.path.join(TEMPLATES_DIR, "mob_*.png")))
    carregados = []
    for f in arquivos:
        img = cv2.imread(f, cv2.IMREAD_UNCHANGED)
        bgr, mask = _preparar_template(img)
        if bgr is not None and mask is not None:
            carregados.append((f, bgr, mask))
        else:
            print(f"  [AVISO] Template ignorado (poucos pixels uteis): {os.path.basename(f)}")

    templates      = [img for _, img, _ in carregados]
    template_masks = [mask for _, _, mask in carregados]
    template_nomes = [os.path.basename(f) for f, _, _ in carregados]
    if templates:
        print(f"  [OK] {len(templates)} template(s): {template_nomes}")
        return True
    if not USAR_CONTRASTE:
        print(f"  [AVISO] Sem templates. Rode: python ro_bot.py --capturar")
        return False
    print(f"  [OK] Sem templates â€” usando contraste (fundo preto)")
    return True

def proximo_nome_template():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    i = 0
    while os.path.exists(os.path.join(TEMPLATES_DIR, f"mob_{i}.png")):
        i += 1
    return os.path.join(TEMPLATES_DIR, f"mob_{i}.png")

def carregar_yolo(silencioso=False):
    global yolo_model, _yolo_avisou

    if not USAR_YOLO:
        return False
    if yolo_model is not None:
        return True
    if not os.path.exists(YOLO_MODEL_PATH):
        if not silencioso and not _yolo_avisou:
            print(f"  [YOLO] Modelo nao encontrado: {YOLO_MODEL_PATH}")
            print("  [YOLO] Capture frames com --dataset e treine com ro_yolo_train.py")
            _yolo_avisou = True
        return False

    try:
        from ultralytics import YOLO
        yolo_model = YOLO(YOLO_MODEL_PATH)
        print(f"  [YOLO] Modelo carregado: {YOLO_MODEL_PATH}")
        return True
    except Exception as e:
        if not silencioso and not _yolo_avisou:
            print(f"  [YOLO] Falha ao carregar modelo: {e}")
            print("  [YOLO] Instale: python -m pip install ultralytics")
            _yolo_avisou = True
        return False

# â”€â”€ deteccao â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _mascara_interface(frame):
    h, w = frame.shape[:2]
    mask = np.ones((h, w), dtype=np.uint8) * 255
    mask[:int(h*0.08), :] = 0
    mask[int(h*0.85):, :] = 0
    mask[:, :int(w*0.04)] = 0
    mask[:, int(w*ROI_DIREITA_MAX):] = 0
    mask[:int(h*0.24), :int(w*0.47)] = 0
    mask[int(h*0.82):, :int(w*0.48)] = 0
    return mask

def _mascara_roi(frame):
    h, w = frame.shape[:2]
    roi = frame.copy()
    roi[:int(h*0.08), :]  = 0   # topo completo
    roi[int(h*0.85):, :]  = 0   # chat/barras inferiores
    roi[:, :int(w*0.04)]  = 0   # borda esq
    roi[:, int(w*ROI_DIREITA_MAX):]  = 0   # painel direito: quests + minimap + borda
    # Painel esquerdo completo: char info + barras de skill + botao ITEM
    # Cobre ate 20% de altura x 40% de largura (inclui botao ITEM a y~15%, x~37%)
    roi[:int(h*0.24), :int(w*0.47)] = 0
    roi[int(h*0.82):, :int(w*0.48)] = 0  # chat/battle log inferior esquerdo

    # Mascara apenas o sprite do personagem (minimal â€” sem efeitos visuais)
    cx, cy = w // 2, h // 2
    # Mascara minima: cobre apenas o sprite imediato do personagem.
    # Antes era 7%/14%/11% (271Ã—258px) â€” mobs a 200px ficavam invisiveis.
    # Agora 4%/8%/6% (155Ã—144px) â€” YOLO detecta mobs bem mais perto.
    mx = int(w * 0.04)
    y0 = max(0, cy - int(h * 0.08))
    y1 = min(h, cy + int(h * 0.06))
    roi[y0:y1, cx-mx : cx+mx] = 0

    return roi

def _perto_do_mouse(x, y, raio=CURSOR_RAIO_IGNORE):
    try:
        mx, my = win32api.GetCursorPos()
        return abs(x - mx) < raio and abs(y - my) < raio
    except Exception:
        return False

def detectar_por_contraste(frame, j):
    roi  = _mascara_roi(frame)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, CONTRASTE_MIN, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mobs = []
    cx_c = (j.left + j.right)  // 2
    cy_c = (j.top  + j.bottom) // 2
    fh, fw = frame.shape[:2]
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < CONTRASTE_AREA:
            continue
        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw > fw*0.25 or bh > fh*0.25:
            continue
        # Rejeita deteccoes cujo centro esta sobre pixel muito escuro (parede/fundo)
        # Verifica um patch ao redor do centro do contorno no frame original
        cx_cnt, cy_cnt = bx + bw // 2, by + bh // 2
        px0 = max(0, cx_cnt-8); px1 = min(fw, cx_cnt+9)
        py0 = max(0, cy_cnt-8); py1 = min(fh, cy_cnt+9)
        brilho_local = float(np.mean(frame[py0:py1, px0:px1]))
        if brilho_local < 25:  # area totalmente preta = parede
            continue
        tx = int(j.left + cx_cnt)
        ty = int(j.top  + cy_cnt)
        mobs.append((tx, ty))
    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    return mobs

def detectar_por_yolo(frame, j, com_info=False):
    if not carregar_yolo(silencioso=True):
        return []

    roi = _mascara_roi(frame)
    try:
        if USAR_YOLO_TRACKING:
            results = yolo_model.track(
                source=roi,
                conf=YOLO_CONF,
                imgsz=YOLO_IMGSZ,
                persist=True,
                verbose=False,
            )
        else:
            results = yolo_model.predict(
                source=roi,
                conf=YOLO_CONF,
                imgsz=YOLO_IMGSZ,
                verbose=False,
            )
    except Exception as e:
        print(f"  [YOLO] Erro na inferencia: {e}")
        return []

    if not results:
        return []

    result = results[0]
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    mobs = []
    cx_c = (j.left + j.right)  // 2
    cy_c = (j.top  + j.bottom) // 2

    for box in boxes:
        try:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            label = str(names.get(cls_id, cls_id)).lower()
            if YOLO_CLASSES_MOB and label not in YOLO_CLASSES_MOB and cls_id != 0:
                continue
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            track_id = (int(box.id[0].item())
                        if (USAR_YOLO_TRACKING and box.id is not None)
                        else None)
        except Exception:
            continue

        mx = int(j.left + (x1 + x2) / 2)
        # Ragnarok 2.5D interage melhor na base do sprite; o centro da bbox
        # costuma cair na cabeca/corpo e distorce range/parede. A validacao
        # testa alguns pontos para nao perder mob por sombra/HP bar.
        candidatos_y = [
            int(j.top + y1 + (y2 - y1) * YOLO_TARGET_Y_RATIO),
            int(j.top + y1 + (y2 - y1) * 0.64),
            int(j.top + y1 + (y2 - y1) * 0.84),
            int(j.top + y1 + (y2 - y1) * 0.52),
        ]
        my = candidatos_y[0]
        if _perto_do_mouse(mx, my):
            continue
        if not any(_pixel_caminhavel(frame, j, mx, cy) for cy in candidatos_y):
            continue
        if any((mx - ox) ** 2 + (my - oy) ** 2 < TEMPLATE_NMS_RAIO ** 2
               for ox, oy, _, _ in mobs):
            continue
        mobs.append((mx, my, f"YOLO:{label}", conf))
        _track_ids[(mx, my)] = track_id   # grava ID para lookup no state-machine

    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    if com_info:
        return mobs
    return [(mx, my) for mx, my, _, _ in mobs]

def detectar_por_template(frame, j, com_info=False):
    """
    com_info=True: retorna lista de (x, y, nome_template, score) para debug.
    com_info=False (padrao): retorna lista de (x, y).
    """
    if not templates:
        return []
    roi = _mascara_roi(frame)
    candidatos = []
    cx_c = (j.left + j.right)  // 2
    cy_c = (j.top  + j.bottom) // 2
    for t_idx, tmpl in enumerate(templates):
        mask = template_masks[t_idx] if t_idx < len(template_masks) else None
        if mask is None:
            continue
        for escala in TEMPLATE_ESCALAS:
            if escala == 1.0:
                tmpl_s, mask_s = tmpl, mask
            else:
                th0, tw0 = tmpl.shape[:2]
                tw_s = max(8, int(tw0 * escala))
                th_s = max(8, int(th0 * escala))
                tmpl_s = cv2.resize(tmpl, (tw_s, th_s), interpolation=cv2.INTER_AREA)
                mask_s = cv2.resize(mask, (tw_s, th_s), interpolation=cv2.INTER_NEAREST)

            th, tw = tmpl_s.shape[:2]
            if roi.shape[0] < th or roi.shape[1] < tw:
                continue
            if int(np.sum(mask_s > 0)) < TEMPLATE_MIN_PIXELS:
                continue

            res  = cv2.matchTemplate(roi, tmpl_s, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= THRESHOLD)
            for py, px in zip(locs[0], locs[1]):
                score = float(res[py, px])
                mx    = int(j.left + px + tw//2)
                my    = int(j.top  + py + th//2)
                nome  = template_nomes[t_idx] if t_idx < len(template_nomes) else f"tmpl{t_idx}"
                candidatos.append((mx, my, nome, score))

    candidatos.sort(key=lambda p: p[3], reverse=True)
    mobs = []
    for cand in candidatos:
        mx, my = cand[0], cand[1]
        if any((mx - ox) ** 2 + (my - oy) ** 2 < TEMPLATE_NMS_RAIO ** 2
               for ox, oy, _, _ in mobs):
            continue
        mobs.append(cand)

    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    if com_info:
        return mobs
    return [(mx, my) for mx, my, _, _ in mobs]

BLACKLIST_RAIO  = 90   # pixels â€” raio de exclusao ao redor de um MISS
BLACKLIST_TEMPO = 45   # segundos â€” quanto tempo ignorar a posicao

def detectar_por_sprite(frame, j, com_info=False):
    """
    Detector generico sem template: procura componentes coloridos/claros sobre
    o mapa ja mascarado. E um fallback; pode pegar efeitos se usado sozinho.
    """
    roi = _mascara_roi(frame)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    mask_cor = ((sat >= SPRITE_SAT_MIN) & (val >= SPRITE_VAL_MIN)) | (val >= 135)
    mask = mask_cor.astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mobs = []
    cx_c = (j.left + j.right)  // 2
    cy_c = (j.top  + j.bottom) // 2
    fh, fw = frame.shape[:2]

    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < SPRITE_AREA_MIN or area > SPRITE_AREA_MAX:
            continue

        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw < 8 or bh < 8 or bw > 95 or bh > 125:
            continue
        if bw / max(bh, 1) > 2.8 or bh / max(bw, 1) > 3.5:
            continue

        cx_cnt, cy_cnt = bx + bw // 2, by + bh // 2
        px0 = max(0, cx_cnt - 10); px1 = min(fw, cx_cnt + 11)
        py0 = max(0, cy_cnt - 10); py1 = min(fh, cy_cnt + 11)
        patch = frame[py0:py1, px0:px1]
        if patch.size == 0:
            continue

        brilho_local = float(np.mean(patch))
        if brilho_local < 25:
            continue

        tx = int(j.left + cx_cnt)
        ty = int(j.top  + cy_cnt)
        if _perto_do_mouse(tx, ty):
            continue
        if not _pixel_caminhavel(frame, j, tx, ty):
            continue
        if any((tx - ox) ** 2 + (ty - oy) ** 2 < TEMPLATE_NMS_RAIO ** 2
               for ox, oy, _, _ in mobs):
            continue
        mobs.append((tx, ty, "SPRITE", 0.0))

    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    if com_info:
        return mobs
    return [(mx, my) for mx, my, _, _ in mobs]

def detectar_por_movimento(frame, j, com_info=False):
    global _mov_frame_ant

    roi = _mascara_roi(frame)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    if _mov_frame_ant is None or _mov_frame_ant.shape != gray.shape:
        _mov_frame_ant = gray
        return []

    diff = cv2.absdiff(gray, _mov_frame_ant)
    _mov_frame_ant = gray

    _, mask = cv2.threshold(diff, MOV_DIFF_MIN, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    mask = cv2.dilate(mask, np.ones((4, 4), np.uint8), iterations=1)

    if float(np.mean(mask > 0)) > 0.08:
        return []

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mobs = []
    cx_c = (j.left + j.right)  // 2
    cy_c = (j.top  + j.bottom) // 2

    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < MOV_AREA_MIN or area > MOV_AREA_MAX:
            continue

        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bw < 7 or bh < 7 or bw > 100 or bh > 130:
            continue
        if bw / max(bh, 1) > 3.0 or bh / max(bw, 1) > 3.8:
            continue

        cx_cnt, cy_cnt = bx + bw // 2, by + bh // 2
        tx = int(j.left + cx_cnt)
        ty = int(j.top  + cy_cnt)
        if _perto_do_mouse(tx, ty):
            continue
        if not _pixel_caminhavel(frame, j, tx, ty):
            continue
        if any((tx - ox) ** 2 + (ty - oy) ** 2 < TEMPLATE_NMS_RAIO ** 2
               for ox, oy, _, _ in mobs):
            continue
        mobs.append((tx, ty, "MOV", 0.0))

    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    if com_info:
        return mobs
    return [(mx, my) for mx, my, _, _ in mobs]

def _blacklist_add(x, y):
    _blacklist.append((x, y, time.time()))

def _blacklist_check(x, y):
    agora = time.time()
    # Limpa entradas expiradas
    _blacklist[:] = [(bx, by, bt) for bx, by, bt in _blacklist
                     if agora - bt < BLACKLIST_TEMPO]
    return any(abs(x - bx) < BLACKLIST_RAIO and abs(y - by) < BLACKLIST_RAIO
               for bx, by, bt in _blacklist)

def detectar_mobs(frame, j):
    mobs = detectar_por_yolo(frame, j)
    if not mobs:
        mobs = detectar_por_template(frame, j)
    if not mobs and USAR_DETECTOR_MOVIMENTO:
        mobs = detectar_por_movimento(frame, j)
    if not mobs and USAR_DETECTOR_SPRITE:
        mobs = detectar_por_sprite(frame, j)
    if not mobs and USAR_CONTRASTE:
        mobs = detectar_por_contraste(frame, j)
    # Remove posicoes com MISS recente e cursor do mouse
    cx_mouse, cy_mouse = win32api.GetCursorPos()
    mobs = [(mx, my) for mx, my in mobs
            if not _blacklist_check(mx, my)
            and not (abs(mx - cx_mouse) < CURSOR_RAIO_IGNORE
                     and abs(my - cy_mouse) < CURSOR_RAIO_IGNORE)]
    if LOS_MOB_ATIVO:
        mobs = [(mx, my) for mx, my in mobs
                if alvo_com_los(frame, j, mx, my)]
    return mobs

def dentro_da_janela(j, x, y, margem=0):
    return (j.left + margem <= x < j.right - margem and
            j.top + margem <= y < j.bottom - margem)

def alvo_com_los(frame, j, x, y):
    rx, ry = x - j.left, y - j.top
    h, w = frame.shape[:2]
    if not (0 <= rx < w and 0 <= ry < h):
        return False
    return _alvo_tem_caminho(frame, j, x, y)

def mob_ainda_vivo(hwnd, j, ax, ay, raio=80):
    """Verifica se ainda tem mob na posicao do alvo."""
    frame = capturar_cv(hwnd, j)
    mobs  = detectar_mobs(frame, j)
    return any(abs(mx-ax) < raio and abs(my-ay) < raio for mx, my in mobs)

def _mob_perto(mobs, ax, ay, raio=ALVO_REAQUIRE_RAIO):
    if not mobs:
        return None
    candidatos = []
    for mx, my in mobs:
        d2 = (mx - ax) ** 2 + (my - ay) ** 2
        if d2 <= raio ** 2:
            candidatos.append((d2, mx, my))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0])
    return candidatos[0][1], candidatos[0][2]

def _rastrear_alvo(mobs, ax, ay, track_id=None):
    """
    Localiza o alvo entre os mobs detectados.
    Prioridade 1: track_id YOLO (ID persistente entre frames).
    Prioridade 2: proximidade geometrica via _mob_perto.
    Retorna (mx, my) ou None.
    """
    if not mobs:
        return None
    if track_id is not None:
        for mx, my in mobs:
            if _track_ids.get((mx, my)) == track_id:
                return (mx, my)
    return _mob_perto(mobs, ax, ay)


def aguardar_reaquisicao(hwnd, j, ax, ay, timeout=ALVO_GRACE_S):
    fim = time.time() + timeout
    ultimo = None
    while rodando and time.time() < fim:
        frame = capturar_cv(hwnd, j)
        mobs = detectar_mobs(frame, j)
        alvo = _mob_perto(mobs, ax, ay)
        if alvo:
            return alvo, len(mobs)
        if mobs:
            ultimo = mobs[0], len(mobs)
        time.sleep(ALVO_RECHECK_S)
    return ultimo if ultimo else (None, 0)

def distancia_do_personagem(j, x, y):
    cx = (j.left + j.right) // 2
    cy = (j.top + j.bottom) // 2
    return ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5

def _aprox_watch_reset():
    _aprox_watch.update({"x": None, "y": None, "dist": None, "fails": 0})

def _aprox_watch_update(ax, ay, dist):
    if not APROX_WATCH_ATIVO:
        return False
    last_x = _aprox_watch["x"]
    last_y = _aprox_watch["y"]
    last_dist = _aprox_watch["dist"]
    mesmo_alvo = (
        last_x is not None and last_y is not None and
        abs(ax - last_x) < APROX_WATCH_RAIO and
        abs(ay - last_y) < APROX_WATCH_RAIO
    )

    if mesmo_alvo and last_dist is not None:
        ganho = last_dist - dist
        if ganho < APROX_WATCH_MIN_DELTA:
            _aprox_watch["fails"] += 1
        else:
            _aprox_watch["fails"] = 0
    else:
        _aprox_watch["fails"] = 0

    _aprox_watch["x"] = ax
    _aprox_watch["y"] = ay
    _aprox_watch["dist"] = dist
    return _aprox_watch["fails"] >= APROX_WATCH_TENTATIVAS

def aproximar_ate_range(hwnd, j, ax, ay):
    """Se estiver fora do range, faz um passo e devolve ao loop principal."""
    global _aprox_bloqueado, _explore_until
    _aprox_bloqueado = False
    dist = distancia_do_personagem(j, ax, ay)
    if dist <= COMBATE_RANGE_PX:
        _aprox_watch_reset()
        return ax, ay, True

    if _aprox_watch_update(ax, ay, dist):
        _blacklist_add(ax, ay)
        _aprox_bloqueado = True
        print(f"  [PATH] Alvo inalcanÃ§avel ({dist:.0f}px sem progresso); blacklist temporaria")
        _aprox_watch_reset()
        return ax, ay, False

    cx = (j.left + j.right) // 2
    cy = (j.top + j.bottom) // 2
    tx = int(cx + (ax - cx) * COMBATE_APROX_FATOR)
    ty = int(cy + (ay - cy) * COMBATE_APROX_FATOR)
    if COMBATE_USAR_WAYPOINT:
        frame = capturar_cv(hwnd, j)
        waypoint = _waypoint_para_alvo(frame, j, ax, ay, dist)
        if waypoint is None:
            _blacklist_add(ax, ay)
            _aprox_bloqueado = True
            if log: log.path(ax, ay, "sem_caminho")
            print(f"  [PATH] Sem caminho visual ate o alvo ({dist:.0f}px); blacklist temporaria")
            _aprox_watch_reset()
            return ax, ay, False
        tx, ty = waypoint
    print(f"  [RANGE] Aproximando ({dist:.0f}px -> alvo); recalcula no proximo frame")
    if log: log.move(ax, ay)
    passo_estereo(j, tx, ty)
    _explore_until = max(_explore_until, time.time() + 0.85)
    time.sleep(COMBATE_MOVE_SETTLE_S)
    return ax, ay, False

# â”€â”€ click e acoes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def mouse_click(x, y):
    win32api.SetCursorPos((x, y))
    time.sleep(0.04)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,   0, 0, 0, 0)

def parar_movimento(j):
    """Interrompe clique de exploracao anterior clicando perto do personagem."""
    cx = (j.left + j.right) // 2
    cy = (j.top + j.bottom) // 2
    mouse_click(cx, cy)
    time.sleep(0.08)

def forcar_refresh(j, motivo, ignorar_cooldown=False):
    global _ultimo_refresh
    if not REFRESH_ATIVO:
        return False
    agora = time.time()
    if not ignorar_cooldown and (agora - _ultimo_refresh) < REFRESH_COOLDOWN_S:
        return False

    focar(j)
    print(f"  [REFRESH] {motivo}")
    if log: log.refresh(motivo)
    pyautogui.hotkey(TECLA_REFRESH_MOD, TECLA_REFRESH_KEY)
    _ultimo_refresh = agora
    time.sleep(0.45)
    return True

def passo_estereo(j, x, y):
    focar(j)
    win32api.SetCursorPos((x, y))
    time.sleep(0.05)
    pyautogui.press(TECLA_PASSO)
    time.sleep(0.05)
    mouse_click(x, y)
    time.sleep(DELAY_PASSO)

def rotacao_skills(j, ciclo=0, ax=None, ay=None):
    """Executa uma rotacao completa de skills."""
    focar(j)
    pyautogui.press(TECLA_TAB)
    time.sleep(0.08)
    if ax is not None and ay is not None:
        win32api.SetCursorPos((ax, ay))
        time.sleep(0.05)
    for tecla, delay in ROTACAO:
        if not rodando: return
        pyautogui.press(tecla)
        if SKILL_CLICAR_ALVO and ax is not None and ay is not None:
            time.sleep(SKILL_CLICK_DELAY_S)
            mouse_click(ax, ay)
        if log: log.skill(tecla, ciclo)
        time.sleep(delay + SKILL_POS_CAST_S)

def lotar_area(j, ax, ay):
    """Move ate o loot e pressiona a tecla de coletar."""
    focar(j)
    # move o cursor para onde o mob morreu e clica para ir ate la
    win32api.SetCursorPos((ax, ay))
    time.sleep(0.05)
    mouse_click(ax, ay)
    time.sleep(0.4)
    for _ in range(5):
        pyautogui.press(TECLA_LOOT)
        time.sleep(DELAY_LOOT)

def combater(hwnd, j, ax, ay):
    """
    Rotacao de ataque apos teleporte de 60% do caminho.
    O mob fica a ~40% da distancia original â€” fora da mascara central, detectavel.
    Retorna o ciclo em que o mob morreu (truthy) ou False.
    """
    # Pre-check: apos teleporte parcial o mob deve estar visivel
    frame_pre = capturar_cv(hwnd, j)
    mobs_pre  = len(detectar_mobs(frame_pre, j))
    if mobs_pre == 0:
        print("  [SKIP] Nenhum mob visivel apos mover â€” ignorando")
        if log: log.skip(ax, ay)
        return False

    for ciclo in range(1, MAX_CICLOS_ATAQUE + 1):
        if not rodando:
            return False
        rotacao_skills(j, ciclo)

        frame_pos = capturar_cv(hwnd, j)
        mobs_pos  = len(detectar_mobs(frame_pos, j))
        if mobs_pos < mobs_pre:
            print(f"  [KILL] Mob morreu no ciclo {ciclo}")
            return ciclo

    print(f"  [MISS] Mob sobreviveu {MAX_CICLOS_ATAQUE} ciclos â€” pulando")
    if log: log.miss(ax, ay)
    return False

def combater_com_persistencia(hwnd, j, ax, ay):
    """
    Combate com debounce de visao.
    Retorna int=kill, False=miss confirmado, None=alvo piscou/nao blacklistar.
    """
    frame_pre = capturar_cv(hwnd, j)
    mobs_pre_lista = detectar_mobs(frame_pre, j)
    alvo_pre = _mob_perto(mobs_pre_lista, ax, ay)
    if alvo_pre:
        ax, ay = alvo_pre
    elif mobs_pre_lista:
        ax, ay = mobs_pre_lista[0]

    mobs_pre = len(mobs_pre_lista)
    if mobs_pre == 0:
        print("  [LOCK] Alvo sumiu apos mover; aguardando reacquisicao...")
        alvo, qtd = aguardar_reaquisicao(hwnd, j, ax, ay)
        if alvo:
            ax, ay = alvo
            mobs_pre = max(1, qtd)
            print(f"  [LOCK] Alvo reacquirido em ({ax},{ay})")
        else:
            print("  [SKIP] Alvo nao confirmado; sem blacklist")
            if log: log.skip(ax, ay)
            return None

    for ciclo in range(1, MAX_CICLOS_ATAQUE + 1):
        if not rodando:
            return None

        ax, ay, em_range = aproximar_ate_range(hwnd, j, ax, ay)
        if not em_range:
            if _aprox_bloqueado:
                return "blocked"
            return None

        rotacao_skills(j, ciclo, ax, ay)
        frame_pos = capturar_cv(hwnd, j)
        mobs_pos_lista = detectar_mobs(frame_pos, j)
        alvo_pos = _mob_perto(mobs_pos_lista, ax, ay)
        mobs_pos = len(mobs_pos_lista)

        if mobs_pos < mobs_pre:
            print(f"  [KILL] Mob morreu no ciclo {ciclo}")
            return ciclo

        if not alvo_pos:
            alvo, qtd = aguardar_reaquisicao(hwnd, j, ax, ay, timeout=0.8)
            if alvo:
                ax, ay = alvo
                mobs_pre = max(1, qtd)
                print(f"  [LOCK] Mantendo alvo em ({ax},{ay})")
                continue
            print(f"  [KILL?] Alvo desapareceu apos ataque no ciclo {ciclo}")
            return ciclo

    print(f"  [MISS] Mob sobreviveu {MAX_CICLOS_ATAQUE} ciclos - pulando")
    if log: log.miss(ax, ay)
    return False

def _mapa_caminhavel(frame, incluir_personagem=True):
    global _walk_cache_key, _walk_cache_mask, _walk_cache_frame
    key = (id(frame), incluir_personagem)
    if _walk_cache_key == key and _walk_cache_frame is frame and _walk_cache_mask is not None:
        return _walk_cache_mask

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask_ui = _mascara_interface(frame)
    walk = ((gray > MAPA_LIMIAR_PAREDE) & (mask_ui > 0)).astype(np.uint8) * 255
    walk = cv2.morphologyEx(walk, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    walk = cv2.morphologyEx(walk, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    if incluir_personagem:
        h, w = walk.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.circle(walk, (cx, cy), 36, 255, -1)

    _walk_cache_key = key
    _walk_cache_mask = walk
    _walk_cache_frame = frame
    return walk

def _distancia_parede(walk):
    return cv2.distanceTransform((walk > 0).astype(np.uint8), cv2.DIST_L2, 5)

def _linha_caminhavel(walk, x0, y0, x1, y1):
    h, w = walk.shape[:2]
    dist = int(max(abs(x1 - x0), abs(y1 - y0)))
    if dist <= 0:
        return False, 0.0

    ok = 0
    total = 0
    for i in range(1, dist + 1, 6):
        t = i / dist
        # Ignora os primeiros pixels porque o sprite do personagem fica no centro.
        if t < 0.10:
            continue
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        if 0 <= x < w and 0 <= y < h:
            total += 1
            if walk[y, x] > 0:
                ok += 1

    if total == 0:
        return False, 0.0
    pct = ok / total
    return pct >= 0.82, pct

def _criar_grid_caminhavel(walk, cell=MAPA_GRID):
    h, w = walk.shape[:2]
    gh = max(1, h // cell)
    gw = max(1, w // cell)
    resized = cv2.resize(walk, (gw, gh), interpolation=cv2.INTER_AREA)
    return resized > 170

def _astar_grid(grid, start, goal):
    gh, gw = grid.shape
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < gw and 0 <= sy < gh and 0 <= gx < gw and 0 <= gy < gh):
        return None
    if not grid[sy, sx] or not grid[gy, gx]:
        return None

    vizinhos = [(-1, 0, 10), (1, 0, 10), (0, -1, 10), (0, 1, 10),
                (-1, -1, 14), (1, -1, 14), (-1, 1, 14), (1, 1, 14)]
    aberto = []
    heapq.heappush(aberto, (0, (sx, sy)))
    veio_de = {}
    custo = {(sx, sy): 0}

    while aberto:
        _, atual = heapq.heappop(aberto)
        if atual == (gx, gy):
            caminho = [atual]
            while atual in veio_de:
                atual = veio_de[atual]
                caminho.append(atual)
            caminho.reverse()
            return caminho

        ax, ay = atual
        for dx, dy, peso in vizinhos:
            nx, ny = ax + dx, ay + dy
            if not (0 <= nx < gw and 0 <= ny < gh) or not grid[ny, nx]:
                continue
            novo = custo[atual] + peso
            if novo >= custo.get((nx, ny), 10**9):
                continue
            custo[(nx, ny)] = novo
            prioridade = novo + (abs(gx - nx) + abs(gy - ny)) * 10
            veio_de[(nx, ny)] = atual
            heapq.heappush(aberto, (prioridade, (nx, ny)))

    return None

def _grid_proximo_caminhavel(grid, gx, gy, max_raio=5):
    gh, gw = grid.shape
    if 0 <= gx < gw and 0 <= gy < gh and grid[gy, gx]:
        return gx, gy

    melhor = None
    for raio in range(1, max_raio + 1):
        for ny in range(max(0, gy - raio), min(gh, gy + raio + 1)):
            for nx in range(max(0, gx - raio), min(gw, gx + raio + 1)):
                if not grid[ny, nx]:
                    continue
                d2 = (nx - gx) ** 2 + (ny - gy) ** 2
                if melhor is None or d2 < melhor[0]:
                    melhor = (d2, nx, ny)
        if melhor is not None:
            return melhor[1], melhor[2]
    return None

def _caminho_grid_para_alvo(frame, j, tx, ty):
    h, w = frame.shape[:2]
    rx, ry = int(tx - j.left), int(ty - j.top)
    if not (0 <= rx < w and 0 <= ry < h):
        return None

    walk = _mapa_caminhavel(frame, incluir_personagem=True)
    grid = _criar_grid_caminhavel(walk)
    cx, cy = w // 2, h // 2
    start = (min(grid.shape[1] - 1, max(0, cx // MAPA_GRID)),
             min(grid.shape[0] - 1, max(0, cy // MAPA_GRID)))
    goal_raw = (min(grid.shape[1] - 1, max(0, rx // MAPA_GRID)),
                min(grid.shape[0] - 1, max(0, ry // MAPA_GRID)))

    if not grid[start[1], start[0]]:
        grid[start[1], start[0]] = True
    goal = _grid_proximo_caminhavel(grid, goal_raw[0], goal_raw[1])
    if goal is None:
        return None

    caminho = _astar_grid(grid, start, goal)
    if not caminho:
        return None
    return walk, caminho, start, goal

def _alvo_tem_caminho(frame, j, tx, ty):
    plano = _caminho_grid_para_alvo(frame, j, tx, ty)
    if plano is None:
        return False

    walk, caminho, _, _ = plano
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    rx, ry = int(tx - j.left), int(ty - j.top)
    _, linha_pct = _linha_caminhavel(walk, cx, cy, rx, ry)
    if linha_pct >= LOS_MIN_PCT:
        return True

    linear = max(1.0, ((rx - cx) ** 2 + (ry - cy) ** 2) ** 0.5)
    caminho_px = max(1, len(caminho) - 1) * MAPA_GRID
    return caminho_px <= linear * CAMINHO_ALVO_MAX_ALONGAMENTO

def _waypoint_para_alvo(frame, j, tx, ty, dist):
    plano = _caminho_grid_para_alvo(frame, j, tx, ty)
    if plano is None:
        return None

    _, caminho, _, _ = plano
    if len(caminho) <= 1:
        return tx, ty

    passos = min(len(caminho) - 1, max(2, min(COMBATE_WAYPOINT_CELLS, int(dist / MAPA_GRID * 0.55))))
    wx, wy = caminho[passos]
    px = int(wx * MAPA_GRID + MAPA_GRID / 2)
    py = int(wy * MAPA_GRID + MAPA_GRID / 2)
    return j.left + px, j.top + py

def _planejar_exploracao_visual(j, frame, sem_mob=0):
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    # Usa mapa estabilizado (media de frames) para ignorar efeitos visuais temporarios
    walk = _mapa_caminhavel_estavel(frame, incluir_personagem=True)
    dist_wall = _distancia_parede(walk)
    grid = _criar_grid_caminhavel(walk)
    start = (min(grid.shape[1] - 1, max(0, cx // MAPA_GRID)),
             min(grid.shape[0] - 1, max(0, cy // MAPA_GRID)))
    if not grid[start[1], start[0]]:
        grid[start[1], start[0]] = True

    tx_min = int(w * 0.08)
    tx_max = int(w * EXPLORAR_X_MAX)
    ty_min = int(h * 0.12)
    ty_max = int(h * 0.82)
    raio_min, raio_max = (300, 620) if sem_mob > 20 else (170, 430)
    heading = _explore_heading_get()

    candidatos = []
    candidatos_visitados = []
    for ang in np.linspace(0, 2 * np.pi, 32, endpoint=False):
        for raio in (raio_min, (raio_min + raio_max) // 2, raio_max):
            jitter = random.uniform(-0.22, 0.22)
            x = int(cx + np.cos(ang + jitter) * raio)
            y = int(cy + np.sin(ang + jitter) * raio * 0.62)
            x = max(tx_min, min(tx_max, x))
            y = max(ty_min, min(ty_max, y))
            if not (0 <= x < w and 0 <= y < h):
                continue
            if walk[y, x] == 0 or dist_wall[y, x] < MAPA_CLEARANCE_MIN:
                continue
            visitado = _hist_check(j.left + x, j.top + y)
            hist_penalty = 420 if visitado else 0
            linha_ok, linha_pct = _linha_caminhavel(walk, cx, cy, x, y)
            gx = min(grid.shape[1] - 1, max(0, x // MAPA_GRID))
            gy = min(grid.shape[0] - 1, max(0, y // MAPA_GRID))
            caminho = _astar_grid(grid, start, (gx, gy))
            if not caminho:
                continue

            dist_centro = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            score = dist_wall[y, x] * 5 + dist_centro * 0.18 + linha_pct * 120
            if linha_ok:
                score += 80
            if heading is not None and sem_mob >= 3:
                cand_ang = float(np.arctan2(y - cy, x - cx))
                diff = _angle_diff(cand_ang, heading)
                if sem_mob < 24 and diff > (np.pi * 0.72):
                    continue
                score += max(0.0, 1.0 - diff / np.pi) * EXPLORAR_HEADING_BONUS
                if diff > (np.pi * 0.50):
                    score -= EXPLORAR_HEADING_BONUS * 0.75
            score -= hist_penalty
            score += random.random() * 20
            destino = (score, x, y, caminho, linha_ok)
            if visitado:
                candidatos_visitados.append(destino)
            else:
                candidatos.append(destino)

    if not candidatos:
        candidatos = candidatos_visitados
    if not candidatos:
        return None

    candidatos.sort(key=lambda item: item[0], reverse=True)
    top_n = 2 if heading is not None else 4
    escolha_top = candidatos[:min(top_n, len(candidatos))]
    _, x, y, caminho, linha_ok = random.choice(escolha_top)
    _explore_heading_set(cx, cy, x, y)
    if linha_ok:
        return j.left + x, j.top + y, True

    passos = MAPA_WAYPOINT_LONGO if sem_mob > 20 else MAPA_WAYPOINT_CURTO
    wx, wy = caminho[min(len(caminho) - 1, passos)]
    px = int(wx * MAPA_GRID + MAPA_GRID / 2)
    py = int(wy * MAPA_GRID + MAPA_GRID / 2)
    px = max(tx_min, min(tx_max, px))
    py = max(ty_min, min(ty_max, py))
    return j.left + px, j.top + py, True

def _pixel_caminhavel(frame, j, tx, ty, limiar=22):
    """
    Retorna True se a area ao redor do alvo e majoritariamente caminhavel.
    Usa raio de 25px e exige 55% de pixels nao-parede (brilho > limiar).
    Borda de plataforma tem muito preto ao redor -> reprovado.
    Centro de area aberta tem pouco preto -> aprovado.
    """
    rx, ry = tx - j.left, ty - j.top
    h, w = frame.shape[:2]
    if not (0 <= rx < w and 0 <= ry < h):
        return False
    raio = 25
    x0, y0 = max(0, rx - raio), max(0, ry - raio)
    x1, y1 = min(w, rx + raio + 1), min(h, ry + raio + 1)
    walk = _mapa_caminhavel(frame, incluir_personagem=True)
    patch = walk[y0:y1, x0:x1]
    if patch.size == 0:
        return False
    pct = float(np.mean(patch > 0))
    return pct > 0.55  # exige pelo menos 55% de area caminhavel ao redor

def detectar_hp_bar_mob(frame, j, mx, my):
    """
    Busca a barra de HP colorida acima do sprite do mob.
    Retorna float 0.0-1.0 (proporcao verde = HP restante) ou None se nao achou.
    Util para priorizar alvos com pouco HP e confirmar se mob esta vivo.
    """
    if not HP_BAR_MOB_ATIVO:
        return None
    rx, ry = mx - j.left, my - j.top
    h, w = frame.shape[:2]
    y0 = max(0, ry - HP_BAR_MOB_Y_BUSCA)
    y1 = max(0, ry - 8)
    x0 = max(0, rx - 50)
    x1 = min(w, rx + 50)
    if y0 >= y1 or x0 >= x1:
        return None
    roi_hp = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi_hp, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    # Pixels que sao cor de barra de HP: verde/amarelo ou vermelho, alta saturacao
    barra = (sat > 100) & (val > 80) & (
        ((hue >= 35) & (hue <= 85)) |   # verde / amarelo-verde
        (hue <= 12) | (hue >= 160)       # vermelho
    )
    for row in range(barra.shape[0]):
        pix = int(np.sum(barra[row]))
        if pix >= HP_BAR_MOB_PIX_MIN:
            linha_hue = hue[row][barra[row]]
            if len(linha_hue) == 0:
                continue
            verdes = int(np.sum((linha_hue >= 35) & (linha_hue <= 85)))
            return float(verdes) / len(linha_hue)
    return None


def _mapa_caminhavel_estavel(frame, incluir_personagem=True):
    """
    Media dos ultimos WALK_HIST_N frames do mapa caminhavel.
    Reduz ruido de animacoes de skill/mob que pintam pixels no chao
    e causam falsos 'bloqueado' no planejamento de rota.
    """
    global _walk_hist
    atual = _mapa_caminhavel(frame, incluir_personagem)
    _walk_hist.append(atual.astype(np.float32))
    if len(_walk_hist) > WALK_HIST_N:
        _walk_hist.pop(0)
    if len(_walk_hist) < 3:
        return atual
    media = np.mean(np.stack(_walk_hist, axis=0), axis=0)
    return (media > 127).astype(np.uint8) * 255


def _hist_add(x, y):
    _hist_explore.append((x, y, time.time()))

def _hist_check(x, y):
    agora = time.time()
    _hist_explore[:] = [(hx, hy, ht) for hx, hy, ht in _hist_explore
                        if agora - ht < HIST_TEMPO]
    return any(abs(x - hx) < HIST_RAIO and abs(y - hy) < HIST_RAIO
               for hx, hy, ht in _hist_explore)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  LOG VISUAL â€” screenshots anotados + compilacao em video
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _angle_diff(a, b):
    return abs((a - b + np.pi) % (2 * np.pi) - np.pi)

def _explore_heading_get():
    if not EXPLORAR_HEADING_ATIVO or _explore_heading is None:
        return None
    ang, ts = _explore_heading
    if time.time() - ts > EXPLORAR_HEADING_TEMPO:
        return None
    return ang

def _explore_heading_set(cx, cy, x, y):
    global _explore_heading
    if EXPLORAR_HEADING_ATIVO:
        _explore_heading = (float(np.arctan2(y - cy, x - cx)), time.time())

def _explore_heading_reset():
    global _explore_heading
    _explore_heading = None

_vlog_pasta   = None   # pasta da sessao atual (criada em vlog_iniciar)
_vlog_seq     = 0      # numero sequencial do proximo frame
_vlog_frames  = []     # lista de caminhos para compilar video no fim
_vlog_t0      = 0.0    # timestamp de inicio da sessao

# Cores por tipo de evento (BGR)
_VLOG_CORES = {
    "MOB":          (0,   200, 255),  # amarelo
    "MOVE":         (255, 180,   0),  # azul
    "SKILL":        (0,   255, 100),  # verde
    "KILL":         (0,   255,   0),  # verde vivo
    "LOOT":         (100, 255, 180),  # verde claro
    "PATH":         (0,    60, 255),  # vermelho
    "STUCK":        (0,    60, 255),  # vermelho
    "BLIND_ATTACK": (0,   140, 255),  # laranja
    "EXPLORE":      (180, 180, 180),  # cinza
    "DEFAULT":      (200, 200, 200),
}


def vlog_iniciar(ts_sessao):
    """Cria a pasta da sessao e inicializa o modulo de log visual."""
    global _vlog_pasta, _vlog_seq, _vlog_frames, _vlog_t0
    if not VISUAL_LOG_ATIVO:
        return
    _vlog_pasta  = os.path.join(VISUAL_LOG_PASTA, ts_sessao)
    _vlog_seq    = 0
    _vlog_frames = []
    _vlog_t0     = time.time()
    os.makedirs(_vlog_pasta, exist_ok=True)
    print(f"  [VLOG] Pasta: {_vlog_pasta}")


def vlog_frame(frame, j, evento, info=None,
               mob_x=None, mob_y=None, estado_nome="",
               waypoint_xy=None, outros_mobs=None):
    """
    Salva um screenshot anotado.
    frame    : imagem BGR capturada do jogo
    evento   : string do tipo de evento ("MOB", "KILL", etc.)
    info     : texto extra para mostrar (distancia, ciclo, etc.)
    mob_x/y  : coordenadas absolutas do alvo (desenha marcador)
    estado_nome: nome do estado atual da maquina
    """
    global _vlog_seq
    if not VISUAL_LOG_ATIVO or _vlog_pasta is None:
        return
    if evento not in VISUAL_LOG_EVENTOS:
        return

    vis  = frame.copy()
    cor  = _VLOG_CORES.get(evento, _VLOG_CORES["DEFAULT"])
    h, w = vis.shape[:2]
    t_rel = round(time.time() - _vlog_t0, 2)

    # --- Marcador no alvo ---
    if mob_x is not None and mob_y is not None:
        rx = int(mob_x - j.left)
        ry = int(mob_y - j.top)
        if 0 <= rx < w and 0 <= ry < h:
            cv2.circle(vis, (rx, ry), 28, cor, 3)
            cv2.circle(vis, (rx, ry),  5, cor, -1)
            cv2.line(vis, (rx - 35, ry), (rx + 35, ry), cor, 1)
            cv2.line(vis, (rx, ry - 35), (rx, ry + 35), cor, 1)

    # --- Personagem no centro ---
    cx, cy = w // 2, h // 2
    cv2.circle(vis, (cx, cy), 12, (255, 255, 255), 2)

    # --- Linha personagem -> alvo ---
    if mob_x is not None and mob_y is not None:
        rx = int(mob_x - j.left)
        ry = int(mob_y - j.top)
        if 0 <= rx < w and 0 <= ry < h:
            cv2.line(vis, (cx, cy), (rx, ry), cor, 1, cv2.LINE_AA)

    # --- Waypoint (onde o bot clica para caminhar) ---
    if waypoint_xy is not None:
        wx = int(waypoint_xy[0] - j.left)
        wy = int(waypoint_xy[1] - j.top)
        if 0 <= wx < w and 0 <= wy < h:
            cv2.drawMarker(vis, (wx, wy), (0, 255, 255),
                           cv2.MARKER_DIAMOND, 18, 2)
            cv2.line(vis, (wx-10, wy), (wx+10, wy), (0,255,255), 1)
            cv2.line(vis, (wx, wy-10), (wx, wy+10), (0,255,255), 1)

    # --- Mobs ignorados (cinza) ---
    if outros_mobs:
        for omx, omy in outros_mobs[:6]:  # maximo 6
            orx = int(omx - j.left)
            ory = int(omy - j.top)
            if 0 <= orx < w and 0 <= ory < h:
                cv2.circle(vis, (orx, ory), 14, (120, 120, 120), 1)

    # --- HUD de informacoes ---
    linhas = [
        f"t={t_rel:.2f}s   [{evento}]",
        f"Estado: {estado_nome}",
    ]
    if mob_x is not None:
        dist = ((mob_x - (j.left + w//2))**2 + (mob_y - (j.top + h//2))**2)**0.5
        linhas.append(f"Alvo: ({int(mob_x)},{int(mob_y)})  dist={dist:.0f}px")
    if info:
        linhas.append(str(info))

    # Fundo semi-transparente para o HUD
    overlay = vis.copy()
    hud_h   = len(linhas) * 22 + 14
    cv2.rectangle(overlay, (6, 6), (440, 6 + hud_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, vis, 0.45, 0, vis)

    # Texto
    for i, linha in enumerate(linhas):
        y_txt = 26 + i * 22
        cv2.putText(vis, linha, (12, y_txt),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, cor, 1, cv2.LINE_AA)

    # Borda colorida fina ao redor da imagem
    cv2.rectangle(vis, (0, 0), (w - 1, h - 1), cor, 3)

    # --- Salvar ---
    nome = os.path.join(_vlog_pasta,
                        f"{_vlog_seq:05d}_{evento}.jpg")
    cv2.imwrite(nome, vis, [cv2.IMWRITE_JPEG_QUALITY, 82])
    _vlog_frames.append(nome)
    _vlog_seq += 1


def vlog_finalizar():
    """
    Chamado no fim da sessao.
    Compila todos os screenshots em um video MP4 se VISUAL_LOG_VIDEO=True.
    """
    if not VISUAL_LOG_ATIVO or not _vlog_frames:
        return
    print(f"  [VLOG] {len(_vlog_frames)} frames salvos em {_vlog_pasta}")
    if not VISUAL_LOG_VIDEO:
        return
    try:
        amostra = cv2.imread(_vlog_frames[0])
        if amostra is None:
            return
        h, w = amostra.shape[:2]
        ts   = os.path.basename(_vlog_pasta)
        arq  = os.path.join(VISUAL_LOG_PASTA, f"ro_video_{ts}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(arq, fourcc, VISUAL_LOG_FPS, (w, h))
        for caminho in _vlog_frames:
            img = cv2.imread(caminho)
            if img is not None:
                writer.write(img)
        writer.release()
        print(f"  [VLOG] Video salvo: {arq}")
    except Exception as e:
        print(f"  [VLOG] Erro ao gerar video: {e}")


def _scan_extrair_mobs(results, frame, j):
    """Extrai posicoes (mx, my) dos resultados YOLO para o worker de scan."""
    if not results:
        return []
    result = results[0]
    names  = getattr(result, "names", {}) or {}
    boxes  = getattr(result, "boxes", None)
    if boxes is None:
        return []
    mobs   = []
    cx_c   = (j.left + j.right) // 2
    cy_c   = (j.top  + j.bottom) // 2
    for box in boxes:
        try:
            cls_id = int(box.cls[0].item())
            label  = str(names.get(cls_id, cls_id)).lower()
            if YOLO_CLASSES_MOB and label not in YOLO_CLASSES_MOB and cls_id != 0:
                continue
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        except Exception:
            continue
        mx = int(j.left + (x1 + x2) / 2)
        my = int(j.top  + y1 + (y2 - y1) * YOLO_TARGET_Y_RATIO)
        if _blacklist_check(mx, my):
            continue
        if _perto_do_mouse(mx, my):
            continue
        if not _pixel_caminhavel(frame, j, mx, my):
            continue
        if LOS_MOB_ATIVO and not alvo_com_los(frame, j, mx, my):
            continue
        if any((mx-ox)**2+(my-oy)**2 < TEMPLATE_NMS_RAIO**2 for ox, oy in mobs):
            continue
        mobs.append((mx, my))
    mobs.sort(key=lambda p: (p[0]-cx_c)**2 + (p[1]-cy_c)**2)
    return mobs


def _scan_worker(hwnd, j):
    """
    Thread dedicada de deteccao rapida.
    Roda YOLO a SCAN_IMGSZ em loop; deposita (frame, mobs) na _scan_queue.
    Main loop consome quando disponivel â€” sem esperar inferencia.
    """
    global _scan_model
    if not SCAN_ASYNC_ATIVO or not USAR_YOLO:
        return
    try:
        from ultralytics import YOLO as _YOLO
        _scan_model = _YOLO(YOLO_MODEL_PATH)
    except Exception as e:
        print(f"  [SCAN] Falha ao carregar modelo de scan: {e}")
        return
    print(f"  [SCAN] Worker iniciado ({SCAN_IMGSZ}px ~{1/SCAN_INTERVALO:.0f}fps)")
    while rodando:
        try:
            frame   = capturar_cv(hwnd, j)
            roi     = _mascara_roi(frame)
            results = _scan_model.predict(
                source=roi, conf=SCAN_CONF,
                imgsz=SCAN_IMGSZ, verbose=False,
            )
            mobs = _scan_extrair_mobs(results, frame, j)
            # Descarta resultado antigo se fila cheia, mantÃ©m sempre o mais fresco
            if _scan_queue.full():
                try: _scan_queue.get_nowait()
                except Exception: pass
            _scan_queue.put_nowait((frame, mobs))
        except Exception:
            pass
        time.sleep(SCAN_INTERVALO)


def scan_pegar():
    """
    Retorna (frame, mobs) do ultimo scan assincrono, ou None se indisponivel.
    Chamada nao-bloqueante â€” nao atrasa o loop principal.
    """
    try:
        return _scan_queue.get_nowait()
    except Exception:
        return None


def _esperar_mob_range(hwnd, j, duracao_s, ax_ref, ay_ref, tid_ref=None):
    """
    Substitui time.sleep() passivo por polling ativo a cada 100ms.
    Se o alvo entrar em COMBATE_RANGE_PX durante a espera, retorna True
    imediatamente â€” o personagem pode entrar em ATACAR sem esperar o fim
    do settle completo.
    """
    fim = time.time() + duracao_s
    while time.time() < fim and rodando:
        time.sleep(min(0.10, max(0.01, fim - time.time())))
        # Tenta usar scan assincrono primeiro (zero custo de inferencia)
        scan = scan_pegar()
        if scan:
            frame_tmp, mobs_tmp = scan
        else:
            frame_tmp = capturar_cv(hwnd, j)
            mobs_tmp  = detectar_mobs(frame_tmp, j)
        novo = _rastrear_alvo(mobs_tmp, ax_ref, ay_ref, tid_ref)
        if novo:
            dist = distancia_do_personagem(j, novo[0], novo[1])
            if dist <= COMBATE_RANGE_PX:
                return True
    return False


def explorar(j, frame=None, sem_mob=0):
    cx = (j.left + j.right)  // 2
    cy = (j.top  + j.bottom) // 2
    ww = j.right - j.left
    hh = j.bottom - j.top

    if USAR_MAPA_VISUAL and frame is not None:
        plano = _planejar_exploracao_visual(j, frame, sem_mob)
        if plano is not None:
            tx, ty, ok = plano
            _hist_add(tx, ty)
            passo_estereo(j, tx, ty)
            return tx, ty, ok

    # Limites de exploracao (evita painel de quests e bordas)
    tx_min = j.left + int(ww * 0.08)
    tx_max = j.left + int(ww * EXPLORAR_X_MAX)
    ty_min = j.top  + int(hh * 0.12)
    ty_max = j.bottom - int(hh * 0.15)

    # Passo maior quando ha muito tempo sem mob (sai da area atual)
    if sem_mob > 20:
        dx_range = (350, 600)
        dy_range = (180, 350)
    else:
        dx_range = (200, 400)
        dy_range = (100, 220)

    # Tenta ate 12 direcoes â€” prioriza pixel caminhavel e posicao nao visitada
    tx, ty, ok = cx, cy, False
    heading = _explore_heading_get()
    for tentativa in range(12):
        if heading is not None and sem_mob >= 3:
            ang = heading + random.uniform(-0.38, 0.38)
            dx = int(np.cos(ang) * random.randint(*dx_range))
            dy = int(np.sin(ang) * random.randint(*dy_range))
        else:
            dx = random.choice([-1, 1]) * random.randint(*dx_range)
            dy = random.choice([-1, 1]) * random.randint(*dy_range)
        tx = max(tx_min, min(tx_max, cx + dx))
        ty = max(ty_min, min(ty_max, cy + dy))
        ok = (frame is None) or _pixel_caminhavel(frame, j, tx, ty)
        nao_visitado = not _hist_check(tx, ty)
        if ok and nao_visitado:
            break
        if ok and tentativa >= 8:
            break   # aceita posicao visitada se nao ha alternativa

    _hist_add(tx, ty)
    _explore_heading_set(cx, cy, tx, ty)
    passo_estereo(j, tx, ty)
    return tx, ty, ok

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MODO CAPTURAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def modo_capturar(hwnd, j):
    print()
    print("=" * 56)
    print("  CAPTURAR TEMPLATES")
    print("  Mova o mouse em cima do mob -> S para salvar")
    print("  Repita para mobs diferentes -> Q para sair")
    print("=" * 56)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    total = 0

    while True:
        frame = capturar_cv(hwnd, j)
        mx, my = win32api.GetCursorPos()
        rx, ry = mx - j.left, my - j.top
        vis = frame.copy()

        if 0 <= rx < frame.shape[1] and 0 <= ry < frame.shape[0]:
            x0 = max(0, rx-TEMPLATE_RAIO); y0 = max(0, ry-TEMPLATE_RAIO)
            x1 = min(frame.shape[1], rx+TEMPLATE_RAIO)
            y1 = min(frame.shape[0], ry+TEMPLATE_RAIO)
            cv2.rectangle(vis, (x0,y0), (x1,y1), (0,255,255), 2)
            cv2.circle(vis, (rx,ry), 4, (0,0,255), -1)

        cv2.putText(vis, f"[S]=salvar  [Q]=sair  ({total} salvos)",
                    (8,22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 1)
        cv2.imshow("Capturar Template", vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s") and 0 <= rx < frame.shape[1] and 0 <= ry < frame.shape[0]:
            x0 = max(0, rx-TEMPLATE_RAIO); y0 = max(0, ry-TEMPLATE_RAIO)
            x1 = min(frame.shape[1], rx+TEMPLATE_RAIO)
            y1 = min(frame.shape[0], ry+TEMPLATE_RAIO)
            crop = frame[y0:y1, x0:x1]
            nome = proximo_nome_template()
            cv2.imwrite(nome, crop)
            total += 1
            print(f"  [OK] {nome}  ({x1-x0}x{y1-y0}px)  [{total} total]")
            cv2.imshow(f"Salvo: {os.path.basename(nome)}", crop)
            cv2.waitKey(600)

    cv2.destroyAllWindows()
    print(f"\n  {total} template(s) em '{TEMPLATES_DIR}/'")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  MODO VERIFICAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def modo_dataset(hwnd, j):
    pasta = os.path.join("datasets", "ro_mob", "images", "raw")
    os.makedirs(pasta, exist_ok=True)
    auto = False
    ultimo_auto = 0.0
    total = len(glob.glob(os.path.join(pasta, "*.png")))

    print()
    print("=" * 56)
    print("  CAPTURAR DATASET YOLO")
    print("  S = salvar frame  |  A = auto on/off  |  Q = sair")
    print(f"  Pasta: {pasta}")
    print("=" * 56)

    while True:
        frame = capturar_cv(hwnd, j)
        vis = frame.copy()
        status = "AUTO" if auto else "MANUAL"
        cv2.putText(vis, f"[S]=salvar  [A]=auto  [Q]=sair  {status}  ({total} frames)",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
        cv2.imshow("Dataset YOLO", vis)

        agora = time.time()
        if auto and agora - ultimo_auto >= 1.0:
            nome = os.path.join(pasta, datetime.now().strftime("frame_%Y%m%d_%H%M%S_%f.png"))
            cv2.imwrite(nome, frame)
            total += 1
            ultimo_auto = agora
            print(f"  [DATASET] {nome}")

        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            break
        if key == ord("a"):
            auto = not auto
            print(f"  [DATASET] Auto {'ON' if auto else 'OFF'}")
        if key == ord("s"):
            nome = os.path.join(pasta, datetime.now().strftime("frame_%Y%m%d_%H%M%S_%f.png"))
            cv2.imwrite(nome, frame)
            total += 1
            print(f"  [DATASET] {nome}")

    cv2.destroyAllWindows()
    print(f"\n  {total} frame(s) em '{pasta}'")

def modo_verificar(hwnd, j):
    carregar_templates()
    carregar_yolo()
    print("[VERIFICAR] Q=sair  |  mostra template+score em cada deteccao")
    nome_janela = "Verificar (azul=mascara  vermelho=mob  Q=sair)"
    while True:
        frame  = capturar_cv(hwnd, j)
        # Usa com_info=True para mostrar nome e score de cada deteccao
        mobs_info = detectar_por_yolo(frame, j, com_info=True)
        if not mobs_info:
            mobs_info = detectar_por_template(frame, j, com_info=True)
        if not mobs_info and USAR_DETECTOR_MOVIMENTO:
            mobs_info = detectar_por_movimento(frame, j, com_info=True)
        if not mobs_info and USAR_DETECTOR_SPRITE:
            mobs_info = detectar_por_sprite(frame, j, com_info=True)
        # Tambem roda contraste se nao houver templates
        if not mobs_info and USAR_CONTRASTE:
            mobs_raw  = detectar_por_contraste(frame, j)
            mobs_info = [(mx, my, "CONTRASTE", 0.0) for mx, my in mobs_raw]

        vis = frame.copy()
        # Desenha a area mascarada em azul escuro para referencia
        roi_mask = _mascara_roi(frame)
        vis[roi_mask[:,:,0] == 0] = (20, 10, 0)   # areas mascaradas mais escuras

        for item in mobs_info:
            mx, my, nome, score = item
            rx, ry = mx - j.left, my - j.top
            cv2.circle(vis, (rx, ry), 22, (0, 0, 255), 2)
            cv2.circle(vis, (rx, ry),  5, (0, 255, 0), -1)
            label = f"{nome} {score:.2f}"
            cv2.putText(vis, label, (rx + 6, ry - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        # Mostra barras HP/SP lidas no frame
        hp_lido = _ler_barra(frame, HP_BAR_Y, HP_BAR_X0, HP_BAR_X1)
        sp_lido = _ler_barra(frame, SP_BAR_Y, SP_BAR_X0, SP_BAR_X1)
        h_f, w_f = frame.shape[:2]
        # Desenha linhas de referencia das barras
        y_hp = int(h_f * HP_BAR_Y); y_sp = int(h_f * SP_BAR_Y)
        x0   = int(w_f * HP_BAR_X0); x1 = int(w_f * HP_BAR_X1)
        cv2.line(vis, (x0, y_hp), (x1, y_hp), (0, 255, 0), 1)
        cv2.line(vis, (x0, y_sp), (x1, y_sp), (255, 150, 0), 1)

        # Overlay de caminhabilidade: vermelho=bloqueado, verde=chao provavel.
        walk = _mapa_caminhavel(frame, incluir_personagem=True)
        bloqueado = walk == 0
        livre = walk > 0
        vis[:, :, 2] = np.where(bloqueado, np.clip(vis[:, :, 2].astype(int) + 70, 0, 255), vis[:, :, 2]).astype(np.uint8)
        vis[:, :, 1] = np.where(livre, np.clip(vis[:, :, 1].astype(int) + 18, 0, 255), vis[:, :, 1]).astype(np.uint8)

        if USAR_MAPA_VISUAL:
            plano = _planejar_exploracao_visual(j, frame, sem_mob=0)
            if plano is not None:
                px, py, _ = plano
                rx, ry = px - j.left, py - j.top
                cv2.circle(vis, (rx, ry), 16, (255, 180, 0), 2)
                cv2.circle(vis, (rx, ry), 4, (255, 180, 0), -1)

        cv2.putText(vis, f"Detectados: {len(mobs_info)}  THRESHOLD={THRESHOLD}  Q=sair",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
        cv2.putText(vis, f"HP={hp_lido:.0%}  SP={sp_lido:.0%}  | vermelho=bloq  verde=chao  azul=prox passo",
                    (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.imshow(nome_janela, vis)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        try:
            import keyboard
            if keyboard.is_pressed("q") or keyboard.is_pressed("esc"):
                break
        except Exception:
            pass
        try:
            if cv2.getWindowProperty(nome_janela, cv2.WND_PROP_VISIBLE) < 1:
                break
        except Exception:
            break
    cv2.destroyAllWindows()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  LOOP PRINCIPAL
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def loop(hwnd, j):
    global rodando, _ultimo_refresh, _explore_until, _explore_dest
    global _alvo_lock, _alvo_lock_t   # mantidos por compatibilidade

    # â”€â”€ Variaveis de estado â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    estado    = Estado.BUSCAR
    alvo_pos  = None    # (ax, ay) do alvo atual
    alvo_tid  = None    # track_id YOLO do alvo (None se tracking off)
    alvo_t    = 0.0     # ultima vez que o alvo foi visto
    kill_pos  = None    # posicao do ultimo kill (para loot)
    ciclos    = 0       # ciclos de rotacao no alvo atual

    print()
    print("=" * 56)
    print("  RO BOT â€” Estado-machine + YOLO Tracking")
    print(f"  Janela    : {j.title}  ({j.width}x{j.height})")
    print(f"  Templates : {len(templates)}")
    print(f"  Mapa visual: {'ON' if USAR_MAPA_VISUAL else 'OFF'}")
    print(f"  Tracking  : {'ON' if USAR_YOLO_TRACKING else 'OFF'}")
    print(f"  Rotacao   : {' -> '.join(t for t,_ in ROTACAO)}")
    print(f"  Max ciclos: {MAX_CICLOS_ATAQUE}")
    print("-" * 56)
    print("  F12 = parar  |  mouse canto sup-esq = emergencia")
    print("=" * 56)
    print()
    print("  Iniciando em 3s â€” clique na janela do jogo...")
    time.sleep(3)
    focar(j)

    # Inicia thread de scan assincrono
    if SCAN_ASYNC_ATIVO and os.path.exists(YOLO_MODEL_PATH):
        threading.Thread(target=_scan_worker, args=(hwnd, j), daemon=True).start()

    # Inicia log visual
    ts_sessao = datetime.now().strftime("%Y%m%d_%H%M%S")
    vlog_iniciar(ts_sessao)

    inicio  = time.time()
    kills   = 0
    sem_mob = 0
    _ultimo_refresh = inicio

    while rodando:
        try:
            # Tenta usar frame pre-calculado pelo scan worker (zero-latencia)
            scan = scan_pegar()
            if scan:
                frame, _scan_mobs_cache = scan
            else:
                frame = capturar_cv(hwnd, j)
                _scan_mobs_cache = None

            # â•â• Checks globais (todos os estados) â•â•â•â•â•â•â•â•â•â•
            motivo_jail = antijail_verificar(frame)
            if motivo_jail:
                antijail_alertar(j, motivo_jail)
                break

            morto, tomou_dano = verificar_hp_sp(frame, j)
            if morto:
                rodando = False
                break

            if kills > 0 and kills % KILLS_AVISO_PESO == 0:
                print(f"  [PESO]  {kills} kills â€” verifique o peso!")

            if REFRESH_PERIODICO_S and (time.time() - _ultimo_refresh) > REFRESH_PERIODICO_S:
                forcar_refresh(j, "periodico_buscar")

            # Transiciona para RECUPERAR se recursos criticos
            hp_atual = _ler_barra(frame, HP_BAR_Y, HP_BAR_X0, HP_BAR_X1)
            sp_atual = _ler_barra(frame, SP_BAR_Y, SP_BAR_X0, SP_BAR_X1)
            if estado not in (Estado.RECUPERAR, Estado.LOOT):
                if hp_atual < HP_RECUPERAR_MIN or sp_atual < SP_RECUPERAR_MIN:
                    print(f"  [â†’RECUPERAR] HP={hp_atual:.0%} SP={sp_atual:.0%}")
                    estado   = Estado.RECUPERAR
                    alvo_pos = None
                    continue

            # â•â• ESTADO: BUSCAR â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            if estado == Estado.BUSCAR:
                sem_mob += 1

                # Ponto cego: dano sem mob visivel
                if tomou_dano:
                    if log: log._w("BLIND_ATTACK", {})
                    focar(j)
                    pyautogui.press(TECLA_TAB)
                    time.sleep(0.08)
                    for tecla, delay in ROTACAO:
                        if not rodando: break
                        pyautogui.press(tecla)
                        time.sleep(delay)
                    continue

                # Stuck check
                if sem_mob >= 8 and _verificar_stuck():
                    print("  [STUCK] Forcando salto longo...")
                    if log: log.stuck()
                    if REFRESH_APOS_STUCK:
                        forcar_refresh(j, "stuck")
                    _hist_explore.clear()
                    _explore_heading_reset()
                    tx, ty, ok = explorar(j, frame, sem_mob=30)
                    if log: log.explore(tx, ty, ok)
                    vlog_frame(frame, j, "EXPLORE",
                               info=f"stuck_jump ok={ok}",
                               estado_nome=estado.value, waypoint_xy=(tx, ty))
                    _explore_dest  = (tx, ty)
                    _explore_until = time.time() + EXPLORAR_SETTLE_LONGO_S
                    continue

                mobs = _scan_mobs_cache if _scan_mobs_cache is not None else detectar_mobs(frame, j)
                if mobs:
                    sem_mob = 0
                    _explore_until = 0.0
                    _explore_dest  = None
                    _explore_heading_reset()

                    # Prioriza mob com menor HP quando ha varios
                    ax, ay = mobs[0]
                    if len(mobs) > 1 and HP_BAR_MOB_ATIVO:
                        mobs_hp = []
                        for mx, my in mobs:
                            hp_pct = detectar_hp_bar_mob(frame, j, mx, my)
                            mobs_hp.append((hp_pct if hp_pct is not None else 1.0, mx, my))
                        mobs_hp.sort(key=lambda m: m[0])
                        ax, ay = mobs_hp[0][1], mobs_hp[0][2]
                        if mobs_hp[0][0] < 1.0:
                            print(f"  [HP-BAR] Alvo HP~{mobs_hp[0][0]:.0%} priorizado")

                    if not dentro_da_janela(j, ax, ay):
                        continue

                    alvo_pos = (ax, ay)
                    alvo_tid = _track_ids.get((ax, ay))
                    alvo_t   = time.time()
                    ciclos   = 0
                    if log: log.mob(ax, ay, len(mobs))

                    # Fast-path: mob ja em range \u2192 ATACAR direto, sem passar por APROXIMAR
                    dist_imediata = distancia_do_personagem(j, ax, ay)
                    vlog_frame(frame, j, "MOB",
                               info=f"qtd={len(mobs)} dist={dist_imediata:.0f}px",
                               mob_x=ax, mob_y=ay, estado_nome=estado.value)
                    if dist_imediata <= COMBATE_RANGE_PX:
                        print(f"  [BUSCAR\u2192ATACAR] ({ax},{ay}) ja em range ({dist_imediata:.0f}px) \u2014 ataque direto!")
                        parar_movimento(j)
                        estado = Estado.ATACAR
                    else:
                        print(f"  [BUSCAR\u2192APROXIMAR] ({ax},{ay}) dist={dist_imediata:.0f}px tid={alvo_tid}")
                        parar_movimento(j)
                        estado = Estado.APROXIMAR

                else:
                    if time.time() < _explore_until:
                        time.sleep(0.08)
                        continue
                    if sem_mob % 5 == 0:
                        if log: log.idle(sem_mob)
                        print(f"  [BUSCAR] Explorando ({sem_mob}x sem mob)...")
                    tx, ty, ok = explorar(j, frame, sem_mob)
                    if log: log.explore(tx, ty, ok)
                    vlog_frame(frame, j, "EXPLORE",
                               info=f"sem_mob={sem_mob} ok={ok}",
                               estado_nome=estado.value, waypoint_xy=(tx, ty))
                    _explore_dest  = (tx, ty)
                    _explore_until = time.time() + (EXPLORAR_SETTLE_LONGO_S if sem_mob > 20 else EXPLORAR_SETTLE_S)

            # â•â• ESTADO: APROXIMAR â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            elif estado == Estado.APROXIMAR:
                ax, ay = alvo_pos

                mobs = _scan_mobs_cache if _scan_mobs_cache is not None else detectar_mobs(frame, j)
                novo = _rastrear_alvo(mobs, ax, ay, alvo_tid)
                if novo:
                    ax, ay   = novo
                    alvo_pos = novo
                    alvo_tid = _track_ids.get(novo, alvo_tid)
                    alvo_t   = time.time()
                elif time.time() - alvo_t > (ALVO_GRACE_BASE + distancia_do_personagem(j, ax, ay) / 100 * ALVO_GRACE_POR_100PX):
                    grace_usada = ALVO_GRACE_BASE + distancia_do_personagem(j, ax, ay) / 100 * ALVO_GRACE_POR_100PX
                    print(f"  [APROXIMAR\u2192BUSCAR] Alvo perdido apos {grace_usada:.1f}s (dist-escalado)")
                    estado   = Estado.BUSCAR
                    alvo_pos = None
                    continue

                dist = distancia_do_personagem(j, ax, ay)

                # â”€â”€ Switch oportunista â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                # Se apareceu mob muito mais perto que o alvo atual,
                # troca imediatamente. Evita bot ir a 420px ignorando mob a 140px.
                if mobs and dist > COMBATE_RANGE_PX:
                    mx0, my0 = mobs[0]
                    dist0 = distancia_do_personagem(j, mx0, my0)
                    if (dist0 <= COMBATE_RANGE_PX or
                            (dist0 < dist * ALVO_SWITCH_RATIO and
                             dist - dist0 > ALVO_SWITCH_MIN_DIST)):
                        ax, ay   = mx0, my0
                        alvo_pos = (ax, ay)
                        alvo_tid = _track_ids.get((ax, ay), alvo_tid)
                        alvo_t   = time.time()
                        _aprox_watch_reset()
                        if dist0 <= COMBATE_RANGE_PX:
                            print(f"  [SWITCH\u2192ATACAR] Mob em range ({dist0:.0f}px)!")
                            estado = Estado.ATACAR
                            continue
                        print(f"  [SWITCH] Oportunista {dist0:.0f}px << {dist:.0f}px")
                        dist = dist0

                if dist <= COMBATE_RANGE_PX:
                    print(f"  [APROXIMAR\u2192ATACAR] Em range ({dist:.0f}px)")
                    _aprox_watch_reset()
                    estado = Estado.ATACAR
                    continue

                if _aprox_watch_update(ax, ay, dist):
                    print(f"  [APROXIMAR\u2192BUSCAR] Sem progresso; blacklist ({ax},{ay})")
                    _blacklist_add(ax, ay)
                    _aprox_watch_reset()
                    if log: log.path(ax, ay, "aprox_watch")
                    estado   = Estado.BUSCAR
                    alvo_pos = None
                    continue

                waypoint = None
                if COMBATE_USAR_WAYPOINT:
                    waypoint = _waypoint_para_alvo(frame, j, ax, ay, dist)
                if waypoint is None:
                    if COMBATE_USAR_WAYPOINT:
                        print(f"  [APROXIMAR\u2192BUSCAR] Sem caminho; blacklist ({ax},{ay})")
                        _blacklist_add(ax, ay)
                        if log: log.path(ax, ay, "sem_caminho")
                        _aprox_watch_reset()
                        estado   = Estado.BUSCAR
                        alvo_pos = None
                        continue
                    cx = (j.left + j.right) // 2
                    cy = (j.top  + j.bottom) // 2
                    waypoint = (int(cx + (ax - cx) * COMBATE_APROX_FATOR),
                                int(cy + (ay - cy) * COMBATE_APROX_FATOR))

                if log: log.move(ax, ay)
                _outros = [(mx,my) for mx,my in mobs if (mx,my) != (ax,ay)][:5]
                vlog_frame(frame, j, "MOVE",
                           info=f"dist={dist:.0f}px  wp=({waypoint[0]},{waypoint[1]})",
                           mob_x=ax, mob_y=ay, estado_nome=estado.value,
                           waypoint_xy=waypoint, outros_mobs=_outros)
                passo_estereo(j, waypoint[0], waypoint[1])
                _explore_until = max(_explore_until, time.time() + 0.85)
                # Scan reativo: acorda a cada 100ms durante a caminhada.
                # Se mob entrar em range antes do fim do settle, ataca imediatamente.
                if _esperar_mob_range(hwnd, j, COMBATE_MOVE_SETTLE_S, ax, ay, alvo_tid):
                    print(f"  [APROXIMARâ†’ATACAR] Mob entrou em range durante caminhada!")
                    _aprox_watch_reset()
                    estado = Estado.ATACAR

            # â•â• ESTADO: ATACAR â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            elif estado == Estado.ATACAR:
                ax, ay = alvo_pos

                dist = distancia_do_personagem(j, ax, ay)
                if dist > COMBATE_RANGE_PX:
                    print(f"  [ATACARâ†’APROXIMAR] Fora de range ({dist:.0f}px)")
                    _aprox_watch_reset()
                    estado = Estado.APROXIMAR
                    continue

                mobs_pre = detectar_mobs(frame, j)
                qtd_pre  = len(mobs_pre)

                if qtd_pre == 0:
                    novo_alvo, qtd = aguardar_reaquisicao(hwnd, j, ax, ay)
                    if novo_alvo:
                        ax, ay   = novo_alvo
                        alvo_pos = novo_alvo
                        alvo_t   = time.time()
                        qtd_pre  = max(1, qtd)
                    else:
                        if ciclos == 0:
                            print("  [ATACAR->BUSCAR] Alvo sumiu antes da primeira skill; sem kill")
                            if log: log.skip(ax, ay)
                            vlog_frame(frame, j, "PATH",
                                       info="alvo sumiu antes da primeira skill",
                                       mob_x=ax, mob_y=ay, estado_nome=estado.value)
                            alvo_pos = None
                            estado = Estado.BUSCAR
                            continue
                        print(f"  [ATACARâ†’LOOT] Mob sumiu â€” kill pre-animacao")
                        kills   += 1
                        kill_pos = (ax, ay)
                        if log: log.kill(ax, ay, ciclos)
                        vlog_frame(frame, j, "KILL",
                                   info=f"kill pre-anim ciclo={ciclos} total={kills}",
                                   mob_x=ax, mob_y=ay, estado_nome=estado.value)
                        print(f"  [KILL] #{kills}  ({int(time.time()-inicio)}s)")
                        ciclos    = 0
                        alvo_pos  = None
                        estado    = Estado.LOOT
                        continue

                novo = _rastrear_alvo(mobs_pre, ax, ay, alvo_tid)
                if novo:
                    ax, ay   = novo
                    alvo_pos = novo
                    alvo_tid = _track_ids.get(novo, alvo_tid)

                ciclos += 1
                if ciclos > MAX_CICLOS_ATAQUE:
                    print(f"  [ATACARâ†’BUSCAR] Miss â€” {MAX_CICLOS_ATAQUE} ciclos")
                    if log: log.miss(ax, ay)
                    vlog_frame(frame, j, "PATH",
                               info=f"MISS {ciclos} ciclos sem kill",
                               mob_x=ax, mob_y=ay, estado_nome=estado.value)
                    refreshed = REFRESH_APOS_MISS and forcar_refresh(j, "miss")
                    if not refreshed:
                        _blacklist_add(ax, ay)
                        print(f"  [BL] ({ax},{ay}) bloqueado por {BLACKLIST_TEMPO}s")
                    estado   = Estado.BUSCAR
                    alvo_pos = None
                    ciclos   = 0
                    continue

                vlog_frame(frame, j, "SKILL",
                           info=f"ciclo={ciclos}  dist={dist:.0f}px",
                           mob_x=ax, mob_y=ay, estado_nome=estado.value)
                rotacao_skills(j, ciclos, ax, ay)
                # Aguarda efeitos visuais de skill (cristais, explosoes) assentarem
                # antes de checar kill â€” evita YOLO ver particulas como mobs vivos.
                time.sleep(0.22)

                frame_pos = capturar_cv(hwnd, j)
                mobs_pos  = detectar_mobs(frame_pos, j)
                qtd_pos   = len(mobs_pos)
                alvo_vivo = _rastrear_alvo(mobs_pos, ax, ay, alvo_tid)

                if qtd_pos < qtd_pre or not alvo_vivo:
                    print(f"  [ATACARâ†’LOOT] Kill no ciclo {ciclos}!")
                    kills   += 1
                    kill_pos = (ax, ay)
                    if log: log.kill(ax, ay, ciclos)
                    vlog_frame(frame_pos, j, "KILL",
                               info=f"ciclo={ciclos}  total={kills}",
                               mob_x=ax, mob_y=ay, estado_nome=estado.value)
                    print(f"  [KILL] #{kills}  ({int(time.time()-inicio)}s)")
                    ciclos    = 0
                    alvo_pos  = None
                    estado    = Estado.LOOT
                else:
                    if alvo_vivo:
                        ax, ay   = alvo_vivo
                        alvo_pos = alvo_vivo
                        alvo_tid = _track_ids.get(alvo_vivo, alvo_tid)

            # â•â• ESTADO: LOOT â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            elif estado == Estado.LOOT:
                if kill_pos:
                    lotar_area(j, kill_pos[0], kill_pos[1])
                    if log: log.loot(kill_pos[0], kill_pos[1])
                    vlog_frame(frame, j, "LOOT",
                               mob_x=kill_pos[0], mob_y=kill_pos[1],
                               estado_nome=estado.value)
                    kill_pos = None
                estado = Estado.BUSCAR

            # â•â• ESTADO: RECUPERAR â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
            elif estado == Estado.RECUPERAR:
                hp = _ler_barra(frame, HP_BAR_Y, HP_BAR_X0, HP_BAR_X1)
                sp = _ler_barra(frame, SP_BAR_Y, SP_BAR_X0, SP_BAR_X1)
                if hp >= HP_RECUPERAR_MIN and sp >= SP_RECUPERAR_MIN:
                    print(f"  [RECUPERARâ†’BUSCAR] HP={hp:.0%} SP={sp:.0%} â€” retomando")
                    estado = Estado.BUSCAR
                else:
                    time.sleep(0.4)

        except pyautogui.FailSafeException:
            print("[STOP] Mouse no canto â€” encerrado.")
            rodando = False
        except Exception as e:
            print(f"[ERRO] {type(e).__name__}: {e}")
            time.sleep(0.5)

    t = int(time.time() - inicio)
    print(f"\n  Encerrado: {t//60}m {t%60}s  |  {kills} kills")
    if log: log.fim(kills, t)
    vlog_finalizar()


# â”€â”€ teclado â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def monitor():
    global rodando
    try:
        import keyboard
        while rodando:
            if keyboard.is_pressed("f12"):
                print("\n  [F12] Parando..."); rodando = False; break
            time.sleep(0.1)
    except Exception:
        pass

# â”€â”€ main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    j    = pegar_janela()
    hwnd = pegar_hwnd()
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.02
    j = preparar_janela(j)
    if not janela_valida(j):
        print(f"  [AVISO] Geometria da janela suspeita: {j.left},{j.top} {j.width}x{j.height}")
        print("  [AVISO] Deixe o jogo visivel e rode novamente se a captura falhar.")

    if "--capturar" in sys.argv:
        modo_capturar(hwnd, j)
    elif "--dataset" in sys.argv:
        modo_dataset(hwnd, j)
    elif "--verificar" in sys.argv:
        modo_verificar(hwnd, j)
    else:
        yolo_ok = carregar_yolo()
        templates_ok = carregar_templates()
        if not yolo_ok and not templates_ok and not USAR_DETECTOR_MOVIMENTO and not USAR_DETECTOR_SPRITE and not USAR_CONTRASTE:
            sys.exit(1)
        print(f"  [AUTO-POT] HP<{HP_MINIMO:.0%} -> {TECLA_POT_HP}  |  SP<{SP_MINIMO:.0%} -> {TECLA_POT_SP}")
        print(f"  [BARRAS]   HP_BAR_Y={HP_BAR_Y}  SP_BAR_Y={SP_BAR_Y}")
        print(f"  [DICA]     Use --verificar para ver as linhas HP/SP e calibrar")
        log = Logger(j)
        threading.Thread(target=monitor, daemon=True).start()
        try:
            loop(hwnd, j)
        except KeyboardInterrupt:
            rodando = False
            print("  Ctrl+C â€” encerrado.")
