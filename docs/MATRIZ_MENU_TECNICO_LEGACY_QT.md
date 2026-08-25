# Matriz do Menu Técnico — Legacy → Qt

Data da auditoria: 25/08/2026  
Referência Legacy: `nabicode_legacy.py`, catálogo `admin_sections`  
Referência Qt: composição administrativa e shell da base `52ae726`

O Qt não recria operações administrativas só para preencher o menu. O gatilho
continua exigindo dez cliques em até cinco segundos, permissão
`technical/view` e confirmação da senha administrativa. Depois dessa dupla
barreira, cada janela revalida sua própria permissão original.

| Área existente no Legacy | Equivalente Qt já existente | Permissão preservada | Situação no menu restrito Qt |
|---|---|---|---|
| Licença | Nenhum módulo administrativo Qt neste escopo | Portão de licença próprio | Não incluída; licenciamento permanece fora desta correção |
| Banco de Dados | Central de Socorro: verificação somente leitura | `configs/view` | Incluída pelo módulo Central de Socorro; reparos de banco do Legacy não foram transportados |
| Backup | Configurações → Backup | `configs/view`; ações revalidam permissões próprias | Incluída pelo módulo Configurações |
| Atualizações | Nenhuma janela Qt existente na composição | Fluxo de atualização próprio | Não incluída; nenhuma função operacional ou atalho foi inventado |
| Padrão de fábrica | Nenhuma janela Qt existente na composição | Fluxo reforçado próprio | Não incluída; nenhuma operação destrutiva foi exposta |
| Diagnóstico | Configurações → Diagnóstico e Central de Socorro | `configs/view`; diagnóstico preserva sua autorização | Incluída pelos dois módulos existentes |
| Migração | Nenhuma janela Qt existente na composição | Fluxo de migração próprio | Não incluída; nenhuma importação foi criada |
| Demonstração | Nenhuma janela Qt existente na composição | Operação Legacy própria | Não incluída; dados fictícios não foram criados ou removidos |
| Ferramentas | Central de Socorro e catálogo VERDE já existente | `configs/view`; reparo suportado exige `configs/edit` | Incluída sem ampliar o catálogo de reparos |
| Sistema | Configurações/Diagnóstico e relatório sanitizado da Central de Socorro | `configs/view` | Incluída pelos módulos existentes, sem expor caminhos internos desnecessários |
| Segurança | Usuários e Auditoria | `technical/users` e `technical/audit` | Ambos incluídos e removidos da lista comum da sidebar |
| Suporte | Ajuda e Central de Socorro | `dashboard/view` e `configs/view` | Ambos incluídos; sem criar canal externo ou credencial |

## Resultado Qt

O menu restrito passa a conter, na ordem da composição:

1. Usuários;
2. Configurações;
3. Ajuda;
4. Central de Socorro;
5. Auditoria.

Essa lista reúne todos os equivalentes atualmente implementados. Configurações,
Ajuda e Central de Socorro mantêm seus acessos operacionais normais quando já
existiam; Usuários e Auditoria deixam de aparecer como favoritos comuns. A
Auditoria também deixa de ser apresentada pelo botão genérico `Histórico`, que
não correspondia ao histórico operacional do Legacy.

Shell e hubs principais usam os controles nativos minimizar,
maximizar/restaurar e fechar. Diálogos de senha, confirmação e aviso não recebem
essa promoção.
