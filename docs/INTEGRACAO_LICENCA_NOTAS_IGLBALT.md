# Integração do Licenciamento — Notas IglBalt

Identidade provisória cadastrada no código:

- produto assinado: `NOTAS_IGLBALT`;
- nome visual: `Notas IglBalt`;
- edição: `COMPLETA`;
- recursos canônicos: `core`;
- tolerância: dez dias;
- formato: envelope `.nabilic`, payload schema 3, assinatura Ed25519.

O aplicativo cliente deve carregar apenas sua chave pública e construir
`LicenseV2Service` com `expected_product_id="NOTAS_IGLBALT"`. A inicialização
normal só ocorre quando a decisão estiver `ATIVA` ou `TOLERANCIA`.

Licenças schema 2 são implicitamente do NabiCode e devem ser recusadas pelo
Notas IglBalt. Licenças schema 3 cujo `product_id` seja diferente também devem
ser recusadas, ainda que a assinatura seja criptograficamente válida.

Não transportar para o novo projeto chave privada, emissor, catálogo do
NabiCode, senha, licença real de cliente ou qualquer módulo comercial/fiscal/IA
do NabiCode. Antes de distribuição, criar fora do Git um par Ed25519 exclusivo
e entregar ao cliente somente o catálogo público correspondente.
