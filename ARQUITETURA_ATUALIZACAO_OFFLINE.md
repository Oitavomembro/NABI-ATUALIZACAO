# Arquitetura de atualização offline do NabiCode

Checkpoint 30  
Data: 08/08/2026  
Status: **ARQUITETURA DEFINIDA; IMPLEMENTAÇÃO DE CAMPO PENDENTE**

## Decisão

Para 2.5.1, priorizar **instalador completo versionado e assinado** em vez de criar imediatamente uma extensão proprietária `.nbu`.

Motivos:

- o onedir é pequeno o suficiente para pendrive;
- o Inno Setup possui instalação/desinstalação e rollback de arquivos mais maduros;
- reduz superfície de erro de um atualizador próprio;
- AppData já está separado de Program Files;
- migrações de banco já criam backup antes de alteração de schema.

O pacote ZIP incremental existente no código continua útil para laboratório, mas não deve escrever em Program Files sem elevação e validação adicional.

## Fluxo seguro proposto

```text
Setup atual + manifesto/hash
→ validar produto, versão, assinatura e SHA-256
→ verificar espaço e fechar instâncias
→ criar backup SQLite validado em AppData
→ registrar estado PREPARADO
→ instalar nova árvore em Program Files
→ iniciar nova versão
→ adquirir lock
→ executar migrations transacionais
→ executar diagnóstico e validar arquivos/versão
→ marcar CONCLUÍDO
→ em falha: restaurar arquivos da instalação anterior + snapshot do banco
```

## Componentes

1. Setup offline versionado: substitui somente arquivos imutáveis.
2. AppData: preserva banco, configurações, backups e histórico de atualização.
3. Manifesto: lista produto, versão, origem mínima, arquivos e hashes.
4. Backup SQLite validado: obrigatório antes de migrations.
5. Estado transacional: `PREPARADO`, `ARQUIVOS_APLICADOS`, `CONCLUIDO`, `FALHA` ou `ROLLBACK_CONCLUIDO`.
6. Diagnóstico pós-reinício: versão, hashes, schema, integridade SQLite e permissões.

## Segurança

- aceitar somente versões superiores e fontes compatíveis;
- usar comparação de hash resistente a timing;
- rejeitar caminhos absolutos e `..`;
- nunca incluir/extrair banco dentro de `{app}`;
- não remover arquivo desconhecido sem lista explícita;
- nunca aplicar com outra instância ativa;
- manter backup e log mesmo após sucesso;
- assinatura Authenticode recomendada para Setup e executável;
- hashes devem acompanhar o pendrive em arquivo separado e canal confiável.

## Rollback

O rollback precisa restaurar dois estados coordenados:

- arquivos imutáveis da versão anterior;
- snapshot do banco anterior à migration.

Se a restauração do banco falhar, o sistema deve permanecer bloqueado para operação e apontar o backup, nunca continuar com estado ambíguo.

## Política de compatibilidade

- reinstalação da mesma versão: permitida somente como reparo de arquivos, sem recriar dados;
- downgrade: bloqueado por padrão;
- atualização com salto de schema: permitida somente se migrations declararem caminho completo;
- atualização em banco de rede: exige backup no servidor e ausência de clientes conectados.

## O que não foi implementado

- nova extensão `.nbu`;
- downloader/internet;
- autoelevação silenciosa dentro do app;
- atualização física de Program Files neste Linux;
- assinatura de código.

## Arquivos alterados

- `ARQUITETURA_ATUALIZACAO_OFFLINE.md`.

Nenhuma rotina perigosa de sobrescrita foi adicionada.
