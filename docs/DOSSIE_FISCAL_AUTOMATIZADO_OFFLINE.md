# Dossiê fiscal automatizado offline

Este harness existe exclusivamente para o perfil `TESTE`. Ele exercita uma
máquina de estados determinística com adapters fake para prontidão, autorização,
rejeição, timeout, resposta desconhecida, consulta/reconciliação, cancelamento,
inutilização, contingência e bloqueios fail-closed.

A revisão 1.1 acrescenta o bloqueio explícito de autorização quando a numeração
fake não foi inicializada. A matriz operacional adversarial separada também
confirma que a API real exige gate, catálogo, numeração e reserva correspondente
antes de qualquer assinatura ou transporte simulado.

O arquivo do harness não importa nem compõe `FiscalService`, repositórios,
banco, certificado, endpoints ou interface. A entrada é executada diretamente
para não carregar o agregador amplo de `services`. Durante os cenários, traps
bloqueiam sockets e aliases internos, resolução DNS, HTTP, SQLite e abertura de
arquivos de certificado/chave por `open`, `pathlib`, `io` ou `os.open`. Qualquer
tentativa de ultrapassar essa fronteira aborta o dossiê.

Para gerar o JSON e o resumo humano sanitizado:

```powershell
python services/fiscal_offline_dossier.py --output-dir docs/evidencias/fiscal_offline
```

Os resultados `APROVADO` significam somente que o comportamento esperado pelo
teste automatizado foi observado. Códigos, mensagens e protocolos são sintéticos.
Nada neste dossiê comprova credenciamento, certificado, comunicação, autorização,
cancelamento ou inutilização pela SEFAZ.

Continuam pendentes e separados: homologação física acompanhada com empresa e
certificado autorizados, endpoints oficiais vigentes, NF-e 55, NFC-e 65,
impressão/DANFE/QR, evidências externas, contingência conforme norma e calendário
aplicáveis, pacote contábil, aprovações responsáveis e autorização expressa para
qualquer futura produção. Produção fiscal permanece bloqueada.
