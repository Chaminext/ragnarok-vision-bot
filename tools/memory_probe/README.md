# Ragnarok Memory Probe

Probe isolado e read-only para testar se os offsets de memoria funcionam no client atual.

Ele nao integra com `ro_bot.py`, nao clica, nao ataca e nao cria overlay. A saida e JSON para validarmos:

- mapa atual;
- HP/SP do personagem;
- posicao world/screen do personagem;
- contagem de atores;
- lista de mobs com `gid`, `screen`, `world` e distancia.

## Teste rapido

Com o Ragnarok aberto:

```powershell
python tools\memory_probe\ro_memory_probe.py --pretty --include mobs
```

Ele tenta encontrar primeiro por nomes comuns de processo. Se nao achar, tenta pela janela `4th | Gepard`.

Ou:

```powershell
tools\memory_probe\run_probe.bat
```

## Watch em tempo real

```powershell
python tools\memory_probe\ro_memory_probe.py --include mobs --watch 0.25
```

## Ver tudo que o actor list retornar

```powershell
python tools\memory_probe\ro_memory_probe.py --pretty --include all
```

## Descobrir o nome real do processo

```powershell
python tools\memory_probe\ro_memory_probe.py --list-processes --pretty
```

Depois rode apontando pelo nome ou PID:

```powershell
python tools\memory_probe\ro_memory_probe.py --process NomeDoClient.exe --pretty
python tools\memory_probe\ro_memory_probe.py --pid 1234 --pretty
```

## Como saber se deu certo

Bom sinal:

```json
{
  "ok": true,
  "map": "pay_dun04",
  "player": {
    "hp_pct": 0.95,
    "sp_pct": 0.72,
    "screen": {"x": 968, "y": 516}
  },
  "counts": {"mob": 3},
  "actors": [
    {"type_name": "mob", "screen": {"x": 1100, "y": 450}, "distance": 8.2}
  ]
}
```

Sinais de offset errado:

- `manager` igual a `0x0`;
- `map` vazio ou com texto quebrado;
- HP/SP zerados ou absurdos;
- actor list vazia mesmo com mobs visiveis;
- coordenadas `screen` muito fora da tela.

## Observacao

Este probe usa `OpenProcess` com permissao de leitura (`PROCESS_VM_READ`) e `ReadProcessMemory`.
Em clients com anti-cheat, teste primeiro somente como diagnostico isolado.
