# Integração controlada do diff de flash

## Bases comparadas

- Canônica: `NabiCode_v2_4_98_CHECKPOINT_1_AUDITORIA_20260808.zip`, SHA-256 `79FFA91F53C993199765FF2E53B614DE40EAFA0DC0B7A70967ED53D832961935`.
- Fonte de diff: `NabiCode_v2_4_98_CORRECAO_FLASH_WINDOWS.zip`, SHA-256 `5546C73268E9D4BF51B0BC953B76E943DD2CE9C13FC3C992E178E558E00CB082`.

## 25 arquivos ausentes do pacote de flash

1. `controllers/developer_tools_controller.py`
2. `controllers/legacy_backend_adapter.py`
3. `controllers/release_package_controller.py`
4. `database/runtime_adapter.py`
5. `database/sqlite_introspection.py`
6. `helpers/file_hashing.py`
7. `helpers/lazy_instance.py`
8. `REFACTOR_BASELINE.md`
9. `REFACTOR_CONFLITOS_PENDENTES.md`
10. `REFACTOR_PERSISTENCIA_AUDITORIA.md`
11. `REFACTOR_RELATORIO_FINAL.md`
12. `repositories/admin_audit_repository.py`
13. `repositories/emitted_document_repository.py`
14. `repositories/receipt_repository.py`
15. `services/legacy_runtime_facade.py`
16. `services/nfe_matching_service.py`
17. `services/update_package_validation_service.py`
18. `services/windows_shell_dispatcher.py`
19. `tests/test_cliente_repository_legacy_extraction.py`
20. `tests/test_extracted_cli_controllers.py`
21. `tests/test_extracted_services.py`
22. `tests/test_extracted_validators.py`
23. `validators/movement_validator.py`
24. `validators/nfe_import_validator.py`
25. `validators/receipt_validator.py`
26. `validators/stock_validator.py`

Nota: a comparação nominal inicial chamou o conjunto de “25 arquivos”, mas a enumeração reproduzível contém 26 caminhos. O valor correto é 26; a diferença anterior foi erro de contagem no relatório, não mudança de conteúdo.

## Arquivos exclusivos e úteis do pacote de flash

- `ui/screen_navigation.py`: mecanismo de navegação atômica.
- `ui/window_reveal.py`: mecanismo de revelação de Toplevel.
- `tests/test_atomic_screen_navigation.py`: regressões de navegação.
- `tests/test_toplevel_reveal.py`: regressões de janelas.
- Relatórios e lista de integração do trabalho anterior.

## Alterações integradas por intenção

- Conceito de montagem oculta e revelação tardia de Toplevel, reimplementado em `ui/window_reveal.py` sem transparência por alpha.
- Remoção da maximização do PDV durante construção.
- Revelação do PDV, histórico de cliente e histórico de notificações somente após montagem.
- Preparação das telas persistentes antes do `tkraise()`.
- Seis testes novos em `tests/test_flash_navigation_regression.py`.
- Atualização do teste legado do PDV para o novo contrato público.

## Alterações descartadas

- Substituição integral de `nabicode_legacy.py`: conflita com a refatoração e removeria adapters/facades/serviços novos.
- `AtomicScreenNavigator` como classe adicional: a base canônica já possui telas persistentes empilhadas; introduzi-lo exigiria mudanças de layout e backgrounds sem benefício necessário para corrigir a ordem.
- Containers/backplates adicionais e troca global de frames transparentes por fundos sólidos: potencial conflito com `BackgroundManager` e preferência visual do usuário.
- Uso de `attributes("-alpha", 0/1)`: não remove a causa e funciona como ocultação adicional; não foi transplantado.
- Testes que exigiam cor não branca em todas as telas e módulo inexistente `historico` na pilha: não representam fielmente a base canônica.
- Alterações não relacionadas em services, repositories, managers, database, validators e helpers: pertencem a uma linhagem anterior e conflitavam com a refatoração completa.

## Arquivos modificados no checkpoint

- `nabicode_legacy.py`
- `ui/__init__.py`
- `ui/window_reveal.py`
- `tests/test_flash_navigation_regression.py`
- `tests/test_sprint1_32_visual_pdv_receipt.py`
- Documentos do checkpoint.

## Testes

- Focados: `10 passed` na execução final focada.
- Suíte completa intermediária válida: `883 passed, 11 subtests passed`.
- A contagem aumentou de 877 para 883 devido a seis testes novos.
- Uma execução intermediária apresentou 17 erros de setup por falta de acesso ao diretório temporário global; a repetição com `--basetemp` isolado eliminou todos esses erros.

