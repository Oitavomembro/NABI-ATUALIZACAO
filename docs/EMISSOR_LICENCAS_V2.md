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

Abra `license_issuer_app.py` somente na máquina administrativa. Informe a chave
privada externa, o catálogo público correspondente, a solicitação da máquina,
o titular, a edição, a validade e os recursos. Escolha um novo destino
`.nabilic`.

O botão **Revisar** não assina nem grava. Ele exibe todos os dados não secretos
e um SHA-256 da revisão. Qualquer alteração posterior invalida a revisão. O
botão **Assinar e gerar** pede a senha somente nesse instante, confirma que a
chave privada corresponde ao catálogo, assina, verifica o resultado e cria o
arquivo sem sobrescrever destino existente.

O emissor é multiproduto. A seleção determina edição e recursos canônicos.
Estão cadastrados `NABICODE` e `NOTAS_IGLBALT` (nome visual "Notas IglBalt").
Cada produto exige chave e catálogo próprios; a chave privada do NabiCode nunca
deve assinar uma licença do Notas IglBalt. A chave permanente do novo produto
só pode ser criada em cerimônia externa.

O Notas IglBalt possui contrato externo próprio: a assinatura cobre somente o
payload canônico schema 3 e o documento contém apenas `payload` e `signature`.
Essa exceção é isolada em `license_issuer/notas_iglbalt_format.py`; não altera o
envelope V2 das licenças NabiCode existentes.

Também é possível usar `license_issuer_cli.py issue`. A linha de comando exibe
a mesma revisão e somente continua quando o operador digita `EMITIR`; a senha
não é argumento de linha de comando.

## Renovação e revogação

Use **Carregar licença anterior** e selecione também o catálogo público que a
valida. A ferramenta preserva fingerprint, titular, edição, recursos, UUID e
identificador da chave. Renovação exige emissão posterior e validade maior,
sempre criando outro arquivo. Revogação cria uma nova licença assinada com o
mesmo UUID e marcador de revogação; não altera o documento anterior.

Use **Verificar licença** (ou o subcomando `verify`) para validar assinatura e
exibir dados públicos. Verificação não usa nem solicita chave privada.

Nunca envie a chave privada ou sua senha ao cliente. O cliente recebe somente
o `.nabilic` assinado. Não existe validade ilimitada implícita, senha mestre ou
meio de prolongar uma licença sem nova assinatura.

## Empacotamento separado

O spec `build_tools/pyinstaller/nabicode_license_issuer.spec` gera o executável
administrativo `NabiCode_Emissor_Licencas_V2`, separado do aplicativo entregue
ao cliente. Ele exclui IA, PDV, serviços comerciais e entradas principais, e
não inclui catálogo, licença ou chave em `datas`.

Antes da distribuição, execute `build_tools/build_license_issuer.py` em máquina
controlada. O validador recusa o build se encontrar extensões comuns de segredo
ou licença no checkout. Registre hash, versões e lista de dependências do
artefato produzido.

Nunca envie a chave privada ou sua senha ao cliente. O cliente recebe somente
o `.nabilic` assinado.

As referências externas avaliadas e os riscos de cadeia de fornecimento estão
registrados em `docs/PESQUISA_EMISSORES_ED25519.md`.

## Revisão jurídica pendente

Os termos comerciais, tratamento de dados, regras de revogação, suporte,
renovação, edição de avaliação e continuidade após bloqueio devem ser revisados
por profissional jurídico antes da distribuição. Este documento descreve o
controle técnico e não substitui contrato ou parecer legal.
