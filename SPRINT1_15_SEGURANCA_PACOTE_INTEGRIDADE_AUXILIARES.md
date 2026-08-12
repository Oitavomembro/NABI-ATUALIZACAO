# Sprint 1.15 — Segurança do pacote e integridade dos auxiliares

- Banco operacional removido da base distribuível.
- Validador de empacotamento criado para bloquear bancos, backups, certificados, chaves e arquivos de segredo.
- Gerador de pacote de atualização passou a executar a validação antes de compactar.
- Erros SQLite de categorias e auxiliares são traduzidos para erros estáveis da camada de aplicação.
- Montagem de razão social e descrição foi removida da UI e centralizada em comando tipado.
- Catálogos agora rejeitam nomes duplicados e registros malformados.
- Compatibilidade de `criar_auxiliar(...)` foi mantida temporariamente.
