# Lista exata de arquivos alterados — Checkpoint 35

Comparação contra `NabiCode_v2_5_1_DEV_CHECKPOINT_34_INSTALLER_PIPELINE.zip`.

## Código e infraestrutura alterados

1. `main.py` — controle pause/stop/PID da splash, tratamento amigável do conflito de instância, log e fluxo de erro; smoke de build antes da criação de dados.
2. `splash_screen.py` — substituição do Matrix pelo motor Lightspeed Tk/Pillow desacoplado do tempo de startup.
3. `nabicode_legacy.py` — coordenação e parent explícito somente nos modais obrigatórios do startup.
4. `core/runtime_profile.py` — `DatabaseInUseError`, mantendo a semântica do lock.
5. `core/startup_window_coordinator.py` — novo coordenador de modais e sinal de pausa da splash.
6. `build_tools/pyinstaller/nabicode.spec` — hidden imports explícitos de `PIL.ImageDraw` e `PIL.ImageFont`.
7. `build_tools/references/splash_nabicode_deep_trust_fluid.py` — cópia byte a byte do protótipo visual aprovado, apenas para auditoria; não entra no runtime.

## Testes alterados/adicionados

8. `tests/test_checkpoint35_startup_splash.py` — 10 testes obrigatórios novos.
9. `tests/test_splash_screen_startup.py` — contratos do novo motor e teste adicional pause/PID.
10. `tests/test_v243_splash_and_cutter.py` — atualização do contrato visual substituído; testes de impressão/corte preservados.
11. `tests/test_sprint1_32_visual_pdv_receipt.py` — atualização do contrato de framebuffer reutilizado; testes do PDV preservados.
12. `tests/test_sprint1_33_pdv_visual_regressions.py` — atualização dos limites visuais; testes do PDV preservados.

## Documentação nova

13. `RELATORIO_TECNICO_CHECKPOINT_35_STARTUP_SPLASH.md`
14. `VALIDACAO_MANUAL_WINDOWS_CHECKPOINT_35.md`
15. `RESULTADO_TESTES_CHECKPOINT_35.txt`
16. `LISTA_EXATA_ARQUIVOS_ALTERADOS_CHECKPOINT_35.md`

Nenhum arquivo de PDV, vendas, financeiro, schema, impressão, corte, reimpressão ou cálculo comercial foi alterado.
