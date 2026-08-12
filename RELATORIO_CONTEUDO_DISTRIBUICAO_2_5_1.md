# RELATÓRIO DE CONTEÚDO DA DISTRIBUIÇÃO — NABICODE 2.5.1 DEV

## Estado da auditoria

O conteúdo do build Windows anterior não está materializado neste workspace.
Consequentemente, este documento registra a política corrigida e o resultado
esperado do próximo build, não uma aprovação física de um diretório inexistente.

O log informado para o build anterior confirma que PyInstaller concluiu EXE e
COLLECT e que a reprovação ocorreu na validação posterior. A confirmação física
do novo inventário deverá ser produzida pelo manifesto do pipeline no Windows.

## Layout obrigatório

```text
build_output/dist/NabiCode_v2_5_1/
    NabiCode_v2_5_1.exe
    _internal/
        VERSAO.txt                  # 2.5.1
        PERFIL_NABICODE.txt         # PRODUCAO
        certifi/cacert.pem          # bundle público autorizado
        ...runtime Python e dependências...
```

O wheelhouse e a `.build-venv` são ferramentas de build e não podem aparecer
dentro da distribuição ou do instalador.

## Conteúdo expressamente proibido

- `matplotlib/tests`, `matplotlib/testing` e quaisquer diretórios `test` ou
  `tests` de dependências;
- `pytest` e testes do projeto;
- `benchmark_tests`, `stress_tests` e `soak_tests`;
- `.venv`, `.build-venv`, wheelhouse, `__pycache__` e `.pytest_cache`;
- `.py`, `.pyw`, `.pyi` e `.pyc` soltos;
- bancos `.db`, `.sqlite` e `.sqlite3`;
- logs;
- `.pfx`, `.p12`, `.key` e qualquer `.pem` não autorizado.

## Exceção criptográfica específica

A única exceção para `.pem` é o caminho normalizado, sem wildcard:

`_internal/certifi/cacert.pem`

Ela não autoriza certificados de cliente, chaves privadas ou outros arquivos
PEM. O arquivo do Certifi contém autoridades certificadoras públicas usadas por
Requests para verificação TLS. Referência: <https://github.com/certifi/python-certifi>.

## Coleta de dependências

O `.spec` deixou de usar `collect_all()` indiscriminadamente. Os hooks oficiais
das versões travadas continuam responsáveis por recursos nativos e datas dos
pacotes suportados. Hidden imports explícitos cobrem os caminhos opcionais e
dinâmicos usados pelo NabiCode, incluindo:

- fiscal: Requests, Certifi, Cryptography e lxml;
- relatórios: ReportLab e OpenPyXL;
- dashboard: backend TkAgg e `matplotlib.figure`;
- imagens: Pillow/ImageTk;
- impressão Windows: `win32con`, `win32print`, `win32ui` e `pywintypes`.

## Evidências que o próximo pipeline deve gerar

- `build_output/manifest.json`: caminho, tamanho e SHA-256 de cada arquivo;
- `build_output/SHA256SUMS.txt`: hashes do onedir;
- `build_output/startup_packaged.json`: perfil PRODUCAO e conclusão do smoke;
- `build_output/smoke_version.txt`: versão 2.5.1;
- `build_output/installer/SHA256SUMS.txt`: hash do Setup.

## Resultado atual

| Item | Estado |
| --- | --- |
| política do validador | aprovada por testes |
| exceção Certifi | aprovada por teste positivo e negativos |
| remoção de `collect_all()` | concluída |
| exclusão de testes Matplotlib | configurada e testada estaticamente |
| inventário físico do novo onedir | pendente de rebuild Windows |
| manifesto final | pendente |
| hash final do instalador | pendente |
