# Correção do Runtime Profile / Second Instance Lock — NabiCode 2.4.97

## Evidência principal

O log capturado no Windows 10, Python 3.14.6 e pytest 9.1.1 registra:

- `collected 863 items`;
- interrupção recorrente após 665 testes, sempre ao entrar em
  `test_lock_blocks_second_instance_and_releases`;
- relatório interno do pytest com `outcome='passed'` para esse teste;
- `KeyboardInterrupt` somente durante
  `colorama.ansitowin32.StreamWrapper.flush()`, quando o pytest escrevia o
  progresso no console.

Isso demonstra que as asserções do teste terminam corretamente e que a
interrupção é entregue de forma assíncrona ao processo do pytest.

## Causa raiz

O teste `test_lock_blocks_second_instance_and_releases` não cria subprocesso e
não abre a GUI. As duas instâncias do lock são objetos no próprio processo do
pytest.

Ao detectar o arquivo de lock já existente, `DatabaseUsageLock._pid_alive()`
executava `os.kill(pid, 0)`. Essa técnica é uma sondagem válida em POSIX, mas o
valor `0` no Windows corresponde a `CTRL_C_EVENT`. Portanto, a chamada não era
uma consulta passiva: ela gerava um evento de console. Como o lock continha o
PID do próprio pytest e o processo compartilhava o console do CMD, o evento era
entregue ao pytest como `KeyboardInterrupt` logo após o teste ser marcado como
`PASSED`.

## Correção aplicada

- Windows agora consulta o processo com `OpenProcess` e `GetExitCodeProcess`.
- Nenhum sinal de console é enviado para verificar se o PID está ativo.
- O handle nativo é sempre fechado em `finally`.
- Falha de acesso é tratada conservadoramente como processo ativo, preservando
  a proteção contra duas instâncias.
- POSIX mantém `os.kill(pid, 0)`, com distinção entre PID inexistente e falta de
  permissão.
- O teste libera os dois locks obrigatoriamente em `finally`.
- O callback registrado em `atexit` é removido quando o lock é liberado.
- O próprio teste recebeu uma asserção de regressão que impede o retorno de
  `os.kill` no caminho Windows, sem alterar a contagem total de 863 testes.

## Subprocessos e isolamento de console

O teste corrigido não usa `subprocess.Popen`, `subprocess.run`, `terminate`,
`kill`, `wait`, `CTRL_C_EVENT`, `CTRL_BREAK_EVENT` nem inicia outra instância da
GUI. Portanto, não há subprocesso de segunda instância para isolar ou processo
filho para encerrar; `wait(timeout=...)`, `terminate`, `kill`,
`CREATE_NEW_PROCESS_GROUP` e `CREATE_NO_WINDOW` não se aplicam a este teste. O
lock continua sendo validado diretamente, sem abrir o NabiCode e sem possibilidade
de deixar instância órfã.

## Referências técnicas

- Python 3.14, `os.kill`: no Windows, `CTRL_C_EVENT` e `CTRL_BREAK_EVENT` são
  sinais de console especiais.
- Microsoft Win32, `OpenProcess`: abre um handle local sem enviar sinal.
- Microsoft Win32, `GetExitCodeProcess`: retorna `STILL_ACTIVE` enquanto o
  processo continua em execução.

## Arquivos modificados

- `core/runtime_profile.py`
- `tests/test_runtime_profile_isolation.py`
- `RELATORIO_CORRECAO_RUNTIME_PROFILE_LOCK_2_4_97.md`

## Validação executada

Teste isolado:

```text
python -m pytest -vv -s tests/test_runtime_profile_isolation.py::RuntimeProfileTests::test_lock_blocks_second_instance_and_releases --full-trace
1 passed in 0.45s
```

Suíte completa, com `APPDATA` temporário gravável exigido pelo sandbox Linux:

```text
python -m pytest -q
863 passed, 11 subtests passed in 19.18s
```

Resultados locais:

- 863 testes concluídos;
- zero falhas;
- zero `KeyboardInterrupt`;
- zero subprocessos iniciados pelo teste do lock;
- zero possibilidade de processo NabiCode órfão nesse teste.

A reprodução original é específica do Windows. A confirmação final da API
nativa e de `0 KeyboardInterrupt` deve ser feita no mesmo Windows 10/11 e
Python 3.14.6 usados para produzir o log.
