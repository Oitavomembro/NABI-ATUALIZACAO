# Emissor externo de Licenças NabiCode V2

## Cerimônia inicial

Execute `license_issuer_cli.py keygen` em máquina administrativa controlada.
Informe um caminho de chave privada fora do checkout e uma senha exclusiva com
no mínimo doze caracteres. O emissor recusa destino privado dentro do
repositório e nunca sobrescreve chave existente.

O comando produz:

- PEM PKCS#8 Ed25519 criptografado, privado;
- catálogo JSON contendo somente chave pública.

Copie apenas o catálogo público para
`licensing/trusted_public_keys.json`. A chave privada não pode entrar em Git,
logs, ticket, mensageria, backup comum do cliente ou pacote PyInstaller.

## Guarda obrigatória

Antes de uso real, o proprietário deve:

1. criar duas cópias criptografadas verificadas;
2. armazená-las em locais físicos separados e controlados;
3. guardar a senha por meio independente;
4. registrar `key_id`, hash SHA-256 do catálogo público e responsáveis;
5. testar restauração e emissão em ambiente isolado;
6. definir procedimento de rotação e comprometimento.

Essa etapa depende do segredo real do proprietário e não pode ser automatizada
ou simulada no repositório.

## Emissão

Obtenha o fingerprint hash pelo comando administrativo `--request`. Emita com
`license_issuer_cli.py issue`, informando titular, edição, validade, recursos e
destino `.nabilic`. Para revogar, emita documento mais recente com o mesmo UUID
e `--revoked`.

Nunca envie a chave privada ou sua senha ao cliente. O cliente recebe somente
o `.nabilic` assinado.

## Revisão jurídica pendente

Os termos comerciais, tratamento de dados, regras de revogação, suporte,
renovação, edição de avaliação e continuidade após bloqueio devem ser revisados
por profissional jurídico antes da distribuição. Este documento descreve o
controle técnico e não substitui contrato ou parecer legal.
