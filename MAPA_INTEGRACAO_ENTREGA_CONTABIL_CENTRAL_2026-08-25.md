# Mapa isolado — integração da entrega contábil com a Central do Contador

Data: 2026-08-25  
Branch: `codex/integracao-entrega-contabil-central`  
Worktree: `NabiCode-QT-EntregaContabilCentral-codex`  
Base imutável: `a179e791a82bc0a58c4ccccc1bccf357b6008fa8` (`origin/codex/homologacao-primeiro-uso`)  
Merge na branch estável: **não realizado**

## Proveniência auditada

- A entrega informada em `433264c44179d5d8b58301393ea29f2c94a1d845` tem como pai funcional `e544928` e merge-base `aa3cf7d` com a base de primeiro uso.
- Somente o commit funcional foi reaplicado sobre `a179e79`, gerando `8c2278b`; o mapa antigo não foi misturado ao mapa desta integração.
- Nenhuma alteração foi feita em `main_qt.py`, licensing, IA, Fiscal/SEFAZ ou banco operacional real.

## Concluído

1. Núcleo durável reaplicado em `8c2278b`:
   - outbox SQLite separada do banco operacional;
   - pacote imutável no spool e idempotência persistente;
   - estados `PREPARADO`, `ENFILEIRADO`, `ENVIADO_AO_TRANSPORTE`, `RECEBIDO_CONFIRMADO`, `FALHA` e `DESCONHECIDO`;
   - adaptador exclusivo para pasta local/rede/OneDrive já montada, com publicação atômica e recibo por hash;
   - resultado ambíguo obriga consulta antes de nova tentativa.
2. Porta de aplicação e vínculo do pacote em `ebcab6f`:
   - `AccountantDeliveryGateway` é a única porta entre o caso de uso e a outbox;
   - o resultado da geração carrega SHA-256 do ZIP exato;
   - revisão valida destinatário, CNPJ, consentimento, competência, perfil, hash e pasta existente;
   - destinatário permanece apenas em memória; a outbox persiste seu hash;
   - mesma operação produz a mesma chave idempotente;
   - todas as operações revalidam sessão, permissão e plano imutável.
3. Central e UX em `6e1d72b`, com reforço de teste em `4ac2ea3`:
   - módulo `Central do Contador` registrado com `relatorios/generate`;
   - entrega só abre após geração bem-sucedida e clique humano;
   - revisar, preparar, autorizar tentativa, copiar e verificar são cinco ações distintas;
   - `ENVIADO_AO_TRANSPORTE` informa expressamente que ainda não houve confirmação;
   - `RECEBIDO_CONFIRMADO` prova presença/recibo, não abertura, leitura, importação ou aprovação pelo contador;
   - `DESCONHECIDO` desabilita repetição e oferece somente verificação.

## Evidências

- Testes focados: `65 passed`.
- Teste adicional do acesso humano à entrega: `17 passed`.
- Regressão relacionada (pacote, reconciliação, segurança, composição, UI e outbox): `136 passed`, com um aviso esperado de nome ZIP duplicado criado pelo teste adversarial.
- `git diff --check`: sem erro (apenas avisos de normalização LF/CRLF do checkout Windows).
- Árvore de trabalho estava limpa após cada commit funcional.

## Limites mantidos

- Sem API, credencial, serviço pago ou sincronização própria de nuvem.
- OneDrive é aceito somente quando já aparece como pasta do sistema operacional.
- Sem transporte automático, temporizador ou reenvio silencioso.
- Sem declaração de que o contador recebeu intelectualmente, leu ou aprovou o conteúdo.
- Sem integração com Fiscal/SEFAZ, IA, licensing, shell legado ou banco real.

## Próximo passo autorizado

Executar `compileall`, repetir `git diff --check`, confirmar a lista final de arquivos, commitar este mapa separadamente e publicar apenas `codex/integracao-entrega-contabil-central`. A integração na branch estável continua proibida até decisão explícita posterior.
