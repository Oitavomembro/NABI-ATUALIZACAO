# Integração do Licenciamento — Notas IglBalt

Identidade provisória cadastrada no código:

- produto assinado: `NOTAS_IGLBALT`;
- nome visual: `Notas IglBalt`;
- edição: `COMPLETA`;
- recursos canônicos: `core`;
- tolerância: dez dias;
- formato próprio `.nabilic`: objeto com exatamente `payload` e `signature`;
- assinatura Ed25519 sobre os bytes UTF-8 do payload canônico, com chaves
  ordenadas, sem espaços, `ensure_ascii=false` e valores finitos;
- payload exato: `schema`, `product_id`, `edition`, `machine_code`, `features`,
  `issued_at`, `not_before` e `expires_at`;
- `not_before` e `expires_at` são `null` no contrato atual de homologação.

O aplicativo cliente deve carregar somente a chave pública bruta Base64,
decodificá-la para exatamente 32 bytes e validar o contrato em
`license_issuer/notas_iglbalt_format.py`. O funcionamento normal só pode ocorrer
depois da assinatura, produto, edição, máquina e features serem confirmados.

Licenças schema 2 e envelopes do NabiCode não possuem o formato externo exigido
pelo Notas IglBalt e devem ser recusados. O formato NabiCode permanece intacto.

Não transportar para o novo projeto chave privada, emissor, catálogo do
NabiCode, senha, licença real de cliente ou qualquer módulo comercial/fiscal/IA
do NabiCode. Antes de distribuição, criar fora do Git um par Ed25519 exclusivo
e entregar ao cliente somente o catálogo público correspondente.
