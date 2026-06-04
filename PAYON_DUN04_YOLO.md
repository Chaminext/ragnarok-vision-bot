# Teste YOLO - Caverna de Payon ultimo piso

Mapa alvo: `pay_dun04`.

Classes treinadas no primeiro teste:

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

Plantas ficam fora das classes por enquanto:

```text
red_plant
shining_plant
white_plant
```

Fluxo recomendado sem rotulagem manual:

```powershell
python ro_bot.py --dataset
python ro_synthetic_dataset.py --profile data/payon_dun04_mobs.json --out datasets/payon_dun04_synth --per-class 120 --negatives 60
python ro_yolo_train.py --data datasets/payon_dun04_synth/dataset.yaml --output models/payon_dun04_yolo.pt
$env:RO_YOLO_MODEL="models\payon_dun04_yolo.pt"
python ro_bot.py --verificar
```

O primeiro comando captura fundos reais do mapa. No `--dataset`, use `A` para
auto-captura ou `S` para salvar frames manualmente. Nao precisa desenhar caixas.

Fluxo manual, somente se o sintetico nao ficar bom:

```powershell
python ro_label.py --data datasets/ro_mob/payon_dun04_dataset.yaml
```

No rotulador manual:

```text
0-9    escolhe a classe
[ ]    classe anterior/proxima
mouse  desenha caixa
N      salva e vai para proxima imagem
D      remove ultima caixa
C      limpa imagem
Q      sai
```

Importante:

- O dataset sintetico usa spritesheets do Divine Pride e gera labels YOLO sozinho.
- Capture fundos dentro do `pay_dun04`; fundos de outro mapa reduzem a qualidade.
- Se o treino sintetico confundir sprite real, capture mais fundos e aumente `--per-class`.
- Plantas ficam como negativo por enquanto.
