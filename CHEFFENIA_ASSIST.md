# Cheffenia Hard - preparo assistido

Base criada para testar reconhecimento por MVP na Cheffenia Hard sem ligar isso
automaticamente no bot ainda.

Arquivos:

- `data/cheffenia_hard_mobs.json`: banco revisavel com 45 MVPs Hard, IDs,
  spritesheets, elemento, elemento recomendado e campo de atalho.
- `datasets/ro_mob/cheffenia_hard_dataset.yaml`: YAML de classes YOLO por MVP.
- `ro_cheffenia_assist.py`: atualiza/enriquece o banco a partir da wiki/Divine
  Pride e regera o YAML.

Comandos uteis:

```powershell
python ro_cheffenia_assist.py --status
python ro_cheffenia_assist.py --refresh --enrich --write-yaml --status
```

Fluxo rapido para teste supervisionado:

```powershell
cheffenia_prepare.bat
cheffenia_train.bat
cheffenia_verify.bat
cheffenia_run_supervised.bat
```

Arquivos gerados/local:

- `datasets/cheffenia_hard_synth/`: dataset sintetico com sprites Divine Pride.
- `models/cheffenia_hard_yolo.pt`: peso treinado para o teste.

Antes de rodar o bot em Cheffenia:

1. Entre no mapa e rode `cheffenia_verify.bat`.
2. Confirme que o overlay detecta MVPs e nao marca UI/personagem.
3. Fique 30-60s no verificador olhando falsos positivos.
4. So depois rode `cheffenia_run_supervised.bat`.

No primeiro teste, pare com F12 assim que notar:

- mob detectado atras de parede;
- personagem perseguindo alvo distante demais;
- muitos `SKIP` seguidos;
- pot HP/SP acionando tarde;
- cursor saindo para UI/quest list.

Antes de usar switch automatico, revisar no JSON:

- `recommended_attack_element`
- `switch_slots`
- `switch_key`
- `reviewed`

Fluxo futuro:

1. Revisar os 45 mobs e atalhos de elemento.
2. Gerar dataset sintetico com spritesheets + fundos reais da Cheffenia.
3. Treinar YOLO usando `cheffenia_hard_dataset.yaml`.
4. Testar em modo assistido mostrando classe detectada e elemento sugerido.
5. So depois ligar troca automatica no `ro_bot.py`.
