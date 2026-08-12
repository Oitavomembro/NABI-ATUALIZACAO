# Configuração no Windows — NabiCode 2.5.0

## Requisitos

- Windows 10 ou 11 atualizado.
- Python 3.14.x de 64 bits.
- Acesso ao PyPI durante a instalação.

## Ambiente limpo

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

## Validação

```powershell
python -m compileall -q .
python -m pytest -q
python -m pytest -q -s stress_tests
python -m pytest -q -s benchmark_tests
python -m pytest -q -s soak_tests
python main.py --startup-smoke-test --smoke-output startup.txt
Get-Content startup.txt
```

O arquivo deve conter `2.5.0`.

## Execução

```powershell
$env:NABICODE_PROFILE = "TESTE"
python main.py
```

Para produção, use o pacote oficial e o perfil `PRODUCAO`. Nunca reutilize o diretório de dados do perfil de teste.

## Empacotamento preliminar

```powershell
.\GERAR_EXE_TESTE.bat
```

O EXE definitivo depende da validação manual no Windows e não faz parte da candidata automatizada.
