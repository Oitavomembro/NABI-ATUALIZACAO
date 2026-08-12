# NabiCode 2.5.1 DEV — Checkpoint 36

## Hotfix do startup smoke empacotado / perfil PRODUCAO

Data: 8 de agosto de 2026  
Estado: **NabiCode 2.5.1 DEV / candidata de instalação offline**  
Promoção para RELEASE: **não realizada**

Base obrigatória: `NabiCode_v2_5_1_DEV_CHECKPOINT_35_STARTUP_SPLASH.zip`  
SHA-256 da base: `489ab8b127f6e6c780ebe63c30591bb5704443c6809461c5fe3b6836f2817ee7`

## Causa raiz

O modo `--startup-smoke-test` encerrava antes de `configure_profile_environment()`, corretamente evitando criação de AppData, logs, banco, lock, splash e UI. Porém, `validate_packaged_startup_trace()` aceitava apenas o evento `runtime_profile_ready` com perfil `PRODUCAO`. Esse evento pertence ao runtime completo e, por construção, nunca poderia existir no smoke seguro.

O arquivo `PERFIL_NABICODE.txt` já estava corretamente empacotado em `_internal`. A falha era exclusivamente o contrato contraditório entre o entrypoint e o validador.

## Contrato corrigido

Foi adicionada a função somente leitura `resolve_profile_marker()` em `core/runtime_profile.py`. Ela:

- resolve `sys._MEIPASS` no executável PyInstaller;
- lê fisicamente `PERFIL_NABICODE.txt`;
- não usa `NABICODE_PROFILE` como evidência;
- não aceita fallback silencioso;
- falha se o marcador estiver ausente ou inválido;
- não cria diretórios, perfil mutável, AppData, log, banco ou lock.

O smoke agora registra:

```json
{
  "name": "packaged_profile_resolved",
  "details": {
    "profile": "PRODUCAO",
    "marker": "PERFIL_NABICODE.txt"
  }
}
```

e somente depois registra `startup_smoke_complete`.

O validador passou a exigir exatamente essa evidência. Ele também rejeita traces contendo qualquer evento que indique inicialização indevida de:

- runtime mutável;
- banco;
- `DatabaseLock`;
- splash;
- módulo legado;
- janela principal;
- `mainloop`.

Assim, nenhuma validação relevante foi removida. O contrato ficou mais específico e passou a verificar também a ausência de efeitos colaterais.

## Evidências automatizadas

- perfil da árvore-fonte: `TESTE`;
- perfil do recurso do artefato: `PRODUCAO`;
- versão: `2.5.1`;
- `python -m compileall -q .`: aprovado;
- testes focados: **22 passed, 3 subtests passed**;
- suíte completa: **934 passed, 11 subtests passed** em 18,41 s;
- nenhum teste anterior desapareceu: 931 → 934 testes;
- teste em subprocesso confirmou que o smoke da árvore-fonte não cria o diretório configurado em `APPDATA`;
- sequência do trace fonte confirmada sem runtime completo;
- contrato antigo foi reproduzido e corretamente reprovado;
- contrato novo só aprova `PRODUCAO` quando o evento deriva do marcador físico esperado.

## Componentes explicitamente não alterados

- splash visual do Checkpoint 35;
- fluxo de modais;
- lock de instância única e `DatabaseInUseError`;
- banco, schema e migrações;
- PDV, vendas e financeiro;
- impressão, corte e reimpressão;
- regras comerciais e cálculos;
- wheelhouse, PyInstaller spec e Inno Setup.

## Validação Windows

O build final não foi executado neste ambiente Linux. Portanto, o pipeline Windows permanece **PENDENTE DE VALIDAÇÃO FÍSICA**.

Para reconstruir em caminho curto:

```powershell
cd C:\NB\NabiCode
powershell -ExecutionPolicy Bypass -File build_tools\build_offline_windows.ps1
```

Após o build, verificar `build_output\startup_packaged.json`. A sequência mínima esperada é:

1. `process_imports_ready`;
2. `main_entered`;
3. `packaged_profile_resolved`, com `profile=PRODUCAO` e `marker=PERFIL_NABICODE.txt`;
4. `startup_smoke_complete`.

Não devem existir no trace `runtime_profile_ready`, `database_lock_acquired`, `splash_started`, `legacy_import_started`, `main_window_created` ou `mainloop_entered`.

Somente após o pipeline real passar no Windows deve-se considerar este hotfix fisicamente aprovado. A candidata não deve ser promovida para RELEASE nesta etapa.
