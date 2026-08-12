# Relatório técnico — auditoria noturna NabiCode 2.5.1 DEV

Data: 2026-08-08  
Base: `NabiCode_v2_5_1_DEV_CHECKPOINT_38_SPLASH_FIDELIDADE.zip`  
Estado: DEV; candidata de instalação offline; **não promovida para RELEASE**.

## Resultado executivo

A auditoria encontrou e corrigiu problemas estruturais seguros em shutdown, lock, atualização, fronteira de licença, integridade do wheelhouse e quatro exceções latentes na interface legada. Nenhuma regra comercial, financeira, de estoque, PDV ou impressão foi alterada.

Resultado final automatizado: `977 passed, 19 subtests passed`. O Checkpoint 38 tinha `959 passed, 18 subtests passed`; portanto nenhum teste desapareceu e foram acrescentados 18 testes e um subteste.

## Processos e shutdown

- O encerramento do helper da splash não pode mais interromper o bloco `finally` caso nem `terminate` nem `kill` sejam confirmados. O resultado é booleano, a falha é registrada como crítica e os demais recursos continuam sendo limpos.
- O `TaskManager` global é encerrado cooperativamente e de forma idempotente antes da liberação do `DatabaseLock`. Isso evita que tarefas não daemon mantenham uma instância sem janela depois que o banco pareça livre.
- Testes cobrem helper irrecuperável, ordem de cleanup, lock liberado, cancelamento de tarefas e soak de recursos.

## Startup

O encadeamento instrumentado permanece: imports → entrada de `main` → perfil → splash → import legado → caminho do banco → lock → criação da aplicação → migrations → construção da UI/dashboard → `MAIN_WINDOW_READY` → primeiro frame utilizável.

Medição local de `import nabicode_legacy` com `python -X importtime`: aproximadamente **260,419 ms**. Os agregados mais pesados foram `core` (~147,167 ms acumulados) e `services` (~128,123 ms acumulados). A criação real do Tk/CustomTkinter não pôde ser medida neste ambiente sem display Windows. A construção antecipada de telas continua como risco conhecido; não foi alterada sem evidência física suficiente.

Não foram introduzidos `sleep`, busy-loop ou novo subprocesso. O splash fiel do Checkpoint 38 permaneceu funcionalmente intocado durante esta auditoria.

## Licenças

A fronteira de licença diária era calculada como 23:59:59, expirando até 999 ms antes do fim do dia. Agora o limite é exclusivo em 00:00 do dia seguinte: 23:59:59.999999 permanece válido e exatamente 00:00 bloqueia. Os fluxos de licença, unlock e persistência existentes não foram redesenhados.

## DatabaseLock

- O lock agora grava token de proprietário e instante de criação do processo.
- PID reutilizado não é confundido com a instância antiga.
- Locks legados sem instante de criação usam o `mtime` como proteção adicional.
- Host remoto continua conservador: não é apagado por suposição local.
- A gravação usa `flush` + `fsync`; arquivo parcial é removido se a gravação falhar.
- Somente o token exato do proprietário pode liberar o lock.
- Validado por corrida de oito threads, cem reinícios rápidos e subprocesso encerrado abruptamente.

## Atualização offline

O helper de atualização deixou de depender apenas de PID: o processo original também é identificado pelo instante de criação. Isso evita espera indevida ou ação sobre um PID reutilizado. O formato e a regra de aplicação da atualização não foram alterados.

## Banco, memória e recursos

- Stress: 1.000 vendas, 2.000 movimentos, 100 cancelamentos e 100 rollbacks injetados; aprovado.
- Benchmark: consultas de produtos, clientes, histórico, dashboard e financeiro aprovadas.
- Soak final: 5.000 ciclos, 1.000 commits e 4.000 rollbacks; aprovado.
- Soak prolongado executado em quatro rodadas separadas: 20.000 ciclos, 4.000 commits e 16.000 rollbacks no total; sem crescimento progressivo nas amostras de memória.
- Regressão adicional: 3.000 sessões do `DatabaseManager`, sem crescimento de descritores/threads e com crescimento de memória abaixo de 512 KiB.
- Suíte focada de banco: 48 testes aprovados, incluindo backup, schema, migrations, transações e integridade.

## Build offline

O pipeline PowerShell agora valida cada entrada de `wheelhouse/SHA256SUMS.txt`, rejeita caminho inseguro, arquivo ausente, hash divergente e wheel não listado. A `.build-venv` temporária é recriada; `build_output/wheelhouse` é preservado.

Auditoria local da infraestrutura: `{"ok": true, "version": "2.5.1", "distribution": "NabiCode_v2_5_1"}`. Perfil da raiz: `TESTE`; perfil do artefato: `PRODUCAO`.

O wheelhouse e as ferramentas Windows não estão presentes/executáveis neste ambiente Linux. PyInstaller, Inno Setup, smoke do executável instalado e hashes reais do wheelhouse permanecem pendentes de reexecução física no Windows.

## Código morto e falhas latentes

Varreduras com Pyflakes e Vulture foram usadas apenas como diagnóstico. Nenhum bloco foi removido por aparência. Foram corrigidas quatro referências indefinidas comprovadas: parser da conferência XML, `Decimal` no fallback de preço, variável do dashboard e formatador do relatório MySQL. Após a correção, a varredura não encontrou nomes indefinidos nas áreas auditadas.

## Riscos residuais

- Fidelidade visual/FPS do splash, topmost, Alt+Tab, transições e encerramento do helper exigem validação no Windows instalado.
- Impressão e corte físicos não foram executados nesta auditoria.
- A criação completa da UI e contagem de handles Windows não são mensuráveis neste ambiente sem display/Win32.
- O build offline completo deve ser repetido em caminho curto, como `C:\NB\NabiCode`.

Conclusão: candidata DEV tecnicamente aprovada nas validações disponíveis, aguardando validação física Windows. Não é RELEASE.
