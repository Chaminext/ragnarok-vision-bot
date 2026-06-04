# Ragnarok PyBot Vision Lab

Bot experimental para Ragnarok Online em Windows, focado em detecção visual de
mobs com YOLO/OpenCV, captura de tela da janela do jogo e automação de combate.

O projeto está em fase de laboratório. Ele já treina e roda modelos YOLO com GPU,
mas a navegação/rota ainda não está pronta para uso autônomo confiável. O bot pode
passar por mobs, andar em vai-e-volta e só atacar depois de reposicionar a câmera
ou o personagem. Esse é o principal ponto técnico em aberto.

## Objetivo

Construir um bot visual que:

- capture a janela do Ragnarok;
- detecte mobs na tela;
- use YOLO treinado com frames reais ou dataset sintético;
- evite UI, cursor, personagem, parede e falsos positivos;
- ataque mobs detectados;
- colete loot;
- use poções;
- gere logs para análise;
- futuramente reconheça o tipo/elemento do mob para trocar elemento/atalho.

## Status Atual

Funcional:

- Captura da janela via Win32/PrintWindow.
- Modo `--verificar` com overlay de detecção.
- Captura de dataset com `--dataset`.
- Treino YOLO via Ultralytics.
- Uso de GPU NVIDIA com PyTorch CUDA.
- Geração de dataset sintético usando spritesheets do Divine Pride.
- Perfis iniciais para:
  - `pay_dun04` / último piso da Caverna de Payon.
  - Cheffenia Hard.
- Rotulador simples com suporte multi-classe.
- Banco JSON com mobs, classe YOLO, elemento e elemento recomendado.

Experimental:

- Navegação visual por máscara de chão/parede.
- Planejamento local de waypoint.
- Switch futuro de elemento por mob.

Problemas conhecidos:

- Movimento ainda pode ficar em zig-zag.
- O bot pode passar por mobs antes de atacar.
- Em alguns casos ele detecta e mata só depois de ir e voltar.
- `dokebi` e `furious_dokebi` tiveram métricas mais fracas no primeiro treino sintético.
- Dataset sintético ajuda muito, mas não substitui validação em tela real.
- Não deve rodar sem supervisão.

## Estrutura

```text
ro_bot.py                  Bot principal: captura, detecção, combate, loot, HP/SP.
ro_yolo_train.py           Treinamento YOLO.
ro_synthetic_dataset.py    Geração de dataset sintético por sprites Divine Pride.
ro_label.py                Rotulador manual YOLO, com multi-classe.
ro_cheffenia_assist.py     Assistente para banco Cheffenia Hard.

data/
  payon_dun04_mobs.json        Perfil do último piso de Payon.
  cheffenia_hard_mobs.json     Perfil inicial Cheffenia Hard.

datasets/ro_mob/
  dataset.yaml
  payon_dun04_dataset.yaml
  cheffenia_hard_dataset.yaml

PAYON_DUN04_YOLO.md        Guia específico do teste Payon.
CHEFFENIA_ASSIST.md        Guia específico Cheffenia Hard.
requirements_yolo.txt      Dependências principais.
```

Arquivos grandes são ignorados pelo Git:

- `.venv311/`
- `models/`
- `runs/`
- `datasets/.../images`
- `datasets/.../labels`
- datasets sintéticos
- logs
- pesos `yolo*.pt`

## Requisitos

Windows.

Python recomendado:

```text
Python 3.11
```

Para GPU NVIDIA:

- Driver NVIDIA instalado.
- PyTorch com CUDA.
- GPU testada no projeto: NVIDIA GeForce RTX 3060 Ti.

## Instalação

Crie ambiente Python 3.11:

```powershell
cd C:\BOT
py -3.11 -m venv .venv311
.\.venv311\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements_yolo.txt
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

Teste CUDA:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Resultado esperado:

```text
True
NVIDIA GeForce ...
```

## Configuração Principal

No arquivo `ro_bot.py`, ajuste:

```python
JANELA      = "4th | Gepard Shield 3.0 (^-_-^)"
TECLA_PASSO = "f3"
TECLA_LOOT  = "z"
TECLA_TAB   = "tab"
ROTACAO = [
    ("f1", 0.4),
    ("f2", 0.4),
]
```

Também calibre HP/SP se necessário:

```python
HP_BAR_Y
HP_BAR_X0
HP_BAR_X1
SP_BAR_Y
SP_BAR_X0
SP_BAR_X1
```

Use `--verificar` para visualizar linhas e overlays.

## Modos do Bot

Verificação visual:

```powershell
python ro_bot.py --verificar
```

Captura de frames:

```powershell
python ro_bot.py --dataset
```

Execução do bot:

```powershell
python ro_bot.py
```

Usar modelo específico:

```powershell
$env:RO_YOLO_MODEL="models\payon_dun04_yolo.pt"
python ro_bot.py --verificar
```

## Teste Payon `pay_dun04`

Dataset sintético sem rotulagem manual:

```powershell
python ro_bot.py --dataset
python ro_synthetic_dataset.py --profile data/payon_dun04_mobs.json --out datasets/payon_dun04_synth --per-class 120 --negatives 60
python ro_yolo_train.py --data datasets/payon_dun04_synth/dataset.yaml --output models/payon_dun04_yolo.pt --epochs 60 --device 0
```

Testar modelo:

```powershell
$env:RO_YOLO_MODEL="models\payon_dun04_yolo.pt"
python ro_bot.py --verificar
```

Rodar bot somente depois de validar o overlay:

```powershell
$env:RO_YOLO_MODEL="models\payon_dun04_yolo.pt"
python ro_bot.py
```

Classes Payon:

```text
0 am_mut
1 archer_skeleton
2 furious_dokebi
3 cat_o_nine_tails
4 dokebi
5 greatest_general
6 horong
7 moonlight_flower
8 nine_tail
9 skeleton_general
```

Primeiro resultado sintético observado:

```text
all                 mAP50 0.858  mAP50-95 0.767
am_mut              mAP50 0.927
archer_skeleton     mAP50 0.969
furious_dokebi      mAP50 0.448
cat_o_nine_tails    mAP50 0.976
dokebi              mAP50 0.502
greatest_general    mAP50 0.951
horong              mAP50 0.932
moonlight_flower    mAP50 0.990
nine_tail           mAP50 0.995
skeleton_general    mAP50 0.895
```

Interpretação: bom para teste supervisionado, mas Dokebi precisa melhorar.

## Rotulagem Manual

Se o sintético falhar:

```powershell
python ro_label.py --data datasets/ro_mob/payon_dun04_dataset.yaml
```

Controles:

```text
0-9    seleciona classe
[ ]    classe anterior/proxima
mouse  desenha caixa
N      salva e próxima
D      remove última caixa
C      limpa caixas
P      volta
Q      sai
```

## Cheffenia Hard

Preparar/atualizar banco:

```powershell
python ro_cheffenia_assist.py --refresh --enrich --write-yaml --status
```

Arquivos:

```text
data/cheffenia_hard_mobs.json
datasets/ro_mob/cheffenia_hard_dataset.yaml
CHEFFENIA_ASSIST.md
```

Ainda não está ligado no bot. A ideia é fazer teste assistido antes de qualquer
switch automático de elemento.

## Próxima Prioridade Técnica

O problema atual não é mais só detecção. É coordenação entre:

```text
detecção -> escolha de alvo -> aproximação -> ataque -> validação de kill -> próxima rota
```

Melhorias necessárias:

- Travar alvo quando YOLO detecta mob, em vez de continuar explorando.
- Rechecar mobs imediatamente após cada passo.
- Reduzir exploração quando há mob perto.
- Criar estado explícito: `BUSCAR`, `APROXIMAR`, `ATACAR`, `LOOT`, `RECUPERAR`.
- Preferir alvo persistente por alguns frames.
- Usar blacklist só para miss real, não para detecção tardia.
- Melhorar navegação: parar de clicar em waypoints longos quando há mobs próximos.

Essa é a frente que deve ser resolvida antes de rodar autônomo por longos períodos.

## Aviso

Este projeto é experimental e deve ser usado apenas em ambiente controlado, com
supervisão. Automação em jogos pode violar regras de servidores e sistemas anti-cheat.
Revise riscos antes de usar.
