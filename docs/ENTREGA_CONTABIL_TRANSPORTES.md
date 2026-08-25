# Entrega contábil — transportes

O núcleo recebe somente um pacote mensal que já passou pelo validador do
`AccountantMonthlyPackageService`. Antes de criar a entrega, ele exige e confere:

- destinatário informado, normalizado e sem caracteres de controle;
- CNPJ válido e confirmação booleana explícita do operador;
- consentimento booleano explícito para a entrega;
- competência no formato `AAAA-MM` e perfil `ESSENCIAL`, `COMPLETO` ou
  `AUDITORIA`;
- igualdade de CNPJ, competência e perfil com o manifesto validado;
- SHA-256 do ZIP e do manifesto calculados sobre o snapshot imutável do spool.

O nome do destinatário não é persistido. A outbox conserva apenas seu SHA-256,
os instantes das confirmações, os identificadores do pacote e o hash do vínculo
da configuração do transporte. CNPJ, perfil e competência continuam na outbox
porque identificam o pacote contábil entregue. Nenhum segredo ou credencial é
aceito por esta porta.

## Estados reais

- `PREPARADO`: pacote validado e snapshot imutável persistido;
- `ENFILEIRADO`: autorizado para uma tentativa do transporte;
- `ENVIADO_AO_TRANSPORTE`: o adaptador aceitou o pacote, mas não existe ainda
  comprovação consultada de recebimento;
- `RECEBIDO_CONFIRMADO`: uma consulta posterior encontrou o arquivo e um recibo
  estruturalmente válido, com o mesmo SHA-256, referência e transporte;
- `FALHA`: falha definida ou divergência que impede afirmar sucesso;
- `DESCONHECIDO`: a tentativa pode ter produzido efeito, portanto é proibido
  repeti-la antes de consultar.

`ENVIADO_AO_TRANSPORTE` nunca significa que o contador abriu, leu, importou ou
aprovou o conteúdo. `RECEBIDO_CONFIRMADO` também não substitui revisão contábil:
ele prova apenas a presença coerente do pacote e do recibo no destino controlado
pelo adaptador.

Toda repetição usa a mesma chave idempotente. A chave é vinculada ao hash do
pacote e manifesto, CNPJ, competência, perfil, destinatário e configuração do
transporte. Reutilizá-la com qualquer conteúdo divergente falha fechado. Trocar
a pasta configurada depois do preparo também falha, em vez de redirecionar uma
entrega silenciosamente.

## Transporte disponível

`LOCAL_FOLDER_V1` grava em uma pasta local, pasta de rede já montada pelo
Windows ou pasta já sincronizada pelo OneDrive. O NabiCode não cria a pasta, não
autentica no OneDrive e não chama API remota.

O adaptador:

1. confere novamente o SHA-256 do snapshot;
2. copia para um arquivo temporário exclusivo na própria pasta;
3. sincroniza e publica o ZIP atomicamente sem sobrescrever arquivo existente;
4. cria um recibo JSON separado, também publicado atomicamente;
5. consulta depois o ZIP e o recibo e recalcula seus hashes antes de confirmar.

O recibo contém somente layout, referência idempotente, SHA-256 do pacote,
identificador/vínculo do transporte e instante de criação. Ele não contém nome,
e-mail, telefone, CNPJ do contador ou CNPJ da empresa.

Se houver queda depois da publicação do ZIP e antes do recibo, a outbox fica
`DESCONHECIDO`. A consulta local verifica o ZIP exato e pode reconstruir o recibo
ausente; só então promove para `RECEBIDO_CONFIRMADO`. Arquivo ou recibo
incompatível nunca é sobrescrito e exige intervenção.

## Somente portas futuras

- Domínio/Onvio;
- e-mail;
- portal do contador.

Esses transportes não estão implementados. Não há token, senha, credencial,
endpoint ou alegação de compatibilidade no runtime. Cada integração futura deve
usar contrato oficial do fornecedor, armazenamento seguro de credenciais,
idempotência durável, consulta de recibo e testes próprios antes de qualquer
uso. Esta implementação não envia nada à SEFAZ e não altera Fiscal, IA, shell,
banco operacional ou regras contábeis/tributárias.
