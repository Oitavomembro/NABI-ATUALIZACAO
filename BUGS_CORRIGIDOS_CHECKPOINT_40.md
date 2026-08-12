# Bugs corrigidos — Checkpoint 40

## Corrigidos em código

1. **Splash diferente do protótipo** — substituída a reinterpretação por motor byte a byte igual à fonte canônica, preservando a arquitetura de helper/readiness.
2. **PDV sem minimizar normalmente** — removido o atributo `transient` do PDV e adicionada ação explícita de minimizar, sem alterar atalhos.
3. **Duplo clique removia item** — duplo clique agora abre editor transacional da linha.
4. **Remoção ambígua** — movida para clique direito → “Remover item”, com confirmação.
5. **Campo de produto em estado cinza/inativo** — foco agora seleciona o conteúdo anterior sem consumir o evento interno do placeholder; Enter, setas, pesquisa e leitor permanecem sob os controladores existentes.
6. **Desinstalação com processo aberto deixava resíduos** — criado mutex Windows compartilhado com `AppMutex` do Inno. O setup não força encerramento durante operação; exige que a instância seja fechada normalmente.
7. **Atualização podia manter log incompleto de arquivos instalados** — definido `UninstallLogMode=append` para instalação sobre a mesma pasta/AppId.

## Investigado e não alterado

O Histórico de notificações é explicitamente um histórico em memória por sessão. Uma nova instância começa vazia mesmo sem desinstalação; portanto não existe evidência de remoção de dado persistente pelo instalador. Persistência não foi adicionada para evitar criar funcionalidade/regra não solicitada.

## Preservados

- DatabaseLock e mensagem controlada de segunda instância;
- licenças, expiração, bloqueio e desbloqueio;
- venda, orçamento, reabertura, cancelamento, recebimento e financeiro;
- estoque e cadastro mestre de produtos;
- impressão, PDF, recibo e corte;
- perfil fonte TESTE e perfil empacotado PRODUCAO.
