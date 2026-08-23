# Licenciamento NabiCode V2

## Limite de segurança

O V2 substitui decisões locais editáveis por um documento `.nabilic` assinado
com Ed25519. O aplicativo distribuído contém apenas a chave pública. A chave
privada pertence ao proprietário, fica fora do repositório e não é acessada
pelo Legacy, Qt, banco, instalador ou serviços fiscais.

Identificadores brutos do Windows são normalizados somente em memória e
reduzidos por SHA-256 com domínio próprio. A licença e o estado protegido usam
apenas esse fingerprint. A cópia para outra máquina falha fechada.

## Documento canônico

O envelope possui exatamente `format`, `version`, `key_id`, `payload` e
`signature`. O payload é JSON UTF-8 canônico, codificado em base64url sem
padding, e a assinatura cobre seus bytes exatos. Campos desconhecidos,
duplicados, codificação não canônica, chave desconhecida e assinatura inválida
são recusados.

O payload assinado inclui:

- schema e UUID da licença;
- edição `COMERCIAL` ou `AVALIACAO`;
- titular;
- fingerprint SHA-256 da máquina;
- emissão UTC e validade civil;
- tolerância imutável de dez dias;
- recursos contratados;
- revogação explícita assinada.

A edição `AVALIACAO` é vinculada à máquina e limitada a trinta dias. Não existe
senha mestre, configuração de banco ou parâmetro local capaz de emitir,
prolongar ou desbloquear uma licença.

## Estados

- `ATIVA`: até 23:59:59 da validade;
- `TOLERANCIA`: os dez dias civis posteriores, inclusive;
- `BLOQUEADA`: a partir do décimo primeiro dia;
- `INVALIDA`: ausência, adulteração, chave desconhecida, máquina divergente ou
  estado protegido ausente/corrompido;
- `RELOGIO_SUSPEITO`: retrocesso superior a cinco minutos em relação ao último
  uso protegido;
- `REVOGADA`: somente por documento assinado mais recente.

O estado antifraude fica em `%APPDATA%/NabiCode/<perfil>/licensing_v2`, protegido
pela DPAPI em escopo da máquina e fora de `Program Files`. Excluir ou adulterar
esse estado bloqueia; não reinicia a tolerância.

## Portão e modo restrito

Legacy e Qt avaliam o mesmo portão antes de banco, atualização ou importação do
runtime. Assim, licença bloqueada impede operações mutáveis e impede a criação
de workers fiscais sem alterar qualquer regra de XML, outbox, transmissão ou
cancelamento.

Em qualquer estado permanecem disponíveis apenas:

- ativação/importação de `.nabilic`;
- diagnóstico mínimo e código da máquina;
- backup SQLite validado;
- exportação segura equivalente a uma cópia íntegra do banco.

Comandos do executável/checkout:

```text
--license-status
--activate-license C:\caminho\cliente.nabilic
--restricted-backup C:\destino
--safe-export C:\destino
```

Nenhum desses comandos transmite dados ou acessa a SEFAZ.

## Atualização e revogação

Renovação substitui o documento somente após verificar assinatura, máquina e
ordem temporal. O estado protegido conserva a maior emissão e validade já
aceitas, impedindo reinstalação de licença antiga. Atualizações do programa não
apagam os arquivos em AppData. Revogação exige uma nova licença assinada com
`revoked=true` e emissão mais recente.

## Portão de distribuição

O catálogo versionado está intencionalmente sem chave pública real. Antes de
qualquer entrega, executar uma cerimônia de chave fora do repositório, instalar
somente o catálogo público no build, validar o hash do catálogo e guardar duas
cópias criptografadas da chave privada em locais físicos separados. Até isso
ocorrer, o runtime V2 falha fechado e nenhuma cópia comercial/de avaliação está
liberada.
