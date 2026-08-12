# Checkpoint 18 — Dependências e ambiente

- `requirements.txt` contém dependências oficiais e limites de versão.
- `cryptography` e `lxml` permanecem necessárias ao fluxo fiscal e foram preservadas.
- PyInstaller e pywin32 estão declarados para o ambiente Windows.
- Regressão garante que dependências críticas não desapareçam do manifesto.
- `SETUP_WINDOWS.md` documenta Python 3.14, venv, instalação, testes e execução.
- Python: 3.14.6.
- `pip check`: nenhuma dependência quebrada.
- Imports críticos: aprovados.
- Testes focados: 6 aprovados e 2 subtests aprovados.
- `python -m compileall -q .`: aprovado.
- Suíte normal: 902 testes aprovados e 11 subtests aprovados.
