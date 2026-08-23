# Pesquisa de referência — emissão offline com Ed25519

Pesquisa realizada em 23/08/2026 somente em fontes primárias. As referências
abaixo serviram para revisão de arquitetura e segurança. Nenhum código ou
formato externo foi copiado, e nenhuma nova dependência foi incorporada.

## Minisign

- Projeto oficial: <https://github.com/jedisct1/minisign>
- versão consultada: 0.12, tag/commit `b85e15d`;
- licença: ISC, conforme o arquivo `LICENSE` oficial;
- inspiração: ferramenta pequena e separada, chave secreta protegida por senha,
  verificação apenas com chave pública, comportamento conservador contra
  sobrescrita e suporte multiplataforma;
- não incorporado: formato Minisign, código-fonte, executável, CLI ou protocolo.

A licença ISC seria permissiva, mas não há razão técnica para acrescentar essa
dependência: o NabiCode já usa Ed25519 pela biblioteca `cryptography`.

## Keygen — exemplo de arquivos criptográficos vinculados à máquina

- repositório oficial:
  <https://github.com/keygen-sh/example-python-cryptographic-machine-files>
- commit consultado: `1870480` (04/09/2023);
- licença: MIT, conforme o arquivo `LICENSE` oficial;
- inspiração: artefato portátil associado ao fingerprint e validável localmente
  com chave pública;
- não incorporado: código, criptografia de conteúdo, serviço Keygen, protocolo
  de ativação, licença serial ou dependência de rede.

O exemplo usa Ed25519 em conjunto com AES-GCM. O NabiCode não precisa ocultar o
conteúdo da licença: precisa comprovar autenticidade e integridade. Adicionar
criptografia do payload aumentaria gestão de chaves e superfície de falha sem
atender requisito atual.

## PyCA cryptography

- documentação oficial Ed25519:
  <https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/>
- documentação oficial de serialização:
  <https://cryptography.io/en/latest/hazmat/primitives/asymmetric/serialization/>
- versão já incorporada e validada localmente: `cryptography 46.0.7`;
- distribuição oficial consultada:
  <https://pypi.org/project/cryptography/46.0.7/>;
- licença: Apache-2.0 ou BSD-3-Clause.

Foi mantido o uso já existente de assinatura Ed25519 e chave privada PKCS#8
criptografada. A biblioteca fornece wheels para Windows/Python 3.14, permitindo
instalação e execução offline depois que os artefatos aprovados forem colocados
em um repositório interno.

## Manutenção e cadeia de fornecimento

- Não baixar dependências durante emissão nem exigir serviço externo.
- Manter wheelhouse offline aprovado, com versão, hash SHA-256 e proveniência.
- Conferir assinatura/atestação publicada e o hash do wheel antes de promover.
- Gerar o executável administrativo em máquina controlada e registrar o hash.
- Produzir SBOM/lista de versões do pacote administrativo antes da distribuição.
- Reavaliar periodicamente vulnerabilidades e versões. A versão 46.0.7 corrigiu
  vulnerabilidade publicada, mas teve alerta de regressão/yank relacionado ao
  OpenSSL; portanto, ela permanece a versão testada neste checkout, não uma
  recomendação automática para produção. Qualquer atualização exige suíte e
  homologação próprias.
- Não incorporar GPL, AGPL, SSPL ou material sem licença sem decisão jurídica.

No Windows, o emissor é empacotado separadamente, não leva catálogo público,
licença ou segredo em `datas`, e funciona sem internet. A chave privada continua
externa ao executável e ao checkout. Backups criptografados, senha e restauração
dependem de cerimônia física do proprietário.

## Avisos de terceiros

Minisign e o exemplo Keygen foram apenas referências; por isso não entram em
`THIRD_PARTY_NOTICES.md`. `cryptography` já era dependência efetiva e já consta
nos avisos. Esta pesquisa registra a proveniência sem sugerir incorporação.
