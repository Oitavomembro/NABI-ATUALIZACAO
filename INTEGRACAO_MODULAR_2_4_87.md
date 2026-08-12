# NabiCode 2.4.87 — Integração modular

Base: 2.4.86.

Módulos integrados:

- Financeiro: repository, calculator, formatter e recebimento de cliente fora do legado.
- Cadastros: repositories de manutenção, fornecedores, auxiliares e produtos.
- Documental: pipeline de PDF e impressão com renderizador compartilhado.
- Interface: ThemeManager centralizado.
- Legado: migração MySQL resumida delegada ao MySQLMigrationService.

Correções de integração:

- dependência document_rendering incluída e consolidada;
- PDFLineRenderer compatível com center_x;
- MySQLMigrationService atualizado junto do patch;
- contrato de alocação em parcela preservado;
- nenhum fluxo do PDV, pesquisa de produtos ou reimpressão foi redesenhado.
