# Bugs encontrados e corrigidos — auditoria noturna

1. **Cleanup da splash podia interromper o `finally`.** Um segundo timeout após `kill()` escapava do helper. Corrigido para resultado controlado e continuidade do cleanup.
2. **Tarefas de runtime podiam sobreviver à janela.** O pool global não tinha shutdown explícito no encerramento principal. Corrigido antes da liberação do lock.
3. **PID reutilizado causava falso lock.** O lock identificava apenas PID/host. Corrigido com instante de criação e token de proprietário.
4. **Gravação parcial de lock.** Falha durante JSON podia deixar arquivo inválido. Corrigido com `flush`, `fsync` e remoção transacional do parcial.
5. **Release inseguro do lock.** Outra instância no mesmo PID lógico poderia remover o lock. Corrigido por token exato.
6. **Atualizador esperava PID reutilizado.** Corrigido com identidade PID + instante de criação.
7. **Licença diária expirava até 999 ms cedo.** Corrigido com limite exclusivo à meia-noite seguinte.
8. **Conferência XML chamava `numero` inexistente.** Corrigido para o parser validado compartilhado.
9. **Preço inválido no seletor referenciava `Decimal` ausente.** Corrigido com import da biblioteca padrão.
10. **Dashboard de relatórios usava `indicators` inexistente.** Corrigido para a variável `indicadores` retornada pelo serviço.
11. **Salvar relatório de migração chamava `formatar_relatorio` inexistente.** Corrigido para o mesmo formatador usado na prévia.
12. **Wheelhouse era consumido sem conferir integralmente o manifesto.** Corrigido com validação SHA-256 completa e rejeição de wheel extra.

Não corrigidos por falta de prova segura: importações pesadas e construção antecipada de telas. Alterá-las exigiria refatoração e medição física de UI, fora da regra desta missão.
